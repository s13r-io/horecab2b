#!/usr/bin/env python3
"""
Pydantic models for all data structures.
No project dependencies — only pydantic.
"""

from pydantic import BaseModel
from typing import Optional, List


# ============================================================================
# Intent Parsing
# ============================================================================

class ParsedIntent(BaseModel):
    action: str  # low_stock, approve_suggestion, forecast_today, price_check, query
    ingredient: Optional[str] = None
    quantity: Optional[float] = None
    context: Optional[str] = None
    additional_notes: Optional[str] = None
    order_id: Optional[str] = None


# ============================================================================
# Forecasting
# ============================================================================

class IngredientForecast(BaseModel):
    sku: str
    ingredient_name: str
    forecast_quantity: float
    unit: str
    confidence: float  # 0-1
    reasoning: str


# ============================================================================
# Routing
# ============================================================================

class VendorOption(BaseModel):
    vendor_id: str
    vendor_name: str
    price_per_unit: float
    total_cost: float
    reliability_score: float
    score: float  # total_cost / reliability_score (lower is better)
    delivery_time: str
    credit_days: int
    is_recommended: bool


class VendorAssignment(BaseModel):
    vendor_id: str
    vendor_name: str
    items: List[dict]  # [{sku, ingredient_name, quantity, unit, price_per_unit}, ...]
    estimated_cost: float
    routing_reason: str


# ============================================================================
# Orders
# ============================================================================

class OrderSuggestion(BaseModel):
    order_id: str
    restaurant_id: str
    items: List[dict]  # List of forecasted items
    vendor_assignments: List[VendorAssignment]
    total_cost: float
    status: str  # suggested, approved, dispatched
    response_text: str


# ============================================================================
# Dispatch
# ============================================================================

class VendorMessage(BaseModel):
    vendor_id: str
    vendor_name: str
    channel: str  # whatsapp, email, call
    message_text: str


# ============================================================================
# Agent Results
# ============================================================================

class AgentResult(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    agent: str
    duration_ms: int


# ============================================================================
# API Requests/Responses
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    restaurant_id: str = "R001"


class ChatResponse(BaseModel):
    response_text: str
    action: Optional[str] = None  # suggestion, forecast, price_comparison, general
    data: Optional[dict] = None  # Contains order_id for suggestions, etc.


class ApproveRequest(BaseModel):
    order_id: Optional[str] = None
    restaurant_id: str = "R001"


class ApproveResponse(BaseModel):
    status: str  # approved, dispatched, error
    messages: List[VendorMessage]
    error: Optional[str] = None


class ForecastResponse(BaseModel):
    forecasts: List[IngredientForecast]
    order_id: str
    estimated_total_cost: float
    routing_summary: str


class VendorPriceResponse(BaseModel):
    ingredient: str
    unit: str
    options: List[VendorOption]
