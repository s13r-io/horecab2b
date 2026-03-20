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
from utils.data_loader import get_demo_config, get_ingredient_unit
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
                    "is_recommended": o.is_recommended
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
