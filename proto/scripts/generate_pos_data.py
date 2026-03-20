#!/usr/bin/env python3
"""
Generate 30-day POS sales history for demonstration.
Outputs to data/pos_sales_history.json
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# Fix random seed for reproducibility
random.seed(42)

# Data directories
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR.parent / "data"

# Hardcoded rainy days
RAINY_DAYS = {"2026-02-18", "2026-03-05", "2026-03-12"}

# Dish popularity weights (must sum to 1.0)
DISH_WEIGHTS = {
    "D005": 0.20,  # Roti
    "D003": 0.18,  # Dal Makhani
    "D001": 0.15,  # Butter Chicken
    "D004": 0.12,  # Naan
    "D009": 0.08,  # Jeera Rice
    "D002": 0.06,  # Paneer Tikka
    "D007": 0.05,  # Chicken Biryani
    "D006": 0.04,  # Raita
    "D008": 0.02,  # Palak Paneer
    "D010": 0.02,  # Tandoori Chicken
    "D011": 0.02,  # Chole
    "D012": 0.02,  # Matar Paneer
    "D013": 0.02,  # Gulab Jamun
    "D014": 0.02,  # Masala Chai
}

# Load recipes for pricing
with open(DATA_DIR / "recipes.json", "r") as f:
    recipes_data = json.load(f)
    recipes = {r["dish_id"]: r for r in recipes_data["recipes"]}


def generate_pos_data():
    """Generate 30-day POS data from Feb 17 to Mar 18, 2026."""

    start_date = datetime(2026, 2, 17)
    end_date = datetime(2026, 3, 18)

    pos_records = []
    current_date = start_date

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        day_of_week = current_date.strftime("%A")

        # Determine weather and event
        weather = "rainy" if date_str in RAINY_DAYS else "sunny"
        is_event = False
        event_name = None

        if date_str == "2026-03-15":
            is_event = True
            event_name = "Holi"

        # Calculate covers
        base_covers = random.randint(80, 95)
        covers = base_covers

        # Weekend multiplier (Saturday=5, Sunday=6)
        if current_date.weekday() >= 5:
            covers = int(covers * 1.35)

        # Holi multiplier
        if is_event:
            covers = int(covers * 1.6)

        # Generate sales for each dish
        sales = []
        total_revenue = 0.0

        for dish_id, weight in DISH_WEIGHTS.items():
            dish = recipes[dish_id]

            # Base quantity from popularity weight
            qty = int(covers * weight)

            # Rain adjustments
            if weather == "rainy":
                if dish_id in ["D003", "D014"]:  # Dal Makhani, Masala Chai (hot)
                    qty = int(qty * 1.15)
                elif dish_id == "D006":  # Raita (light)
                    qty = int(qty * 0.95)

            # Add noise: +/-10%
            noise = random.uniform(0.9, 1.1)
            qty = max(1, int(qty * noise))

            # Calculate revenue
            revenue = qty * dish["avg_price"]

            sales.append({
                "dish_id": dish_id,
                "dish_name": dish["dish_name"],
                "quantity": qty,
                "revenue": int(revenue)
            })

            total_revenue += revenue

        # Create daily record
        record = {
            "date": date_str,
            "day_of_week": day_of_week,
            "weather": weather,
            "is_event": is_event,
            "event_name": event_name,
            "covers": covers,
            "sales": sales,
            "total_revenue": int(total_revenue)
        }

        pos_records.append(record)
        current_date += timedelta(days=1)

    # Write to file
    output_file = DATA_DIR / "pos_sales_history.json"
    with open(output_file, "w") as f:
        json.dump({"sales_history": pos_records}, f, indent=2)

    print(f"Generated {len(pos_records)} days of POS data to {output_file}")
    print(f"Date range: {start_date.date()} to {end_date.date()}")


if __name__ == "__main__":
    generate_pos_data()
