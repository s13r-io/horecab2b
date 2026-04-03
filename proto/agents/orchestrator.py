#!/usr/bin/env python3
"""
AG-ORCH: Orchestrator Agent
Central hub that routes intents to appropriate agents and manages order lifecycle.
"""

import json
import sqlite3
from datetime import datetime
from anthropic import Anthropic

from models.schemas import ChatResponse, ApproveResponse, ForecastResponse, VendorMessage
from agents.perception import parse_intent
from agents.forecasting import forecast_all_ingredients, forecast_ingredient
from agents.routing import route_ingredient, route_order
from agents.dispatcher import dispatch_order
from utils.helpers import generate_order_id, audit_log
from utils.data_loader import (
    get_demo_config, get_all_ingredients, get_all_recipes,
    get_current_inventory, get_recipes_using_ingredient,
    get_pending_order_quantity, get_adjusted_daily_consumption
)
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)

_client = Anthropic()
_chat_histories: dict[str, list[dict]] = {}

# Conversation state: tracks pending multi-turn confirmations per restaurant
_pending_confirmations: dict[str, dict] = {}

# Staleness threshold for pending confirmations (seconds)
_PENDING_TIMEOUT_SECONDS = 300  # 5 minutes


def _classify_response(message: str) -> str:
    """
    Classify a user response to a pending confirmation prompt.
    Returns: 'yes', 'no', 'quantity:<float>', or 'other'.
    Lightweight — no LLM call.
    """
    msg = message.strip().lower()

    # Explicit yes
    if msg in ("yes", "yeah", "yep", "sure", "ok", "okay", "confirm", "go ahead", "do it",
               "yes please", "y", "haan", "ha"):
        return "yes"

    # Explicit no
    if msg in ("no", "nope", "cancel", "stop", "never mind", "skip", "n", "nahi", "nahi"):
        return "no"

    # Try to extract a quantity (e.g., "12", "12 kg", "order 12", "I'll take 12")
    qty_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kgs|litre|litres|l|units?)?', msg)
    if qty_match:
        return f"quantity:{float(qty_match.group(1))}"

    return "other"


def _gather_order_context(sku: str, target_date: str) -> dict:
    """
    Gather all context needed for order checks: forecast, inventory, pipeline, daily consumption.
    """
    forecast = forecast_ingredient(sku, target_date)
    current_inv = get_current_inventory(sku)
    pending_qty = get_pending_order_quantity(sku)
    daily = get_adjusted_daily_consumption(sku, target_date)
    effective_inv = current_inv + pending_qty
    days_of_stock = round(effective_inv / daily, 1) if daily > 0 else None

    # Get ingredient metadata
    all_ingredients = get_all_ingredients()
    ing = next((i for i in all_ingredients if i["sku"] == sku or i["name"].lower() == sku.lower()), None)

    return {
        "forecast": forecast,
        "forecast_qty": forecast.forecast_quantity,
        "current_inv": current_inv,
        "pending_qty": round(pending_qty, 1),
        "daily": daily,
        "effective_inv": round(effective_inv, 1),
        "days_of_stock": days_of_stock,
        "ingredient": ing,
    }


def _is_pending_stale(pending: dict) -> bool:
    """Check if a pending confirmation is stale (older than timeout)."""
    created = pending.get("created_at")
    if not created:
        return True
    elapsed = (datetime.now() - datetime.fromisoformat(created)).total_seconds()
    return elapsed > _PENDING_TIMEOUT_SECONDS


def _handle_pending_response(message: str, restaurant_id: str) -> ChatResponse:
    """
    Handle a user response to a pending confirmation prompt.
    Returns a ChatResponse, or None if the pending state should be cleared
    and the message processed as a fresh intent.
    """
    pending = _pending_confirmations[restaurant_id]

    # Auto-clear stale state
    if _is_pending_stale(pending):
        del _pending_confirmations[restaurant_id]
        return None

    classification = _classify_response(message)

    if classification == "no":
        del _pending_confirmations[restaurant_id]
        return ChatResponse(
            response_text="Order cancelled.",
            action="query"
        )

    if classification == "yes":
        return _continue_order_flow(restaurant_id, pending["working_qty"])

    if classification.startswith("quantity:"):
        chosen_qty = float(classification.split(":")[1])
        pending["working_qty"] = chosen_qty
        return _continue_order_flow(restaurant_id, chosen_qty)

    # classification == "other" — might be a topic change or the user chose a quantity option
    # Check if it matches one of the offered choices (for quantity_choice step)
    if pending["step"] == "quantity_choice":
        # Try matching against the two offered quantities
        msg_lower = message.strip().lower()
        forecast_qty = pending["forecast_qty"]
        user_qty = pending["user_qty"]
        # Check for phrases like "the forecast", "recommended", "your suggestion"
        if any(kw in msg_lower for kw in ("forecast", "recommend", "suggestion", "your", "system")):
            pending["working_qty"] = forecast_qty
            return _continue_order_flow(restaurant_id, forecast_qty)
        if any(kw in msg_lower for kw in ("mine", "my", "original", "i asked")):
            pending["working_qty"] = user_qty
            return _continue_order_flow(restaurant_id, user_qty)

    # Fall back: parse as fresh intent, clear pending if it's a different action
    del _pending_confirmations[restaurant_id]
    return None  # Caller will re-process as fresh intent


def _continue_order_flow(restaurant_id: str, working_qty: float) -> ChatResponse:
    """
    Resume the order flow from where it was paused.
    Runs remaining checks and either pauses again or creates the order.
    """
    pending = _pending_confirmations[restaurant_id]
    step = pending["step"]
    sku = pending["ingredient"]
    ing_name = pending["ingredient_name"]
    unit = pending["unit"]
    is_perishable = pending.get("is_perishable", False)
    forecast_qty = pending["forecast_qty"]
    pending_pipeline_qty = pending.get("pending_qty", 0)

    config = get_demo_config()
    target_date = config["current_date"]

    # After need_check or quantity_choice: proceed to routing + MOQ check
    # After moq_check: proceed directly to order creation

    if step == "moq_check":
        # User confirmed MOQ — create order with MOQ quantity
        del _pending_confirmations[restaurant_id]
        return _create_order_from_pending(pending, working_qty, target_date, restaurant_id)

    # --- Routing phase ---
    from models.schemas import IngredientForecast as IF
    order_forecast = IF(
        sku=sku,
        ingredient_name=ing_name,
        forecast_quantity=working_qty,
        unit=unit,
        confidence=1.0,
        reasoning=f"User-confirmed order quantity: {working_qty} {unit}"
    )
    # Check MOQ against the best single vendor (not sum of split assignments)
    vendor_options = route_ingredient(sku, working_qty, target_date)
    best_vendor_moq = vendor_options[0].moq if vendor_options else 0

    if working_qty < best_vendor_moq:
        # True MOQ bump — user's quantity is below the best vendor's minimum
        vendor_name = vendor_options[0].vendor_name
        moq_forecast = IF(
            sku=sku, ingredient_name=ing_name,
            forecast_quantity=best_vendor_moq, unit=unit,
            confidence=1.0, reasoning=f"MOQ-adjusted: {best_vendor_moq} {unit}"
        )
        assignments = route_order([moq_forecast], target_date)
        total_cost = sum(a.estimated_cost for a in assignments)

        pending["step"] = "moq_check"
        pending["working_qty"] = best_vendor_moq
        pending["moq"] = best_vendor_moq
        pending["assignments"] = assignments
        pending["total_cost"] = total_cost

        return ChatResponse(
            response_text=(
                f"Minimum order quantity requires **{best_vendor_moq} {unit}** "
                f"(you requested {working_qty} {unit}) from {vendor_name}.\n"
                f"Estimated cost: ₹{total_cost:.2f}\n\n"
                f"Order {best_vendor_moq} {unit} instead?"
            ),
            action="awaiting_confirmation",
            data={"step": "moq_check"}
        )

    assignments = route_order([order_forecast], target_date)
    total_cost = sum(a.estimated_cost for a in assignments)

    # All checks passed — create order
    del _pending_confirmations[restaurant_id]
    return _create_order_from_context(
        restaurant_id, order_forecast, assignments, total_cost, target_date,
        pending_pipeline_qty
    )


def _create_order_from_pending(pending: dict, working_qty: float, target_date: str, restaurant_id: str) -> ChatResponse:
    """Create order using cached assignments from MOQ check step."""
    assignments = pending.get("assignments")
    total_cost = pending.get("total_cost", 0)
    pending_pipeline_qty = pending.get("pending_qty", 0)

    if not assignments:
        # Re-route if assignments weren't cached
        from models.schemas import IngredientForecast as IF
        order_forecast = IF(
            sku=pending["ingredient"], ingredient_name=pending["ingredient_name"],
            forecast_quantity=working_qty, unit=pending["unit"],
            confidence=1.0, reasoning=f"User-confirmed: {working_qty} {pending['unit']}"
        )
        assignments = route_order([order_forecast], target_date)
        total_cost = sum(a.estimated_cost for a in assignments)
    else:
        from models.schemas import IngredientForecast as IF
        order_forecast = IF(
            sku=pending["ingredient"], ingredient_name=pending["ingredient_name"],
            forecast_quantity=working_qty, unit=pending["unit"],
            confidence=1.0, reasoning=f"User-confirmed: {working_qty} {pending['unit']}"
        )

    return _create_order_from_context(
        restaurant_id, order_forecast, assignments, total_cost, target_date,
        pending_pipeline_qty
    )


def _create_order_from_context(
    restaurant_id: str, forecast, assignments, total_cost: float,
    target_date: str, pending_pipeline_qty: float = 0
) -> ChatResponse:
    """
    Create order in DB and return confirmation response.
    Shared by both direct flow and pending confirmation resume.
    """
    config = get_demo_config()
    current_time = config.get("current_time", "15:30")

    order_id = generate_order_id()
    send_schedule = _compute_send_schedule(assignments, current_time, target_date)
    earliest_send_time = min([s["send_time"] for s in send_schedule.values()]) if send_schedule else None

    all_items = [{
        "sku": forecast.sku,
        "ingredient_name": forecast.ingredient_name,
        "quantity": forecast.forecast_quantity,
        "unit": forecast.unit
    }]

    try:
        conn = sqlite3.connect("db/prototype.db")
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO orders (order_id, restaurant_id, items, total_cost, status,
               vendors_assigned, scheduled_send_time)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (order_id, restaurant_id, json.dumps(all_items), total_cost, "suggested",
             json.dumps([{
                 "vendor_id": a.vendor_id,
                 "vendor_name": a.vendor_name,
                 "items": a.items,
                 "estimated_cost": a.estimated_cost,
                 "is_bridge_order": a.is_bridge_order
             } for a in assignments]),
             earliest_send_time)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        audit_log("AG-ORCH", "create_order_error", error=str(e), order_id=order_id)

    # Build confirmation text with pipeline context
    response_text = _build_order_confirmation_text_v2(
        order_id, forecast, assignments, send_schedule, total_cost, pending_pipeline_qty
    )

    return ChatResponse(
        response_text=response_text,
        action="order_confirmation",
        data={"order_id": order_id, "total_cost": total_cost}
    )


def _build_order_confirmation_text_v2(
    order_id: str, forecast, assignments, send_schedule: dict,
    total_cost: float, pending_pipeline_qty: float = 0
) -> str:
    """Build order confirmation with actual routed quantities and pipeline context."""
    is_split = any(a.is_bridge_order for a in assignments)
    sku = forecast.sku
    unit = forecast.unit

    text = f"**Order** `{order_id}`\n\n"

    if is_split:
        total_qty = sum(
            item["quantity"] for a in assignments for item in a.items if item["sku"] == sku
        )
        text += f"**{forecast.ingredient_name}** — {total_qty} {unit}\n"
        for a in assignments:
            for item in a.items:
                if item["sku"] != sku:
                    continue
                bridge_note = " *(urgent bridge)*" if a.is_bridge_order else ""
                text += (
                    f"  → {item['quantity']} {unit} from **{a.vendor_name}**"
                    f" @ ₹{item.get('price_per_unit', 0)}/{unit}{bridge_note}\n"
                )
    else:
        a = assignments[0]
        item = a.items[0]
        text += (
            f"**{forecast.ingredient_name}** — {item['quantity']} {unit}"
            f" @ ₹{item.get('price_per_unit', 0)}/{unit} → **{a.vendor_name}**\n"
        )

    text += f"\n**Total: ₹{total_cost:.2f}**\n"

    if pending_pipeline_qty > 0:
        text += f"\n*Note: {pending_pipeline_qty} {unit} of {forecast.ingredient_name} already on order.*\n"

    text += "\n**Dispatch**\n"
    for a in assignments:
        sched = send_schedule.get(a.vendor_id, {})
        send_time = sched.get("send_time", "")
        send_note = sched.get("note", "")
        bridge_note = " (bridge)" if a.is_bridge_order else ""
        text += f"• **{a.vendor_name}**{bridge_note} — {send_time} *({send_note})*\n"

    text += "\nReply **confirm** to place or **cancel** to discard."
    return text


def handle_message(message: str, restaurant_id: str) -> ChatResponse:
    """
    Main message handler. Routes to appropriate agents based on intent.
    Checks for pending confirmations before parsing new intent.
    """
    # Check for pending confirmation first
    pending = _pending_confirmations.get(restaurant_id)
    if pending:
        result = _handle_pending_response(message, restaurant_id)
        if result is not None:
            return result
        # result is None → pending was cleared, process as fresh intent

    # Parse intent
    intent = parse_intent(message, restaurant_id)

    if intent.action == "low_stock":
        return _handle_low_stock(intent, restaurant_id)
    elif intent.action == "approve_suggestion":
        return _handle_approve_suggestion(intent, restaurant_id)
    elif intent.action == "forecast_today":
        return _handle_forecast_today(restaurant_id)
    elif intent.action == "price_check":
        return _handle_price_check(intent, restaurant_id)
    elif intent.action == "place_order":
        return _handle_place_order(intent, restaurant_id)
    elif intent.action == "confirm_order":
        return _handle_confirm_order(intent, restaurant_id)
    else:
        return _handle_general_query(message, restaurant_id)


def _handle_low_stock(intent, restaurant_id: str) -> ChatResponse:
    """Handle low_stock intent."""
    if not intent.ingredient:
        return ChatResponse(
            response_text="I couldn't identify which ingredient is low. Can you specify?",
            action="query"
        )

    config = get_demo_config()
    target_date = config["current_date"]

    # Forecast this ingredient
    forecast = forecast_ingredient(intent.ingredient, target_date)

    if forecast.forecast_quantity <= 0:
        return ChatResponse(
            response_text=f"✓ {forecast.ingredient_name} is well-stocked. No order needed.",
            action="query"
        )

    # Route ingredient to vendors
    options = route_ingredient(intent.ingredient, forecast.forecast_quantity, target_date)

    if not options:
        return ChatResponse(
            response_text=f"⚠ No vendors available for {forecast.ingredient_name}.",
            action="query"
        )

    # Create order
    order_id = generate_order_id()
    forecasts = [forecast]
    assignments = route_order(forecasts, target_date)

    # Detect split orders
    bridge_assignments = [a for a in assignments if a.is_bridge_order]
    main_assignments = [a for a in assignments if not a.is_bridge_order]

    # Build items list for DB from all assignments
    all_items = []
    for a in assignments:
        for item in a.items:
            all_items.append({
                "sku": item["sku"],
                "ingredient_name": item["ingredient_name"],
                "quantity": item["quantity"],
                "unit": item["unit"]
            })

    # Save to database
    total_cost = sum(a.estimated_cost for a in assignments)
    try:
        conn = sqlite3.connect("db/prototype.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO orders (order_id, restaurant_id, items, total_cost, status, vendors_assigned)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                restaurant_id,
                json.dumps(all_items),
                total_cost,
                "suggested",
                json.dumps([{
                    "vendor_id": a.vendor_id,
                    "vendor_name": a.vendor_name,
                    "items": a.items,
                    "estimated_cost": a.estimated_cost,
                    "is_bridge_order": a.is_bridge_order
                } for a in assignments])
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        audit_log("AG-ORCH", "create_order_error", error=str(e), order_id=order_id)

    # Format response
    if bridge_assignments:
        # Split order response
        bridge = bridge_assignments[0]
        main = main_assignments[0] if main_assignments else None
        bridge_qty = bridge.items[0]["quantity"] if bridge.items else 0
        main_qty = main.items[0]["quantity"] if main and main.items else 0

        response_text = (
            f"🚨 **Split Order Suggested** (ID: {order_id})\n\n"
            f"**Item:** {forecast.ingredient_name}\n\n"
            f"⚡ **Bridge Order** (urgent):\n"
            f"  • {bridge_qty} {forecast.unit} from {bridge.vendor_name}\n"
            f"  • Cost: ₹{bridge.estimated_cost:.2f}\n"
            f"  • Delivers faster to cover until main order arrives\n\n"
        )
        if main:
            response_text += (
                f"📦 **Main Order:**\n"
                f"  • {main_qty} {forecast.unit} from {main.vendor_name}\n"
                f"  • Cost: ₹{main.estimated_cost:.2f}\n"
                f"  • Better price, longer lead time\n\n"
            )
        response_text += (
            f"**Total Cost:** ₹{total_cost:.2f}\n\n"
            f"✓ Click 'Confirm Order' to queue this order."
        )
    else:
        # Single order response
        vendor_names = ", ".join([a.vendor_name for a in assignments])
        actual_qty = main_assignments[0].items[0]["quantity"] if main_assignments and main_assignments[0].items else forecast.forecast_quantity
        moq_note = ""
        if actual_qty > forecast.forecast_quantity:
            moq_note = f" (adjusted from {forecast.forecast_quantity} {forecast.unit} to meet vendor MOQ)"

        response_text = (
            f"📦 **Order Suggested** (ID: {order_id})\n\n"
            f"**Item:** {forecast.ingredient_name}\n"
            f"**Quantity:** {actual_qty} {forecast.unit}{moq_note}\n"
            f"**Assigned to:** {vendor_names}\n"
            f"**Estimated Cost:** ₹{total_cost:.2f}\n\n"
            f"✓ Click 'Confirm Order' to queue this order."
        )

    return ChatResponse(
        response_text=response_text,
        action="suggestion",
        data={
            "order_id": order_id,
            "total_cost": total_cost,
            "vendor_assignments": [{
                "vendor_id": a.vendor_id,
                "vendor_name": a.vendor_name,
                "estimated_cost": a.estimated_cost,
                "is_bridge_order": a.is_bridge_order
            } for a in assignments]
        }
    )


def _handle_approve_suggestion(intent, restaurant_id: str) -> ChatResponse:
    """Handle approve_suggestion intent."""
    order_id = intent.order_id or _get_latest_suggested_order(restaurant_id)

    if not order_id:
        return ChatResponse(
            response_text="❌ No pending order to approve.",
            action="query"
        )

    approve_response = handle_approval(order_id, restaurant_id)

    if approve_response.status == "error":
        return ChatResponse(
            response_text=f"❌ Error: {approve_response.error}",
            action="query"
        )

    scheduled = approve_response.scheduled_send_time
    return ChatResponse(
        response_text=f"✅ Order {order_id} confirmed and queued!\n📅 Vendor messages will be sent at {scheduled}",
        action="order_queued",
        data={"order_id": order_id, "status": "queued", "scheduled_send_time": scheduled}
    )


def _handle_forecast_today(restaurant_id: str) -> ChatResponse:
    """Handle forecast_today intent."""
    config = get_demo_config()
    target_date = config["current_date"]

    forecasts = forecast_all_ingredients(target_date)

    if not forecasts:
        return ChatResponse(
            response_text="📊 No items need to be ordered today.",
            action="query"
        )

    # Route all forecasts
    assignments = route_order(forecasts, target_date)
    total_cost = sum(a.estimated_cost for a in assignments)

    # Format response
    forecast_text = "📊 **Today's Demand Forecast**\n\n"
    for forecast in forecasts:
        forecast_text += f"• {forecast.ingredient_name}: {forecast.forecast_quantity} {forecast.unit}\n"

    forecast_text += f"\n**Suggested Order Cost:** ₹{total_cost:.2f}\n"
    forecast_text += f"**Recommended Vendors:** {', '.join([a.vendor_name for a in assignments])}"

    # Save forecast to database
    forecast_id = generate_order_id().replace("ORD_", "FCST_")
    try:
        conn = sqlite3.connect("db/prototype.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO forecasts (forecast_id, restaurant_id, date, ingredients)
            VALUES (?, ?, ?, ?)
            """,
            (
                forecast_id,
                restaurant_id,
                target_date,
                json.dumps([{
                    "sku": f.sku,
                    "ingredient_name": f.ingredient_name,
                    "forecast_quantity": f.forecast_quantity,
                    "unit": f.unit,
                    "confidence": f.confidence
                } for f in forecasts])
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        audit_log("AG-ORCH", "save_forecast_error", error=str(e))

    return ChatResponse(
        response_text=forecast_text,
        action="forecast",
        data={
            "forecast_id": forecast_id,
            "forecasts": [{
                "sku": f.sku,
                "ingredient_name": f.ingredient_name,
                "forecast_quantity": f.forecast_quantity,
                "unit": f.unit
            } for f in forecasts],
            "estimated_total_cost": total_cost
        }
    )


def _handle_price_check(intent, restaurant_id: str) -> ChatResponse:
    """Handle price_check intent."""
    if not intent.ingredient:
        return ChatResponse(
            response_text="Which ingredient would you like to check prices for?",
            action="query"
        )

    config = get_demo_config()
    target_date = config["current_date"]

    options = route_ingredient(intent.ingredient, 1.0, target_date)

    if not options:
        return ChatResponse(
            response_text=f"❌ No vendors available for {intent.ingredient}.",
            action="query"
        )

    response_text = f"💰 **Price Check: {intent.ingredient}**\n\n"
    for i, opt in enumerate(options, 1):
        recommended = "✓ Recommended" if opt.is_recommended else ""
        moq_text = f" (MOQ: {opt.moq})" if opt.moq > 0 else ""
        lead_text = f", {opt.effective_lead_days}d lead"
        response_text += f"{i}. {opt.vendor_name}: ₹{opt.price_per_unit}/unit{moq_text}{lead_text} {recommended}\n"

    return ChatResponse(
        response_text=response_text,
        action="price_comparison",
        data={
            "ingredient": intent.ingredient,
            "options": [{
                "vendor_id": o.vendor_id,
                "vendor_name": o.vendor_name,
                "price_per_unit": o.price_per_unit
            } for o in options]
        }
    )


def _build_general_query_system_prompt() -> str:
    """Build a context-rich system prompt with restaurant data."""
    # Load restaurant profile
    data_dir = Path(__file__).parent.parent / "data"
    try:
        with open(data_dir / "restaurant_profile.json") as f:
            profile = json.load(f)
    except Exception:
        profile = {}

    # Build inventory summary
    ingredients = get_all_ingredients()
    inventory_lines = []
    for ing in ingredients:
        qty = get_current_inventory(ing["sku"])
        inventory_lines.append(f"  - {ing['name']} ({ing['sku']}): {qty} {ing['unit']} on hand")
    inventory_text = "\n".join(inventory_lines)

    # Build forecasted quantity lookup with target stock
    from agents.forecasting import forecast_ingredient
    from utils.data_loader import get_demo_config
    config = get_demo_config()
    target_date = config["current_date"]

    # Create a lookup dict for quick access to forecast quantities
    forecast_data = {}
    for ing in ingredients:
        forecast = forecast_ingredient(ing["sku"], target_date)
        # Extract target_stock from reasoning (format: "Target stock: XXkg.")
        target_stock = None
        if "Target stock:" in forecast.reasoning:
            parts = forecast.reasoning.split("Target stock:")
            if len(parts) > 1:
                stock_str = parts[1].split("kg")[0].strip()
                try:
                    target_stock = float(stock_str)
                except:
                    pass

        forecast_data[ing["name"].lower()] = {
            "order_quantity": forecast.forecast_quantity,  # Delta: what to ORDER
            "target_stock": target_stock,  # Total inventory needed
            "current_on_hand": get_current_inventory(ing["sku"]),
            "unit": ing["unit"],
            "sku": ing["sku"]
        }

    return f"""You are the procurement assistant for {profile.get('name', 'this restaurant')}.

KEY CONCEPT:
- "Order quantity" = what to ORDER (accounts for existing inventory)
- "Target stock" = total inventory you should have (after delivery)
- Example: Have 8kg, target is 19.4kg → order 11.4kg to reach target

RESPONSE RULES:
1. ONLY answer the exact question asked
2. No extra context, dishes, patterns, or reasoning
3. Keep to 1-2 sentences max
4. Always include quantities and units
5. Clarify what numbers mean (order vs target stock)

Current Inventory (on hand):
{inventory_text}

Forecast Data (for today):
{json.dumps(forecast_data, indent=2)}

RESPONSE TEMPLATES (follow exactly):
- "How much [ing] on hand?" → "You have X on hand. Target stock is Y. Order Z to reach target."
- "Do I need [ing]?" → "Yes, order X (brings total to Y)." or "No, on track."
- "How much [ing] needed?" → "You need Y total stock (currently have X, order Z)."

IMPORTANT: "Order quantity" is NOT additional to current stock—it's what to order to reach the target stock level."""


def _handle_general_query(message: str, restaurant_id: str) -> ChatResponse:
    """Handle general query using Claude API with per-restaurant chat history."""
    if restaurant_id not in _chat_histories:
        _chat_histories[restaurant_id] = []

    history = _chat_histories[restaurant_id]
    history.append({"role": "user", "content": message})

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=150,
            system=_build_general_query_system_prompt(),
            messages=history
        )

        response_text = response.content[0].text
        history.append({"role": "assistant", "content": response_text})
        return ChatResponse(response_text=response_text, action="query")

    except Exception as e:
        # Remove the user message so history stays clean for next attempt
        history.pop()
        return ChatResponse(
            response_text="I encountered an error processing your request.",
            action="query"
        )


def handle_approval(order_id: str, restaurant_id: str) -> ApproveResponse:
    """
    Confirm a suggested order and queue it with a scheduled send time.

    Verify status is 'suggested', compute send schedule, set 'queued'.
    """
    try:
        conn = sqlite3.connect("db/prototype.db")
        cursor = conn.cursor()

        # Get order
        cursor.execute(
            "SELECT status, items, vendors_assigned, scheduled_send_time FROM orders WHERE order_id = ?",
            (order_id,)
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return ApproveResponse(
                status="error",
                messages=[],
                error="Order not found"
            )

        status, items_json, vendors_assigned_json, existing_send_time = row

        if status != "suggested":
            conn.close()
            return ApproveResponse(
                status="error",
                messages=[],
                error=f"Order status is '{status}', expected 'suggested'"
            )

        # Compute scheduled send time if not already set
        vendors_assigned = json.loads(vendors_assigned_json)
        from models.schemas import VendorAssignment

        assignments = [
            VendorAssignment(
                vendor_id=v["vendor_id"],
                vendor_name=v["vendor_name"],
                items=v["items"],
                estimated_cost=v["estimated_cost"],
                routing_reason="Order confirmed"
            )
            for v in vendors_assigned
        ]

        if not existing_send_time:
            config = get_demo_config()
            current_time = config.get("current_time", "15:30")
            target_date = config["current_date"]
            send_schedule = _compute_send_schedule(assignments, current_time, target_date)
            scheduled_send_time = min(s["send_time"] for s in send_schedule.values()) if send_schedule else None
        else:
            scheduled_send_time = existing_send_time

        # Transition to queued
        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE orders SET status = 'queued', queued_at = ?, scheduled_send_time = ?, updated_at = ? WHERE order_id = ?",
            (now, scheduled_send_time, now, order_id)
        )
        conn.commit()
        conn.close()

        # Clear chat history so forecasts recalculate with this order in pipeline
        if restaurant_id in _chat_histories:
            _chat_histories[restaurant_id] = []

        return ApproveResponse(
            status="queued",
            messages=[],
            scheduled_send_time=scheduled_send_time
        )

    except Exception as e:
        return ApproveResponse(
            status="error",
            messages=[],
            error=str(e)
        )


def create_forecast_order(restaurant_id: str) -> dict:
    """
    Create an order from today's forecast without going through LLM intent parsing.
    Returns a dict with order_id, total_cost, response_text, action, and error (if any).
    """
    config = get_demo_config()
    target_date = config["current_date"]

    forecasts = forecast_all_ingredients(target_date)
    if not forecasts:
        return {"action": "query", "response_text": "No items need ordering based on today's forecast.", "order_id": None, "total_cost": 0}

    assignments = route_order(forecasts, target_date)
    total_cost = sum(a.estimated_cost for a in assignments)
    current_time = config.get("current_time", "15:30")
    send_schedule = _compute_send_schedule(assignments, current_time, target_date)
    order_id = generate_order_id()
    earliest_send_time = min([s["send_time"] for s in send_schedule.values()]) if send_schedule else None
    all_items = [{"sku": f.sku, "ingredient_name": f.ingredient_name,
                  "quantity": f.forecast_quantity, "unit": f.unit} for f in forecasts]
    try:
        conn = sqlite3.connect("db/prototype.db")
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO orders (order_id, restaurant_id, items, total_cost, status,
               vendors_assigned, scheduled_send_time) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (order_id, restaurant_id, json.dumps(all_items), total_cost, "suggested",
             json.dumps([{"vendor_id": a.vendor_id, "vendor_name": a.vendor_name,
                          "items": a.items, "estimated_cost": a.estimated_cost,
                          "is_bridge_order": a.is_bridge_order} for a in assignments]),
             earliest_send_time))
        conn.commit()
        conn.close()
    except Exception as e:
        audit_log("AG-ORCH", "create_order_error", error=str(e), order_id=order_id)
        return {"action": "error", "response_text": "Failed to save order.", "order_id": None, "total_cost": 0, "error": str(e)}

    response_text = _build_order_confirmation_text(order_id, forecasts, assignments, send_schedule, total_cost)
    return {"action": "order_confirmation", "response_text": response_text, "order_id": order_id, "total_cost": total_cost}


def _handle_place_order(intent, restaurant_id: str) -> ChatResponse:
    """
    Handle place_order intent with multi-turn conversational checks.

    Flow:
    1. Resolve ingredient
    2. Gather context (forecast, inventory, pipeline)
    3. Need check (if item not needed) → pause for confirmation
    4. Quantity comparison (if user qty ≠ forecast) → pause for confirmation
    5. Route to vendors
    6. MOQ check (if qty bumped) → pause for confirmation
    7. Create order
    """
    config = get_demo_config()
    target_date = config["current_date"]

    try:
        # --- Forecast context (multi-item) — keep original behavior, no per-item checks ---
        if intent.context == "forecast" or (not intent.ingredient and not intent.items):
            result = create_forecast_order(restaurant_id)
            if result["action"] != "order_confirmation":
                return ChatResponse(response_text=result["response_text"], action=result["action"])
            return ChatResponse(
                response_text=result["response_text"],
                action="order_confirmation",
                data={"order_id": result["order_id"], "total_cost": result["total_cost"]}
            )

        # --- Single ingredient context ---
        if not intent.ingredient:
            return ChatResponse(
                response_text="What would you like to order? Say 'order the forecast' or specify an ingredient.",
                action="query"
            )

        user_qty = intent.quantity  # may be None

        # Resolve ingredient
        all_ingredients = get_all_ingredients()
        ing = next(
            (i for i in all_ingredients
             if i["sku"] == intent.ingredient or i["name"].lower() == intent.ingredient.lower()),
            None
        )
        if not ing:
            return ChatResponse(
                response_text=f"Unknown ingredient: {intent.ingredient}",
                action="query"
            )

        sku = ing["sku"]

        # Gather full context
        ctx = _gather_order_context(sku, target_date)
        forecast_qty = ctx["forecast_qty"]
        current_inv = ctx["current_inv"]
        pending_qty = ctx["pending_qty"]
        daily = ctx["daily"]
        days_of_stock = ctx["days_of_stock"]
        unit = ing["unit"]

        # --- No quantity specified: use forecast directly ---
        if user_qty is None:
            if forecast_qty <= 0:
                # Well-stocked — inform with pipeline breakdown
                if pending_qty > 0:
                    msg = (
                        f"{ing['name']} is well-stocked. "
                        f"You have {current_inv} {unit} on hand + {pending_qty} {unit} already on order "
                        f"= {ctx['effective_inv']} {unit} effective stock"
                    )
                else:
                    msg = f"{ing['name']} is well-stocked ({current_inv} {unit} on hand"
                    if days_of_stock is not None:
                        msg += f", ~{days_of_stock} days of stock"
                    msg += ")."
                return ChatResponse(response_text=msg, action="query")

            # Use forecast quantity, skip to routing + MOQ
            working_qty = forecast_qty
            _pending_confirmations[restaurant_id] = {
                "step": "routing",  # skip straight to routing
                "ingredient": sku,
                "ingredient_name": ing["name"],
                "unit": unit,
                "user_qty": forecast_qty,
                "forecast_qty": forecast_qty,
                "working_qty": working_qty,
                "is_perishable": ing.get("perishable", False),
                "shelf_life_days": ing.get("shelf_life_days"),
                "days_of_stock": days_of_stock,
                "current_inv": current_inv,
                "pending_qty": pending_qty,
                "daily": daily,
                "created_at": datetime.now().isoformat(),
            }
            return _continue_order_flow(restaurant_id, working_qty)

        # --- User specified a quantity ---

        # STEP 2a: Need check — is the item needed?
        if forecast_qty <= 0:
            # Item not needed — warn with pipeline breakdown
            if pending_qty > 0:
                msg = (
                    f"You don't appear to need more **{ing['name']}** right now.\n"
                    f"• On hand: {current_inv} {unit}\n"
                    f"• Already on order (queued/placed): {pending_qty} {unit}\n"
                    f"• Effective stock: {ctx['effective_inv']} {unit}"
                )
            else:
                msg = (
                    f"You don't appear to need more **{ing['name']}** right now.\n"
                    f"• On hand: {current_inv} {unit}"
                )
            if days_of_stock is not None:
                msg += f"\n• Lasts approximately **{days_of_stock} days**"
            msg += f"\n\nDo you still want to order {user_qty} {unit}?"

            _pending_confirmations[restaurant_id] = {
                "step": "need_check",
                "ingredient": sku,
                "ingredient_name": ing["name"],
                "unit": unit,
                "user_qty": user_qty,
                "forecast_qty": 0,
                "working_qty": user_qty,
                "is_perishable": ing.get("perishable", False),
                "shelf_life_days": ing.get("shelf_life_days"),
                "days_of_stock": days_of_stock,
                "current_inv": current_inv,
                "pending_qty": pending_qty,
                "daily": daily,
                "created_at": datetime.now().isoformat(),
            }
            return ChatResponse(
                response_text=msg,
                action="awaiting_confirmation",
                data={"step": "need_check"}
            )

        # STEP 2b: Quantity comparison — user qty vs forecast qty
        if user_qty != forecast_qty:
            if pending_qty > 0:
                msg = (
                    f"Based on forecast, you need **{forecast_qty} {unit}** of {ing['name']} "
                    f"(accounting for {current_inv} {unit} on hand + {pending_qty} {unit} already on order).\n"
                    f"You asked for **{user_qty} {unit}**.\n\n"
                    f"Order **{user_qty}** or **{forecast_qty} {unit}**?"
                )
            else:
                msg = (
                    f"Based on forecast, you need **{forecast_qty} {unit}** of {ing['name']} "
                    f"(you have {current_inv} {unit} on hand).\n"
                    f"You asked for **{user_qty} {unit}**.\n\n"
                    f"Order **{user_qty}** or **{forecast_qty} {unit}**?"
                )

            _pending_confirmations[restaurant_id] = {
                "step": "quantity_choice",
                "ingredient": sku,
                "ingredient_name": ing["name"],
                "unit": unit,
                "user_qty": user_qty,
                "forecast_qty": forecast_qty,
                "working_qty": user_qty,  # default to user's choice
                "is_perishable": ing.get("perishable", False),
                "shelf_life_days": ing.get("shelf_life_days"),
                "days_of_stock": days_of_stock,
                "current_inv": current_inv,
                "pending_qty": pending_qty,
                "daily": daily,
                "created_at": datetime.now().isoformat(),
            }
            return ChatResponse(
                response_text=msg,
                action="awaiting_confirmation",
                data={
                    "step": "quantity_choice",
                    "choices": [user_qty, forecast_qty],
                    "unit": unit
                }
            )

        # STEP 2c: Quantities match — proceed directly to routing + MOQ
        _pending_confirmations[restaurant_id] = {
            "step": "routing",
            "ingredient": sku,
            "ingredient_name": ing["name"],
            "unit": unit,
            "user_qty": user_qty,
            "forecast_qty": forecast_qty,
            "working_qty": user_qty,
            "is_perishable": ing.get("perishable", False),
            "shelf_life_days": ing.get("shelf_life_days"),
            "days_of_stock": days_of_stock,
            "current_inv": current_inv,
            "pending_qty": pending_qty,
            "daily": daily,
            "created_at": datetime.now().isoformat(),
        }
        return _continue_order_flow(restaurant_id, user_qty)

    except Exception as e:
        # Clean up pending state on error
        _pending_confirmations.pop(restaurant_id, None)
        audit_log("AG-ORCH", "place_order_error", error=str(e), restaurant_id=restaurant_id)
        return ChatResponse(
            response_text=f"Error creating order: {str(e)}",
            action="query"
        )


def _handle_confirm_order(intent, restaurant_id: str) -> ChatResponse:
    """Handle confirm_order intent - transition suggested→queued."""
    order_id = intent.order_id or _get_latest_suggested_order(restaurant_id)

    if not order_id:
        return ChatResponse(
            response_text="❌ No pending order to confirm.",
            action="query"
        )

    try:
        conn = sqlite3.connect("db/prototype.db")
        cursor = conn.cursor()
        cursor.execute("SELECT status, scheduled_send_time FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()

        if not row or row[0] != "suggested":
            conn.close()
            return ChatResponse(
                response_text=f"❌ Order {order_id} is not awaiting confirmation.",
                action="query"
            )

        now = datetime.now().isoformat()
        cursor.execute(
            "UPDATE orders SET status = 'queued', queued_at = ?, updated_at = ? WHERE order_id = ?",
            (now, now, order_id)
        )
        conn.commit()
        conn.close()

        # Clear chat history for this restaurant so Claude recalculates forecasts with updated pending orders
        if restaurant_id in _chat_histories:
            _chat_histories[restaurant_id] = []

        scheduled = row[1]
        return ChatResponse(
            response_text=f"✅ Order {order_id} is now queued!\n📅 Vendor messages will be sent at {scheduled}",
            action="order_queued",
            data={"order_id": order_id, "scheduled_send_time": scheduled, "status": "queued"}
        )

    except Exception as e:
        audit_log("AG-ORCH", "confirm_order_error", error=str(e), order_id=order_id)
        return ChatResponse(
            response_text=f"❌ Error confirming order: {str(e)}",
            action="query"
        )


def _compute_send_schedule(assignments, current_time: str, target_date: str) -> dict:
    """Compute when to send each vendor's order."""
    from datetime import timedelta
    from utils.data_loader import get_vendor_by_id

    schedule = {}
    current_dt = datetime.strptime(f"{target_date} {current_time}", "%Y-%m-%d %H:%M")

    for assignment in assignments:
        vendor = get_vendor_by_id(assignment.vendor_id)
        cutoff_str = vendor.get("order_cutoff_time", "16:00")
        cutoff_dt = datetime.strptime(f"{target_date} {cutoff_str}", "%Y-%m-%d %H:%M")

        # Target send time = cutoff - 15 min
        send_dt = cutoff_dt - timedelta(minutes=15)
        minutes_until_cutoff = (cutoff_dt - current_dt).total_seconds() / 60

        if minutes_until_cutoff < 0:
            # Cutoff already passed
            send_dt = send_dt + timedelta(days=1)
            note = "next-day (cutoff passed)"
        elif minutes_until_cutoff < 30:
            # Less than 30 min to cutoff
            send_dt = current_dt
            note = "immediate (cutoff imminent)"
        else:
            note = "scheduled"

        schedule[assignment.vendor_id] = {
            "send_time": send_dt.strftime("%Y-%m-%d %H:%M"),
            "cutoff": cutoff_str,
            "note": note
        }

    return schedule


def _build_order_confirmation_text(order_id: str, forecasts, assignments, send_schedule: dict, total_cost: float) -> str:
    """Build order confirmation message."""
    text = f"**📦 Order Summary** (ID: {order_id})\n\n"
    text += "**Items:**\n"
    for forecast in forecasts:
        text += f"• {forecast.ingredient_name}: {forecast.forecast_quantity} {forecast.unit}\n"

    text += f"\n**Vendor Routing:**\n"
    for a in assignments:
        sched = send_schedule.get(a.vendor_id, {})
        send_time = sched.get("send_time", "")
        send_note = sched.get("note", "")
        text += f"• {a.vendor_name}: {len(a.items)} item(s), ₹{a.estimated_cost:.2f} | Send: {send_time} ({send_note})\n"

    text += f"\n**Total Cost:** ₹{total_cost:.2f}\n\n"
    text += "Say **'confirm'** to queue this order, or **'cancel'** to discard."
    return text



def _get_latest_suggested_order(restaurant_id: str) -> str:
    """Get most recent order with status='suggested'."""
    try:
        conn = sqlite3.connect("db/prototype.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT order_id FROM orders WHERE restaurant_id = ? AND status = 'suggested' ORDER BY created_at DESC LIMIT 1",
            (restaurant_id,)
        )
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None
