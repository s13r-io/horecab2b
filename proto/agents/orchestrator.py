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
    get_current_inventory, get_recipes_using_ingredient
)
from pathlib import Path



_client = Anthropic()
_chat_histories: dict[str, list[dict]] = {}


def handle_message(message: str, restaurant_id: str) -> ChatResponse:
    """
    Main message handler. Routes to appropriate agents based on intent.

    Intent routing:
    - low_stock → forecast_ingredient → route_ingredient → create order (status=suggested)
    - approve_suggestion → handle_approval
    - forecast_today → handle_forecast_today
    - price_check → route_ingredient (no order)
    - query → direct Claude API call
    """
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
            f"✓ Ready to approve. Click 'Approve' to dispatch."
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
            f"✓ Ready to approve. Click 'Approve' to dispatch."
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

    return ChatResponse(
        response_text=f"✅ Order {order_id} approved and dispatched!",
        action="query",
        data={"order_id": order_id, "status": "dispatched"}
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

    # Build menu summary
    recipes = get_all_recipes()
    menu_lines = []
    for r in recipes:
        ing_names = ", ".join(i["sku"] for i in r["ingredients"])
        menu_lines.append(f"  - {r['dish_name']}: uses {ing_names}")
    menu_text = "\n".join(menu_lines)

    return f"""You are the procurement assistant for {profile.get('name', 'this restaurant')}, a {profile.get('cuisine', '')} restaurant in {profile.get('location', '')}.
You serve ~{profile.get('avg_daily_covers', 100)} covers/day.

IMPORTANT: You must ONLY answer questions related to this restaurant's procurement, inventory, menu, and ingredients. If a question is outside this domain, politely redirect the user to ask about procurement topics.

When the user asks about an ingredient, ALWAYS check the inventory and menu data below to give a specific, data-driven answer.

Current Inventory:
{inventory_text}

Menu (dishes and their ingredients):
{menu_text}

When asked "do I need X?" or similar:
1. Check if X is in the inventory above
2. Check which dishes use X
3. Compare stock on hand vs expected daily usage
4. Give a concrete answer based on the data

Keep responses concise and specific to this restaurant's data."""


def _handle_general_query(message: str, restaurant_id: str) -> ChatResponse:
    """Handle general query using Claude API with per-restaurant chat history."""
    if restaurant_id not in _chat_histories:
        _chat_histories[restaurant_id] = []

    history = _chat_histories[restaurant_id]
    history.append({"role": "user", "content": message})

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
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
    Approve and dispatch an order.

    Verify status=="suggested", set "approved", dispatch, return messages.
    """
    try:
        conn = sqlite3.connect("db/prototype.db")
        cursor = conn.cursor()

        # Get order
        cursor.execute("SELECT status, items, vendors_assigned FROM orders WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return ApproveResponse(
                status="error",
                messages=[],
                error="Order not found"
            )

        status, items_json, vendors_assigned_json = row

        if status != "suggested":
            conn.close()
            return ApproveResponse(
                status="error",
                messages=[],
                error=f"Order status is '{status}', not 'suggested'"
            )

        # Update status to approved
        cursor.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE order_id = ?",
            ("approved", datetime.now().isoformat(), order_id)
        )
        conn.commit()
        conn.close()

        # Dispatch
        vendors_assigned = json.loads(vendors_assigned_json)
        from models.schemas import VendorAssignment

        assignments = [
            VendorAssignment(
                vendor_id=v["vendor_id"],
                vendor_name=v["vendor_name"],
                items=v["items"],
                estimated_cost=v["estimated_cost"],
                routing_reason="Order approved"
            )
            for v in vendors_assigned
        ]

        config = get_demo_config()
        messages = dispatch_order(order_id, assignments, "Spice Junction", config["current_date"])

        return ApproveResponse(
            status="dispatched",
            messages=[{
                "vendor_id": m.vendor_id,
                "vendor_name": m.vendor_name,
                "channel": m.channel,
                "message_text": m.message_text
            } for m in messages]
        )

    except Exception as e:
        return ApproveResponse(
            status="error",
            messages=[],
            error=str(e)
        )


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
