#!/usr/bin/env python3
"""
AG-DPF: Demand Prediction & Forecasting Agent
Predicts ingredient needs using weighted average of historical sales.
"""

from datetime import datetime, timedelta
from typing import List

from models.schemas import IngredientForecast
from utils.data_loader import (
    get_all_ingredients,
    get_recipes_using_ingredient,
    get_last_n_days_sales,
    get_current_inventory,
    get_ingredient_unit,
    get_demo_config
)


def forecast_ingredient(sku: str, target_date: str, num_days: int = 7) -> IngredientForecast:
    """
    Forecast ingredient need for a given SKU on a target date.

    Algorithm:
    1. Get recipes using sku → compute ingredient qty per dish cover
    2. For each of 7 days: sum ingredient qty across all dishes (using that day's sales)
    3. Weighted average → base_daily_need
    4. Apply weekend multiplier (if applicable)
    5. Apply event multiplier (if upcoming events within 2 days)
    6. Apply +15% safety stock
    7. Subtract current inventory
    8. Return max(0.0, round(result, 1))
    """
    # Get historical sales data
    sales_data = get_last_n_days_sales(num_days, target_date)

    if not sales_data:
        # No historical data, return zero forecast
        return IngredientForecast(
            sku=sku,
            ingredient_name=_get_ingredient_name(sku),
            forecast_quantity=0.0,
            unit=get_ingredient_unit(sku),
            confidence=0.0,
            reasoning="No historical sales data available"
        )

    # Get recipes using this ingredient
    recipes = get_recipes_using_ingredient(sku)
    if not recipes:
        return IngredientForecast(
            sku=sku,
            ingredient_name=_get_ingredient_name(sku),
            forecast_quantity=0.0,
            unit=get_ingredient_unit(sku),
            confidence=0.0,
            reasoning="Ingredient not used in any recipe"
        )

    # Calculate weighted average of ingredient quantity across 7 days
    weights = [1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.4]
    weights_used = weights[-len(sales_data):]

    daily_quantities = []
    for sales_record in sales_data:
        daily_qty = 0.0
        # Sales records have a "sales" field with list of dishes
        for dish_sale in sales_record.get("sales", []):
            dish_id = dish_sale["dish_id"]
            covers = dish_sale["quantity"]

            # Find recipe matching this dish
            recipe = next((r for r in recipes if r["dish_id"] == dish_id), None)
            if recipe:
                # Find ingredient in recipe and get qty per cover
                for ing in recipe.get("ingredients", []):
                    if ing["sku"] == sku:
                        daily_qty += ing["quantity"] * covers
                        break

        daily_quantities.append(daily_qty)

    # Weighted average
    weighted_sum = sum(d * w for d, w in zip(daily_quantities, weights_used))
    denominator = sum(weights_used)
    base_daily_need = weighted_sum / denominator if denominator > 0 else 0.0

    # Apply multipliers
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")

    # Weekend multiplier (1.35x on Friday, Saturday, Sunday)
    weekday = target_dt.weekday()  # 0=Mon, 6=Sun
    weekend_multiplier = 1.35 if weekday >= 4 else 1.0

    # Event multiplier (check upcoming_events within 2 days)
    config = get_demo_config()
    event_multiplier = 1.0
    upcoming_events = config.get("upcoming_events", [])
    for event in upcoming_events:
        event_date = datetime.strptime(event["date"], "%Y-%m-%d")
        days_until = (event_date - target_dt).days
        if 0 <= days_until <= 2:
            event_multiplier *= event["multiplier"]

    # Safety stock (+15%)
    safety_multiplier = 1.15

    # Forecast with all multipliers
    forecast_qty = base_daily_need * weekend_multiplier * event_multiplier * safety_multiplier

    # Subtract current inventory
    current_inv = get_current_inventory(sku)
    final_qty = max(0.0, forecast_qty - current_inv)
    final_qty = round(final_qty, 1)

    confidence = 0.85 if len(daily_quantities) >= 5 else 0.70
    reasoning = (
        f"Based on {len(daily_quantities)}-day average. "
        f"Base need: {base_daily_need:.1f}kg. "
        f"Multipliers: weekend={weekend_multiplier}, event={event_multiplier}, safety=1.15. "
        f"Current inventory: {current_inv}kg."
    )

    return IngredientForecast(
        sku=sku,
        ingredient_name=_get_ingredient_name(sku),
        forecast_quantity=final_qty,
        unit=get_ingredient_unit(sku),
        confidence=confidence,
        reasoning=reasoning
    )


def forecast_all_ingredients(target_date: str) -> List[IngredientForecast]:
    """
    Forecast all ingredients for a given date.
    Returns only forecasts with quantity > 0.
    """
    all_ingredients = get_all_ingredients()
    forecasts = []

    for ingredient in all_ingredients:
        sku = ingredient["sku"]
        forecast = forecast_ingredient(sku, target_date)

        if forecast.forecast_quantity > 0:
            forecasts.append(forecast)

    return forecasts


def _get_ingredient_name(sku: str) -> str:
    """Get ingredient name from SKU."""
    ingredients = get_all_ingredients()
    for ing in ingredients:
        if ing["sku"] == sku:
            return ing["name"]
    return sku
