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


def get_vendor_by_id(vendor_id: str) -> dict:
    """Get vendor profile by ID."""
    vendor_data = _load_vendor_pricing()
    for vendor in vendor_data["vendors"]:
        if vendor["vendor_id"] == vendor_id:
            return vendor
    return None
