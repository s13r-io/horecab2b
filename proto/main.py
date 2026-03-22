#!/usr/bin/env python3
"""
Main FastAPI application for NAM Agentic Procurement Platform.
"""

import json
import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse

from db.init_db import init_database
from models.schemas import (
    ChatRequest, ChatResponse,
    ApproveRequest, ApproveResponse,
    VendorPriceResponse
)
from agents.orchestrator import handle_message, handle_approval
from agents.routing import route_ingredient
from agents.forecasting import forecast_all_ingredients
from utils.data_loader import (
    get_demo_config, get_ingredient_unit, get_all_ingredients,
    get_all_recipes, get_last_n_days_sales, get_current_inventory,
    get_vendors_for_sku, get_all_inventory,
    compute_effective_lead_days, get_latest_price_for_vendor_sku,
    get_avg_price_for_vendor_sku, _load_vendor_pricing,
    get_moq_for_vendor_sku
)
from utils.helpers import audit_log


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Lifespan Management
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    init_database()
    logger.info("Database ready. Server starting...")
    yield
    # Shutdown
    logger.info("Server shutting down...")


# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(title="NAM Agentic Procurement Platform", lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for UI
try:
    app.mount("/ui", StaticFiles(directory="ui", html=True), name="ui")
except Exception as e:
    logger.warning(f"Could not mount UI static files: {e}")


# ============================================================================
# Root Redirect
# ============================================================================

@app.get("/")
async def root():
    """Redirect to UI."""
    return RedirectResponse(url="/ui/")


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


# ============================================================================
# Chat Endpoint
# ============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Processes user message and routes to appropriate agent.

    Request: ChatRequest (message, restaurant_id)
    Response: ChatResponse (response_text, action, data)
    """
    try:
        logger.info(f"Chat request from {request.restaurant_id}: {request.message[:50]}")

        # Get current date from config
        config = get_demo_config()

        # Handle message through orchestrator
        response = handle_message(request.message, request.restaurant_id)

        audit_log(
            agent_name="API",
            action="chat_request",
            restaurant_id=request.restaurant_id,
            data={"message_len": len(request.message), "action": response.action},
            duration_ms=0
        )

        return response

    except Exception as e:
        logger.error(f"Error in chat: {str(e)}", exc_info=True)
        audit_log(
            agent_name="API",
            action="chat_error",
            restaurant_id=request.restaurant_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Error processing message")


# ============================================================================
# Order Approval Endpoint
# ============================================================================

@app.post("/approve-order", response_model=ApproveResponse)
async def approve_order(request: ApproveRequest):
    """
    Approve a suggested order and dispatch to vendors.

    Request: ApproveRequest (order_id, restaurant_id)
    Response: ApproveResponse (status, messages, error)
    """
    try:
        logger.info(f"Approval request for order: {request.order_id}")

        # Handle approval through orchestrator
        response = handle_approval(request.order_id, request.restaurant_id)

        if response.status == "error":
            raise HTTPException(status_code=404, detail=response.error or "Order not found or not approvable")

        audit_log(
            agent_name="API",
            action="approve_order",
            restaurant_id=request.restaurant_id,
            order_id=request.order_id,
            data={"status": response.status},
            duration_ms=0
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in approve_order: {str(e)}", exc_info=True)
        audit_log(
            agent_name="API",
            action="approve_order_error",
            restaurant_id=request.restaurant_id,
            order_id=request.order_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Error approving order")


# ============================================================================
# Forecast Endpoint
# ============================================================================

@app.get("/forecast-today")
async def forecast_today(restaurant_id: str = "R001"):
    """
    Get today's demand forecast for all ingredients.

    Returns list of forecasted ingredients and estimated cost.
    """
    try:
        logger.info(f"Forecast request from {restaurant_id}")

        config = get_demo_config()
        target_date = config["current_date"]

        # Get forecasts
        forecasts = forecast_all_ingredients(target_date)

        # Calculate total estimated cost
        from agents.routing import route_order
        if forecasts:
            assignments = route_order(forecasts, target_date)
            total_cost = sum(a.estimated_cost for a in assignments)
        else:
            total_cost = 0.0

        audit_log(
            agent_name="API",
            action="forecast_today",
            restaurant_id=restaurant_id,
            data={"forecast_count": len(forecasts), "total_cost": total_cost},
            duration_ms=0
        )

        return {
            "forecasts": [
                {
                    "sku": f.sku,
                    "ingredient_name": f.ingredient_name,
                    "forecast_quantity": f.forecast_quantity,
                    "unit": f.unit,
                    "confidence": f.confidence,
                    "reasoning": f.reasoning
                }
                for f in forecasts
            ],
            "estimated_total_cost": total_cost,
            "date": target_date
        }

    except Exception as e:
        logger.error(f"Error in forecast_today: {str(e)}", exc_info=True)
        audit_log(
            agent_name="API",
            action="forecast_today_error",
            restaurant_id=restaurant_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Error generating forecast")


# ============================================================================
# Vendor Price Check Endpoint
# ============================================================================

@app.get("/vendor-prices")
async def vendor_prices(ingredient: str, quantity: float = 1.0, restaurant_id: str = "R001"):
    """
    Get price options for an ingredient across vendors.

    Query params:
    - ingredient: ingredient name or SKU
    - quantity: quantity to check (default: 1.0)
    - restaurant_id: restaurant ID (default: R001)

    Returns list of vendor options with prices and scoring.
    """
    try:
        logger.info(f"Price check for {ingredient} from {restaurant_id}")

        config = get_demo_config()
        target_date = config["current_date"]

        # Get vendor options
        options = route_ingredient(ingredient, quantity, target_date)

        if not options:
            raise HTTPException(status_code=404, detail=f"No vendors available for {ingredient}")

        unit = get_ingredient_unit(ingredient) if options else "kg"

        audit_log(
            agent_name="API",
            action="vendor_prices",
            restaurant_id=restaurant_id,
            data={"ingredient": ingredient, "options_count": len(options)},
            duration_ms=0
        )

        return {
            "ingredient": ingredient,
            "unit": unit,
            "quantity": quantity,
            "options": [
                {
                    "vendor_id": o.vendor_id,
                    "vendor_name": o.vendor_name,
                    "price_per_unit": o.price_per_unit,
                    "total_cost": o.total_cost,
                    "reliability_score": o.reliability_score,
                    "score": o.score,
                    "delivery_time": o.delivery_time,
                    "credit_days": o.credit_days,
                    "is_recommended": o.is_recommended,
                    "effective_lead_days": o.effective_lead_days
                }
                for o in options
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in vendor_prices: {str(e)}", exc_info=True)
        audit_log(
            agent_name="API",
            action="vendor_prices_error",
            restaurant_id=restaurant_id,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail="Error checking vendor prices")


# ============================================================================
# Inventory Dashboard Endpoint
# ============================================================================

@app.get("/api/inventory-dashboard")
async def inventory_dashboard(restaurant_id: str = "R001"):
    """
    Returns enriched inventory data for all ingredients.
    Includes avg daily consumption, days of stock, cutoff-aware lead times,
    and per-vendor details (cutoff status, earliest delivery, pricing).
    """
    try:
        from datetime import datetime, timedelta

        config = get_demo_config()
        current_date = config["current_date"]
        current_time = config.get("current_time", "12:00")
        current_date_obj = datetime.strptime(current_date, "%Y-%m-%d")
        ingredients = get_all_ingredients()
        recipes = get_all_recipes()
        sales_days = get_last_n_days_sales(7, current_date)
        num_days = len(sales_days) if sales_days else 1

        # Compute weekend & event multipliers (same as forecasting agent)
        weekday = current_date_obj.weekday()
        weekend_multiplier = 1.35 if weekday >= 4 else 1.0
        event_multiplier = 1.0
        for event in config.get("upcoming_events", []):
            event_date = datetime.strptime(event["date"], "%Y-%m-%d")
            days_until = (event_date - current_date_obj).days
            if 0 <= days_until <= 2:
                event_multiplier *= event.get("demand_multiplier", 1.0)

        # Weighted average weights (same as forecasting agent)
        weights = [1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.4]

        # Build lookup: sku -> list of (dish_id, qty_per_serving)
        sku_recipe_map = {}
        for recipe in recipes:
            for ing in recipe.get("ingredients", []):
                sku = ing["sku"]
                if sku not in sku_recipe_map:
                    sku_recipe_map[sku] = []
                sku_recipe_map[sku].append({
                    "dish_id": recipe["dish_id"],
                    "qty_per_serving": ing["quantity"]
                })

        result_ingredients = []
        for ingredient in ingredients:
            sku = ingredient["sku"]

            # Daily consumption from POS data (weighted average, same as forecast)
            daily_quantities = []
            for day in sales_days:
                day_qty = 0.0
                for sale in day.get("sales", []):
                    for mapping in sku_recipe_map.get(sku, []):
                        if sale["dish_id"] == mapping["dish_id"]:
                            day_qty += sale["quantity"] * mapping["qty_per_serving"]
                daily_quantities.append(day_qty)

            weights_used = weights[-len(daily_quantities):] if daily_quantities else []
            if weights_used:
                weighted_sum = sum(d * w for d, w in zip(daily_quantities, weights_used))
                base_daily = weighted_sum / sum(weights_used)
            else:
                base_daily = 0.0

            # Apply multipliers to get adjusted daily consumption
            adjusted_daily = round(base_daily * weekend_multiplier * event_multiplier, 2)

            # Current inventory
            qty_on_hand = get_current_inventory(sku)

            # Days of stock (based on adjusted daily consumption)
            days_of_stock = round(qty_on_hand / adjusted_daily, 1) if adjusted_daily > 0 else None

            # Per-vendor details with cutoff-aware lead times
            vendors = get_vendors_for_sku(sku, current_date)
            vendor_details = []
            for v in vendors:
                eff_lead = compute_effective_lead_days(v, current_time)
                cutoff = v.get("order_cutoff_time", "16:00")
                cutoff_missed = current_time >= cutoff
                delivery_date_obj = current_date_obj + timedelta(days=eff_lead)
                delivery_date_str = delivery_date_obj.strftime("%b %d")

                if eff_lead == 1:
                    earliest_delivery_str = f"Tomorrow, {v.get('delivery_time', '')}"
                else:
                    earliest_delivery_str = f"{delivery_date_str}, {v.get('delivery_time', '')}"

                vendor_details.append({
                    "vendor_id": v["vendor_id"],
                    "vendor_name": v["vendor_name"],
                    "reliability_score": v.get("reliability_score", 0),
                    "order_cutoff_time": cutoff,
                    "cutoff_missed": cutoff_missed,
                    "delivery_time": v.get("delivery_time", ""),
                    "effective_lead_days": eff_lead,
                    "earliest_delivery": earliest_delivery_str,
                    "latest_price": get_latest_price_for_vendor_sku(v["vendor_id"], sku),
                    "avg_price": get_avg_price_for_vendor_sku(v["vendor_id"], sku),
                    "moq": get_moq_for_vendor_sku(v["vendor_id"], sku),
                })

            # Sort vendors: cutoff not missed first, then by effective lead days
            vendor_details.sort(key=lambda x: (x["cutoff_missed"], x["effective_lead_days"]))

            # Earliest delivery across all vendors
            if vendor_details:
                earliest_lead = min(vd["effective_lead_days"] for vd in vendor_details)
            else:
                earliest_lead = None

            # Status based on days_of_stock vs earliest effective lead time
            # Critical: stock runs out before delivery arrives
            # Warning: stock < lead_time + 1 day (1 day safety buffer)
            if days_of_stock is None or adjusted_daily == 0:
                status = "ok"
            elif earliest_lead is not None and days_of_stock <= earliest_lead:
                status = "critical"
            elif earliest_lead is not None and days_of_stock <= earliest_lead + 1:
                status = "warning"
            else:
                status = "ok"

            # Forecast order quantity (same formula as forecasting agent)
            # Target = (2 * lead_time + 1) * adjusted_daily - current_inventory
            # Only show order for critical/warning items (ensures consistency)
            if status != "ok" and earliest_lead is not None and adjusted_daily > 0:
                coverage_days = 2 * earliest_lead + 1
                target_stock = adjusted_daily * coverage_days
                forecast_order = round(max(0.0, target_stock - qty_on_hand), 1)
            else:
                forecast_order = 0.0

            # Apply MOQ from best vendor (first in sorted list)
            moq = 0.0
            moq_applied = False
            if vendor_details and forecast_order > 0:
                best_vid = vendor_details[0]["vendor_id"]
                moq = get_moq_for_vendor_sku(best_vid, sku)
                if forecast_order < moq:
                    moq_applied = True
                    forecast_order = moq

            result_ingredients.append({
                "sku": sku,
                "name": ingredient["name"],
                "category": ingredient["category"],
                "unit": ingredient["unit"],
                "quantity_on_hand": qty_on_hand,
                "avg_daily_consumption": adjusted_daily,
                "days_of_stock": days_of_stock,
                "earliest_delivery_days": earliest_lead,
                "forecast_order": forecast_order,
                "moq": moq,
                "moq_applied": moq_applied,
                "shelf_life_days": ingredient.get("shelf_life_days"),
                "perishable": ingredient.get("perishable", False),
                "status": status,
                "vendors": vendor_details
            })

        # Sort: critical first, then warning, then ok; within group by days_of_stock asc
        status_order = {"critical": 0, "warning": 1, "ok": 2}
        result_ingredients.sort(key=lambda x: (
            status_order.get(x["status"], 3),
            x["days_of_stock"] if x["days_of_stock"] is not None else 9999
        ))

        return {
            "snapshot_date": current_date,
            "current_time": current_time,
            "ingredients": result_ingredients
        }

    except Exception as e:
        logger.error(f"Error in inventory_dashboard: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error loading inventory dashboard")


# ============================================================================
# Menu Dashboard Endpoint
# ============================================================================

@app.get("/api/menu-dashboard")
async def menu_dashboard(restaurant_id: str = "R001"):
    """
    Returns all dishes with sales data and expandable ingredient breakdown.
    Includes dishes with 0 sales.
    """
    try:
        config = get_demo_config()
        current_date = config["current_date"]
        recipes = get_all_recipes()
        ingredients = get_all_ingredients()
        sales_days = get_last_n_days_sales(7, current_date)
        num_days = len(sales_days) if sales_days else 1

        # Build ingredient name lookup
        ing_name_map = {ing["sku"]: ing["name"] for ing in ingredients}

        # Aggregate sales per dish across all days
        dish_sales = {}  # dish_id -> {total_sold, total_revenue}
        for day in sales_days:
            for sale in day.get("sales", []):
                did = sale["dish_id"]
                if did not in dish_sales:
                    dish_sales[did] = {"total_sold": 0, "total_revenue": 0}
                dish_sales[did]["total_sold"] += sale["quantity"]
                dish_sales[did]["total_revenue"] += sale.get("revenue", sale["quantity"] * 0)

        # Compute period dates
        if sales_days:
            period_start = sales_days[0]["date"]
            period_end = sales_days[-1]["date"]
        else:
            period_start = current_date
            period_end = current_date

        result_dishes = []
        for recipe in recipes:
            did = recipe["dish_id"]
            sales = dish_sales.get(did, {"total_sold": 0, "total_revenue": 0})
            total_sold = sales["total_sold"]
            total_revenue = sales["total_revenue"]

            # If revenue is 0 but we have sales, compute from avg_price
            if total_revenue == 0 and total_sold > 0:
                total_revenue = total_sold * recipe.get("avg_price", 0)

            # Ingredient breakdown
            ing_breakdown = []
            for ing in recipe.get("ingredients", []):
                ing_breakdown.append({
                    "sku": ing["sku"],
                    "name": ing_name_map.get(ing["sku"], ing["sku"]),
                    "qty_per_serving": ing["quantity"],
                    "unit": ing["unit"],
                    "total_consumed": round(total_sold * ing["quantity"], 2)
                })

            result_dishes.append({
                "dish_id": did,
                "dish_name": recipe["dish_name"],
                "category": recipe.get("category", ""),
                "avg_price": recipe.get("avg_price", 0),
                "total_sold": total_sold,
                "avg_daily_sold": round(total_sold / num_days, 1),
                "total_revenue": round(total_revenue),
                "ingredients": ing_breakdown
            })

        # Sort by total_revenue descending
        result_dishes.sort(key=lambda x: x["total_revenue"], reverse=True)

        return {
            "period_days": num_days,
            "period_start": period_start,
            "period_end": period_end,
            "dishes": result_dishes
        }

    except Exception as e:
        logger.error(f"Error in menu_dashboard: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error loading menu dashboard")


# ============================================================================
# Vendors Dashboard Endpoint
# ============================================================================

@app.get("/api/vendors-dashboard")
async def vendors_dashboard(restaurant_id: str = "R001"):
    """
    Returns all vendors with their profiles and the ingredients they supply,
    including latest and average prices.
    """
    try:
        vendor_data = _load_vendor_pricing()
        config = get_demo_config()
        current_time = config.get("current_time", "12:00")
        ingredients = get_all_ingredients()
        ing_name_map = {ing["sku"]: ing["name"] for ing in ingredients}
        ing_unit_map = {ing["sku"]: ing["unit"] for ing in ingredients}

        result_vendors = []
        for vendor in vendor_data["vendors"]:
            vid = vendor["vendor_id"]

            # Collect all SKUs this vendor has ever priced
            sku_set = set()
            for snapshot in vendor_data["pricing_history"]:
                for entry in snapshot["prices"]:
                    if entry["vendor_id"] == vid:
                        sku_set.update(entry.get("items", {}).keys())

            # Build ingredient list with prices
            vendor_ingredients = []
            for sku in sorted(sku_set):
                latest = get_latest_price_for_vendor_sku(vid, sku)
                avg = get_avg_price_for_vendor_sku(vid, sku)
                vendor_ingredients.append({
                    "sku": sku,
                    "name": ing_name_map.get(sku, sku.replace("_", " ").title()),
                    "unit": ing_unit_map.get(sku, "kg"),
                    "latest_price": latest,
                    "avg_price": avg,
                    "moq": vendor.get("min_order_qty", {}).get(sku, 0)
                })

            lead_days = compute_effective_lead_days(vendor, current_time)

            result_vendors.append({
                "vendor_id": vid,
                "vendor_name": vendor["vendor_name"],
                "category": vendor["category"],
                "contact": vendor.get("contact", ""),
                "whatsapp": vendor.get("whatsapp", ""),
                "delivery_time": vendor.get("delivery_time", ""),
                "delivery_days": vendor.get("delivery_days", 1),
                "effective_lead_days": lead_days,
                "order_cutoff_time": vendor.get("order_cutoff_time", ""),
                "cutoff_missed": current_time >= vendor.get("order_cutoff_time", "23:59"),
                "reliability_score": vendor.get("reliability_score", 0),
                "quality_score": vendor.get("quality_score", 0),
                "credit_available": vendor.get("credit_available", False),
                "credit_days": vendor.get("credit_days", 0),
                "comm_channel": vendor.get("comm_preferences", {}).get("channel", ""),
                "comm_language": vendor.get("comm_preferences", {}).get("language", ""),
                "ingredient_count": len(vendor_ingredients),
                "ingredients": vendor_ingredients
            })

        return {
            "snapshot_time": current_time,
            "snapshot_date": config["current_date"],
            "vendor_count": len(result_vendors),
            "vendors": result_vendors
        }

    except Exception as e:
        logger.error(f"Error in vendors_dashboard: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error loading vendors dashboard")


# ============================================================================
# Error Handler
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Generic HTTP exception handler - never expose stack traces."""
    logger.error(f"HTTP exception: {exc.detail}")
    audit_log(
        agent_name="API",
        action="http_error",
        error=exc.detail
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler - never expose stack traces."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    audit_log(
        agent_name="API",
        action="unhandled_error",
        error=str(exc)
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "An error occurred processing your request",
            "status_code": 500
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
