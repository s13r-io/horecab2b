#!/usr/bin/env python3
"""
AG-MVR: Multi-Vendor Routing Agent
Routes ingredients to optimal vendors based on cost and reliability.
"""

from typing import List

from models.schemas import IngredientForecast, VendorOption, VendorAssignment
from utils.data_loader import (
    get_vendors_for_sku,
    get_current_price,
    get_vendor_by_id
)


def route_ingredient(sku: str, quantity: float, target_date: str) -> List[VendorOption]:
    """
    Find optimal vendor(s) for a given ingredient.

    Score = total_cost / reliability_score (lower is better).
    Tiebreaker: higher credit_days wins.
    Mark lowest-score option as is_recommended=True.
    """
    vendors = get_vendors_for_sku(sku, target_date)

    if not vendors:
        return []

    options = []
    for vendor in vendors:
        try:
            price_per_unit = get_current_price(vendor["vendor_id"], sku, target_date)
        except ValueError:
            continue

        total_cost = price_per_unit * quantity
        reliability_score = vendor.get("reliability_score", 0.9)
        score = total_cost / reliability_score if reliability_score > 0 else float('inf')

        option = VendorOption(
            vendor_id=vendor["vendor_id"],
            vendor_name=vendor["vendor_name"],
            price_per_unit=price_per_unit,
            total_cost=round(total_cost, 2),
            reliability_score=reliability_score,
            score=round(score, 2),
            delivery_time=vendor.get("delivery_time", "24h"),
            credit_days=vendor.get("credit_days", 0),
            is_recommended=False
        )
        options.append(option)

    # Sort by score (lower is better), then by credit_days (higher is better)
    options.sort(key=lambda x: (x.score, -x.credit_days))

    # Mark lowest-score option as recommended
    if options:
        options[0].is_recommended = True

    return options


def route_order(forecasts: List[IngredientForecast], target_date: str) -> List[VendorAssignment]:
    """
    Route all forecasted ingredients to vendors.
    Groups ingredients by recommended vendor.

    Returns one VendorAssignment per unique vendor.
    """
    vendor_assignments = {}  # vendor_id -> VendorAssignment dict

    for forecast in forecasts:
        options = route_ingredient(forecast.sku, forecast.forecast_quantity, target_date)

        # Find recommended option
        recommended = next((o for o in options if o.is_recommended), None)
        if not recommended and options:
            recommended = options[0]

        if not recommended:
            continue

        vendor_id = recommended.vendor_id
        if vendor_id not in vendor_assignments:
            vendor = get_vendor_by_id(vendor_id)
            vendor_assignments[vendor_id] = {
                "vendor_id": vendor_id,
                "vendor_name": recommended.vendor_name,
                "items": [],
                "total_cost": 0.0
            }

        # Add item to this vendor's assignment
        vendor_assignments[vendor_id]["items"].append({
            "sku": forecast.sku,
            "ingredient_name": forecast.ingredient_name,
            "quantity": forecast.forecast_quantity,
            "unit": forecast.unit,
            "price_per_unit": recommended.price_per_unit,
            "item_cost": recommended.total_cost
        })
        vendor_assignments[vendor_id]["total_cost"] += recommended.total_cost

    # Convert to VendorAssignment objects
    assignments = []
    for vendor_id, assignment_dict in vendor_assignments.items():
        assignment = VendorAssignment(
            vendor_id=assignment_dict["vendor_id"],
            vendor_name=assignment_dict["vendor_name"],
            items=assignment_dict["items"],
            estimated_cost=round(assignment_dict["total_cost"], 2),
            routing_reason="Lowest cost/reliability score"
        )
        assignments.append(assignment)

    return assignments
