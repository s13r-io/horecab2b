#!/usr/bin/env python3
"""
AG-MVR: Multi-Vendor Routing Agent
Routes ingredients to optimal vendors based on effective cost (credit-adjusted)
with urgency-aware split ordering.
"""

from typing import List

from models.schemas import IngredientForecast, VendorOption, VendorAssignment
from utils.data_loader import (
    get_vendors_for_sku,
    get_current_price,
    get_vendor_by_id,
    get_moq_for_vendor_sku,
    get_current_inventory,
    get_adjusted_daily_consumption,
    get_demo_config,
    compute_effective_lead_days,
    get_ingredient_unit
)

# 0.1% per day (~36% annual) — reflects working capital cost for small restaurants
DAILY_CAPITAL_COST = 0.001


def route_ingredient(sku: str, quantity: float, target_date: str) -> List[VendorOption]:
    """
    Find optimal vendor(s) for a given ingredient.

    Score = effective_cost = total_cost * (1 - credit_days * DAILY_CAPITAL_COST)
    Lower effective_cost is better.
    Tiebreaker: higher reliability_score wins.
    Mark lowest-score option as is_recommended=True.
    """
    vendors = get_vendors_for_sku(sku, target_date)

    if not vendors:
        return []

    config = get_demo_config()
    current_time = config.get("current_time", "12:00")

    options = []
    for vendor in vendors:
        try:
            price_per_unit = get_current_price(vendor["vendor_id"], sku, target_date)
        except ValueError:
            continue

        moq = get_moq_for_vendor_sku(vendor["vendor_id"], sku)
        order_quantity = max(quantity, moq)
        total_cost = price_per_unit * order_quantity
        reliability_score = vendor.get("reliability_score", 0.9)
        credit_days = vendor.get("credit_days", 0)
        eff_lead = compute_effective_lead_days(vendor, current_time)

        # Credit-adjusted effective cost (lower is better)
        effective_cost = total_cost * (1 - credit_days * DAILY_CAPITAL_COST)

        option = VendorOption(
            vendor_id=vendor["vendor_id"],
            vendor_name=vendor["vendor_name"],
            price_per_unit=price_per_unit,
            total_cost=round(total_cost, 2),
            reliability_score=reliability_score,
            score=round(effective_cost, 2),
            delivery_time=vendor.get("delivery_time", "24h"),
            credit_days=credit_days,
            is_recommended=False,
            moq=moq,
            order_quantity=round(order_quantity, 1),
            effective_lead_days=eff_lead
        )
        options.append(option)

    # Sort by effective_cost (lower wins), tiebreak by reliability (higher wins)
    options.sort(key=lambda x: (x.score, -x.reliability_score))

    # Mark lowest-score option as recommended
    if options:
        options[0].is_recommended = True

    return options


def route_ingredient_with_split(
    sku: str,
    forecast_qty: float,
    target_date: str
) -> dict:
    """
    Route an ingredient with urgency-aware split ordering.

    Returns dict with:
      - options: List[VendorOption] (all vendor options, scored)
      - is_split: bool
      - bridge: {vendor_option, qty} or None
      - main: {vendor_option, qty}
      - reason: str
    """
    options = route_ingredient(sku, forecast_qty, target_date)

    if not options or forecast_qty <= 0:
        return {
            "options": options,
            "is_split": False,
            "bridge": None,
            "main": {"vendor_option": options[0] if options else None, "qty": forecast_qty},
            "reason": "No split needed" if options else "No vendors available"
        }

    preferred = options[0]  # best effective cost

    # Get stock and daily consumption for urgency check
    current_stock = get_current_inventory(sku)
    daily = get_adjusted_daily_consumption(sku, target_date)

    if daily <= 0:
        return {
            "options": options,
            "is_split": False,
            "bridge": None,
            "main": {"vendor_option": preferred, "qty": preferred.order_quantity},
            "reason": "No consumption data; single order to best vendor"
        }

    days_of_stock = current_stock / daily
    preferred_lead = preferred.effective_lead_days

    # Can we wait for preferred vendor?
    if days_of_stock >= preferred_lead:
        return {
            "options": options,
            "is_split": False,
            "bridge": None,
            "main": {"vendor_option": preferred, "qty": preferred.order_quantity},
            "reason": f"Stock covers {days_of_stock:.1f}d >= {preferred_lead}d lead; single order"
        }

    # Need faster vendor — find one with lowest lead time
    fastest = min(options, key=lambda x: x.effective_lead_days)

    if fastest.vendor_id == preferred.vendor_id or fastest.effective_lead_days >= preferred_lead:
        return {
            "options": options,
            "is_split": False,
            "bridge": None,
            "main": {"vendor_option": preferred, "qty": preferred.order_quantity},
            "reason": f"Stock low ({days_of_stock:.1f}d) but no faster vendor; single order"
        }

    # SPLIT ORDER
    fast_lead = fastest.effective_lead_days

    # Stock remaining when bridge order arrives
    stock_at_bridge = max(0, current_stock - daily * fast_lead)

    # Bridge covers gap from bridge delivery to preferred delivery, minus leftover stock
    bridge_qty_raw = daily * (preferred_lead - fast_lead) - stock_at_bridge

    if bridge_qty_raw <= 0:
        # Existing stock covers the gap — no bridge needed
        return {
            "options": options,
            "is_split": False,
            "bridge": None,
            "main": {"vendor_option": preferred, "qty": preferred.order_quantity},
            "reason": f"Stock at bridge delivery ({stock_at_bridge:.1f}) covers gap; single order"
        }

    # Apply bridge vendor MOQ
    bridge_moq = get_moq_for_vendor_sku(fastest.vendor_id, sku)
    bridge_qty = round(max(bridge_qty_raw, bridge_moq), 1)

    # Main order = forecast - bridge (user's requirement: deduct, don't duplicate)
    main_qty = forecast_qty - bridge_qty

    if main_qty <= 0:
        # Bridge alone covers everything (high MOQ scenario)
        # Re-price bridge at actual quantity
        bridge_options = route_ingredient(sku, bridge_qty, target_date)
        bridge_opt = next(
            (o for o in bridge_options if o.vendor_id == fastest.vendor_id), fastest
        )
        return {
            "options": options,
            "is_split": False,
            "bridge": None,
            "main": {"vendor_option": bridge_opt, "qty": bridge_qty},
            "reason": (
                f"Bridge MOQ ({bridge_moq}) covers full forecast; "
                f"single order to {fastest.vendor_name}"
            )
        }

    # Apply preferred vendor MOQ to main order
    preferred_moq = get_moq_for_vendor_sku(preferred.vendor_id, sku)
    main_qty = round(max(main_qty, preferred_moq), 1)

    # If MOQ inflation causes total to exceed the requested quantity, fall back to
    # single-vendor order at forecast_qty (respects user intent, avoids over-ordering)
    if bridge_qty + main_qty > forecast_qty:
        single_qty = round(max(forecast_qty, preferred_moq), 1)
        single_options = route_ingredient(sku, single_qty, target_date)
        single_opt = next(
            (o for o in single_options if o.vendor_id == preferred.vendor_id), preferred
        )
        return {
            "options": options,
            "is_split": False,
            "bridge": None,
            "main": {"vendor_option": single_opt, "qty": single_qty},
            "reason": (
                f"Split MOQ inflation ({bridge_qty}+{main_qty}>{forecast_qty}); "
                f"single order to {preferred.vendor_name}"
            )
        }

    # Re-price both at actual quantities
    bridge_options = route_ingredient(sku, bridge_qty, target_date)
    bridge_opt = next(
        (o for o in bridge_options if o.vendor_id == fastest.vendor_id), fastest
    )

    main_options = route_ingredient(sku, main_qty, target_date)
    main_opt = next(
        (o for o in main_options if o.vendor_id == preferred.vendor_id), preferred
    )

    unit = get_ingredient_unit(sku)
    return {
        "options": options,
        "is_split": True,
        "bridge": {"vendor_option": bridge_opt, "qty": bridge_qty},
        "main": {"vendor_option": main_opt, "qty": main_qty},
        "reason": (
            f"Stock: {days_of_stock:.1f}d < preferred lead {preferred_lead}d. "
            f"Bridge: {bridge_qty} {unit} from {fastest.vendor_name} "
            f"(delivers in {fast_lead}d). "
            f"Main: {main_qty} {unit} from {preferred.vendor_name} "
            f"(delivers in {preferred_lead}d)."
        )
    }


def route_order(forecasts: List[IngredientForecast], target_date: str) -> List[VendorAssignment]:
    """
    Route all forecasted ingredients to vendors.
    Uses urgency-aware split ordering when needed.
    Groups ingredients by vendor.

    Returns one VendorAssignment per unique vendor (separate for bridge vs main).
    """
    vendor_assignments = {}  # key -> assignment dict

    for forecast in forecasts:
        split_result = route_ingredient_with_split(
            forecast.sku, forecast.forecast_quantity, target_date
        )

        if split_result["is_split"]:
            # Bridge order
            bridge = split_result["bridge"]
            bv = bridge["vendor_option"]
            _add_to_assignments(
                vendor_assignments, bv, forecast,
                bridge["qty"], is_bridge=True
            )

            # Main order
            main = split_result["main"]
            mv = main["vendor_option"]
            _add_to_assignments(
                vendor_assignments, mv, forecast,
                main["qty"], is_bridge=False
            )
        else:
            # Single order
            main = split_result["main"]
            if main and main["vendor_option"]:
                mv = main["vendor_option"]
                _add_to_assignments(
                    vendor_assignments, mv, forecast,
                    main["qty"], is_bridge=False
                )

    # Convert to VendorAssignment objects
    assignments = []
    for key, ad in vendor_assignments.items():
        assignment = VendorAssignment(
            vendor_id=ad["vendor_id"],
            vendor_name=ad["vendor_name"],
            items=ad["items"],
            estimated_cost=round(ad["total_cost"], 2),
            routing_reason=ad["routing_reason"],
            is_bridge_order=ad["is_bridge"]
        )
        assignments.append(assignment)

    return assignments


def _add_to_assignments(vendor_assignments, vendor_opt, forecast, qty, is_bridge):
    """Helper to add an item to vendor assignment grouping."""
    vendor_id = vendor_opt.vendor_id
    # Separate keys for bridge vs main (same vendor could appear in both)
    key = f"{vendor_id}_bridge" if is_bridge else vendor_id

    if key not in vendor_assignments:
        vendor_assignments[key] = {
            "vendor_id": vendor_id,
            "vendor_name": vendor_opt.vendor_name,
            "items": [],
            "total_cost": 0.0,
            "is_bridge": is_bridge,
            "routing_reason": "Urgency bridge order" if is_bridge else "Best effective cost"
        }

    item_cost = vendor_opt.price_per_unit * qty
    vendor_assignments[key]["items"].append({
        "sku": forecast.sku,
        "ingredient_name": forecast.ingredient_name,
        "quantity": round(qty, 1),
        "unit": forecast.unit,
        "price_per_unit": vendor_opt.price_per_unit,
        "item_cost": round(item_cost, 2),
        "is_bridge": is_bridge
    })
    vendor_assignments[key]["total_cost"] += item_cost
