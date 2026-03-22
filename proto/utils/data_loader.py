#!/usr/bin/env python3
"""
Data loader utility with caching for all JSON data files.
Central hub for data access across all agents.
"""

import json
from functools import lru_cache
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"


# ============================================================================
# Raw file loaders (with @lru_cache)
# ============================================================================

@lru_cache(maxsize=1)
def _load_ingredients():
    """Load ingredients.json"""
    with open(DATA_DIR / "ingredients.json", "r") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_recipes():
    """Load recipes.json"""
    with open(DATA_DIR / "recipes.json", "r") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_vendor_pricing():
    """Load vendor_pricing_history.json"""
    with open(DATA_DIR / "vendor_pricing_history.json", "r") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_pos_history():
    """Load pos_sales_history.json"""
    with open(DATA_DIR / "pos_sales_history.json", "r") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_inventory():
    """Load current_inventory.json"""
    with open(DATA_DIR / "current_inventory.json", "r") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_demo_config():
    """Load demo_config.json"""
    with open(DATA_DIR / "demo_config.json", "r") as f:
        return json.load(f)


# ============================================================================
# Helper query functions
# ============================================================================

def get_recipes_using_ingredient(sku: str) -> list:
    """Get all recipe dicts that use a given SKU."""
    recipes_data = _load_recipes()
    matching = []
    for recipe in recipes_data["recipes"]:
        for ingredient in recipe.get("ingredients", []):
            if ingredient["sku"] == sku:
                matching.append(recipe)
                break
    return matching


def get_vendors_for_sku(sku: str, date: str) -> list:
    """Get vendors that stock a given SKU on a given date."""
    # Find nearest past pricing snapshot
    vendor_data = _load_vendor_pricing()
    snapshots = vendor_data["pricing_history"]

    target_date = datetime.strptime(date, "%Y-%m-%d")
    nearest_snapshot = None

    for snapshot in snapshots:
        snapshot_date = datetime.strptime(snapshot["snapshot_date"], "%Y-%m-%d")
        if snapshot_date <= target_date:
            nearest_snapshot = snapshot
        else:
            break

    # If no past snapshot found, use earliest
    if nearest_snapshot is None:
        nearest_snapshot = snapshots[0]

    # Find vendors that have this SKU in the nearest snapshot
    matching_vendors = []
    for price_entry in nearest_snapshot["prices"]:
        if sku in price_entry.get("items", {}):
            # Get full vendor profile from vendors list
            vendor_id = price_entry["vendor_id"]
            vendor = next(
                (v for v in vendor_data["vendors"] if v["vendor_id"] == vendor_id),
                None
            )
            if vendor:
                matching_vendors.append(vendor)

    return matching_vendors


def get_current_price(vendor_id: str, sku: str, date: str) -> float:
    """Get current price of SKU from a vendor on a given date."""
    vendor_data = _load_vendor_pricing()
    snapshots = vendor_data["pricing_history"]

    target_date = datetime.strptime(date, "%Y-%m-%d")
    nearest_snapshot = None

    for snapshot in snapshots:
        snapshot_date = datetime.strptime(snapshot["snapshot_date"], "%Y-%m-%d")
        if snapshot_date <= target_date:
            nearest_snapshot = snapshot
        else:
            break

    if nearest_snapshot is None:
        nearest_snapshot = snapshots[0]

    # Find price
    for price_entry in nearest_snapshot["prices"]:
        if price_entry["vendor_id"] == vendor_id:
            if sku in price_entry.get("items", {}):
                return price_entry["items"][sku]

    raise ValueError(f"Price not found for vendor {vendor_id}, SKU {sku} on {date}")


def get_last_n_days_sales(n: int, before_date: str) -> list:
    """Get last N days of sales before target date."""
    pos_data = _load_pos_history()
    sales_records = pos_data["sales_history"]

    target_date = datetime.strptime(before_date, "%Y-%m-%d")

    # Filter records before target_date, sort by date ascending
    filtered = [
        r for r in sales_records
        if datetime.strptime(r["date"], "%Y-%m-%d") < target_date
    ]
    filtered.sort(key=lambda r: r["date"])

    # Return last N
    return filtered[-n:] if len(filtered) >= n else filtered


def get_current_inventory(sku: str) -> float:
    """Get current quantity on hand for a SKU."""
    inv_data = _load_inventory()
    for item in inv_data.get("inventory", []):
        if item["sku"] == sku:
            return item["quantity_on_hand"]
    return 0.0


def get_ingredient_unit(sku: str) -> str:
    """Get unit for an ingredient."""
    ing_data = _load_ingredients()
    for ing in ing_data.get("ingredients", []):
        if ing["sku"] == sku:
            return ing["unit"]
    return "kg"  # fallback


def get_demo_config() -> dict:
    """Get demo configuration."""
    return _load_demo_config()


def get_all_ingredients() -> list:
    """Get all ingredient SKUs."""
    ing_data = _load_ingredients()
    return ing_data.get("ingredients", [])


def get_all_recipes() -> list:
    """Get all recipes."""
    recipe_data = _load_recipes()
    return recipe_data.get("recipes", [])


def get_all_inventory() -> list:
    """Get full inventory snapshot."""
    inv_data = _load_inventory()
    return inv_data.get("inventory", [])


def compute_effective_lead_days(vendor: dict, current_time: str) -> int:
    """
    Compute effective lead time in days based on order cutoff time.
    If current_time is before cutoff -> delivery in delivery_days.
    If current_time is at or after cutoff -> delivery in delivery_days + 1.
    """
    cutoff = vendor.get("order_cutoff_time", "16:00")
    base_days = vendor.get("delivery_days", 1)
    if current_time >= cutoff:
        return base_days + 1
    return base_days


def get_latest_price_for_vendor_sku(vendor_id: str, sku: str) -> float:
    """Latest price from most recent snapshot for a vendor+SKU pair."""
    vendor_data = _load_vendor_pricing()
    for snapshot in reversed(vendor_data["pricing_history"]):
        for entry in snapshot["prices"]:
            if entry["vendor_id"] == vendor_id and sku in entry.get("items", {}):
                return entry["items"][sku]
    return None


def get_avg_price_for_vendor_sku(vendor_id: str, sku: str) -> float:
    """Average price across all pricing snapshots for a vendor+SKU pair."""
    vendor_data = _load_vendor_pricing()
    prices = []
    for snapshot in vendor_data["pricing_history"]:
        for entry in snapshot["prices"]:
            if entry["vendor_id"] == vendor_id and sku in entry.get("items", {}):
                prices.append(entry["items"][sku])
    return round(sum(prices) / len(prices), 1) if prices else None


def get_moq_for_vendor_sku(vendor_id: str, sku: str) -> float:
    """Min order qty for a vendor-SKU pair. Returns 0 if none set."""
    vendor_data = _load_vendor_pricing()
    for vendor in vendor_data["vendors"]:
        if vendor["vendor_id"] == vendor_id:
            return vendor.get("min_order_qty", {}).get(sku, 0.0)
    return 0.0


def get_adjusted_daily_consumption(sku: str, target_date: str) -> float:
    """
    Compute adjusted daily consumption for a SKU on target_date.
    Uses weighted 7-day average of POS data, adjusted for weekend/event multipliers.
    Same algorithm as forecasting agent and inventory dashboard.
    Returns 0.0 if no data available.
    """
    sales_data = get_last_n_days_sales(7, target_date)
    if not sales_data:
        return 0.0

    recipes = get_recipes_using_ingredient(sku)
    if not recipes:
        return 0.0

    weights = [1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.4]
    weights_used = weights[-len(sales_data):]

    daily_quantities = []
    for sales_record in sales_data:
        daily_qty = 0.0
        for dish_sale in sales_record.get("sales", []):
            dish_id = dish_sale["dish_id"]
            covers = dish_sale["quantity"]
            recipe = next((r for r in recipes if r["dish_id"] == dish_id), None)
            if recipe:
                for ing in recipe.get("ingredients", []):
                    if ing["sku"] == sku:
                        daily_qty += ing["quantity"] * covers
                        break
        daily_quantities.append(daily_qty)

    weighted_sum = sum(d * w for d, w in zip(daily_quantities, weights_used))
    denominator = sum(weights_used)
    base_daily = weighted_sum / denominator if denominator > 0 else 0.0

    # Apply multipliers
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    weekday = target_dt.weekday()
    weekend_multiplier = 1.35 if weekday >= 4 else 1.0

    config = get_demo_config()
    event_multiplier = 1.0
    for event in config.get("upcoming_events", []):
        event_date = datetime.strptime(event["date"], "%Y-%m-%d")
        days_until = (event_date - target_dt).days
        if 0 <= days_until <= 2:
            event_multiplier *= event.get("demand_multiplier", event.get("multiplier", 1.0))

    return round(base_daily * weekend_multiplier * event_multiplier, 2)


def get_vendor_by_id(vendor_id: str) -> dict:
    """Get vendor profile by ID."""
    vendor_data = _load_vendor_pricing()
    for vendor in vendor_data["vendors"]:
        if vendor["vendor_id"] == vendor_id:
            return vendor
    return None
