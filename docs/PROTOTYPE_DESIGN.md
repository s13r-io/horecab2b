# NAM Agentic Procurement Platform — MVP Prototype Design Doc

**Last Updated:** March 20, 2026
**Scope:** 30% of full platform (demonstrating core concepts for CEO)
**Timeline:** 7-10 days, solo developer (includes Railway deployment for remote demo access)
**Target Audience:** Executive demo (CEO/CTO)

---

## 1. Executive Summary

This document defines the **MVP prototype** that demonstrates the core value proposition of NAM's agentic procurement platform for restaurants.

### What This Prototype Demonstrates

| Phase | Solution | Agent(s) | What's Shown | CEO Value |
|---|---|---|---|---|
| **Foundation** | POS Data Layer (S-46) | Data ingestion | Recipe-to-ingredient mapping + mock POS sales | "We have the data layer" |
| **Phase 1** | Pre-Dawn Smart Order Suggestion (S-02) | AG-DPF | AI predicts daily needs using POS data | "AI makes better decisions than humans" |
| **Phase 1** | Vendor WhatsApp Automation (S-11) | AG-DSP | Auto-formats orders for vendor preferences | "Eliminates manual coordination overhead" |
| **Bonus** | Vendor Routing (Implicit in S-03) | AG-MVR | Picks best vendor based on price/reliability | "Optimizes across fragmented vendors" |

### What This Prototype Does NOT Include

- Real vendor API integrations
- JFSL credit processing
- Full demand forecasting ML model (simplified version)
- Multi-language NLP (mocked with Claude API)
- Vendor scorecards at scale
- Production-grade auth/compliance

---

## 2. Data Model (Core Foundation)

### 2.0 Restaurant Profile

**File:** `data/restaurant_profile.json`
**Purpose:** Define the restaurant being demoed. Single restaurant for MVP.

```json
{
  "restaurant_id": "R001",
  "name": "Spice Junction",
  "cuisine": "North Indian",
  "location": "Mumbai, Andheri West",
  "avg_daily_covers": 100,
  "operating_hours": "11:00-23:00",
  "owner_name": "Raj Patel",
  "contact": "+91-9800000001"
}
```

---

### 2.1 Ingredient Master Catalog

**File:** `data/ingredients.json`
**Purpose:** Define all ingredient SKUs, units, categories, shelf-life (metadata only, NO pricing)

```json
{
  "ingredients": [
    {
      "sku": "tomato",
      "name": "Tomatoes (Fresh)",
      "unit": "kg",
      "category": "Vegetables",
      "shelf_life_days": 5,
      "perishable": true
    },
    {
      "sku": "onion",
      "name": "Onions",
      "unit": "kg",
      "category": "Vegetables",
      "shelf_life_days": 15,
      "perishable": false
    },
    {
      "sku": "chicken_breast",
      "name": "Chicken Breast (Fresh)",
      "unit": "kg",
      "category": "Meat",
      "shelf_life_days": 2,
      "perishable": true
    },
    {
      "sku": "paneer",
      "name": "Paneer",
      "unit": "kg",
      "category": "Dairy",
      "shelf_life_days": 7,
      "perishable": true
    },
    {
      "sku": "butter",
      "name": "Butter (Unsalted)",
      "unit": "kg",
      "category": "Dairy",
      "shelf_life_days": 30,
      "perishable": false
    },
    {
      "sku": "cream",
      "name": "Cream (Fresh)",
      "unit": "kg",
      "category": "Dairy",
      "shelf_life_days": 5,
      "perishable": true
    },
    {
      "sku": "black_lentils",
      "name": "Black Lentils (Urad)",
      "unit": "kg",
      "category": "Dry Goods",
      "shelf_life_days": 180,
      "perishable": false
    },
    {
      "sku": "red_lentils",
      "name": "Red Lentils (Masoor)",
      "unit": "kg",
      "category": "Dry Goods",
      "shelf_life_days": 180,
      "perishable": false
    },
    {
      "sku": "ginger_garlic",
      "name": "Ginger-Garlic Paste",
      "unit": "kg",
      "category": "Condiments",
      "shelf_life_days": 10,
      "perishable": true
    },
    {
      "sku": "yogurt",
      "name": "Yogurt (Plain)",
      "unit": "kg",
      "category": "Dairy",
      "shelf_life_days": 3,
      "perishable": true
    },
    {
      "sku": "wheat_flour",
      "name": "Wheat Flour (Atta)",
      "unit": "kg",
      "category": "Dry Goods",
      "shelf_life_days": 90,
      "perishable": false
    },
    {
      "sku": "rice_basmati",
      "name": "Basmati Rice",
      "unit": "kg",
      "category": "Dry Goods",
      "shelf_life_days": 180,
      "perishable": false
    },
    {
      "sku": "cooking_oil",
      "name": "Cooking Oil (Sunflower)",
      "unit": "litre",
      "category": "Dry Goods",
      "shelf_life_days": 120,
      "perishable": false
    },
    {
      "sku": "salt",
      "name": "Salt (Iodized)",
      "unit": "kg",
      "category": "Dry Goods",
      "shelf_life_days": 365,
      "perishable": false
    },
    {
      "sku": "cumin_powder",
      "name": "Cumin Powder",
      "unit": "kg",
      "category": "Spices",
      "shelf_life_days": 180,
      "perishable": false
    },
    {
      "sku": "turmeric_powder",
      "name": "Turmeric Powder",
      "unit": "kg",
      "category": "Spices",
      "shelf_life_days": 180,
      "perishable": false
    },
    {
      "sku": "red_chili_powder",
      "name": "Red Chili Powder",
      "unit": "kg",
      "category": "Spices",
      "shelf_life_days": 180,
      "perishable": false
    },
    {
      "sku": "garam_masala",
      "name": "Garam Masala",
      "unit": "kg",
      "category": "Spices",
      "shelf_life_days": 120,
      "perishable": false
    },
    {
      "sku": "coriander_leaves",
      "name": "Coriander Leaves (Fresh)",
      "unit": "kg",
      "category": "Vegetables",
      "shelf_life_days": 3,
      "perishable": true
    },
    {
      "sku": "green_chili",
      "name": "Green Chili",
      "unit": "kg",
      "category": "Vegetables",
      "shelf_life_days": 5,
      "perishable": true
    }
  ]
}
```

---

### 2.2 Recipe-to-Ingredient Mapping

**File:** `data/recipes.json`
**Purpose:** Define dishes and their ingredient requirements (quantities per serving)

```json
{
  "recipes": [
    {
      "dish_id": "D001",
      "dish_name": "Butter Chicken",
      "category": "Main Course",
      "avg_price": 225,
      "ingredients": [
        {"sku": "chicken_breast", "quantity": 0.4, "unit": "kg"},
        {"sku": "butter", "quantity": 0.05, "unit": "kg"},
        {"sku": "tomato", "quantity": 0.15, "unit": "kg"},
        {"sku": "onion", "quantity": 0.1, "unit": "kg"},
        {"sku": "cream", "quantity": 0.08, "unit": "kg"},
        {"sku": "ginger_garlic", "quantity": 0.02, "unit": "kg"},
        {"sku": "red_chili_powder", "quantity": 0.005, "unit": "kg"},
        {"sku": "garam_masala", "quantity": 0.003, "unit": "kg"},
        {"sku": "salt", "quantity": 0.005, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D002",
      "dish_name": "Paneer Tikka",
      "category": "Appetizer",
      "avg_price": 200,
      "ingredients": [
        {"sku": "paneer", "quantity": 0.2, "unit": "kg"},
        {"sku": "yogurt", "quantity": 0.1, "unit": "kg"},
        {"sku": "tomato", "quantity": 0.1, "unit": "kg"},
        {"sku": "onion", "quantity": 0.15, "unit": "kg"},
        {"sku": "ginger_garlic", "quantity": 0.015, "unit": "kg"},
        {"sku": "red_chili_powder", "quantity": 0.003, "unit": "kg"},
        {"sku": "cumin_powder", "quantity": 0.002, "unit": "kg"},
        {"sku": "cooking_oil", "quantity": 0.02, "unit": "litre"}
      ]
    },
    {
      "dish_id": "D003",
      "dish_name": "Dal Makhani",
      "category": "Main Course",
      "avg_price": 140,
      "ingredients": [
        {"sku": "black_lentils", "quantity": 0.1, "unit": "kg"},
        {"sku": "red_lentils", "quantity": 0.05, "unit": "kg"},
        {"sku": "butter", "quantity": 0.03, "unit": "kg"},
        {"sku": "cream", "quantity": 0.1, "unit": "kg"},
        {"sku": "onion", "quantity": 0.1, "unit": "kg"},
        {"sku": "ginger_garlic", "quantity": 0.02, "unit": "kg"},
        {"sku": "tomato", "quantity": 0.08, "unit": "kg"},
        {"sku": "cumin_powder", "quantity": 0.003, "unit": "kg"},
        {"sku": "salt", "quantity": 0.005, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D004",
      "dish_name": "Naan",
      "category": "Bread",
      "avg_price": 40,
      "ingredients": [
        {"sku": "wheat_flour", "quantity": 0.08, "unit": "kg"},
        {"sku": "yogurt", "quantity": 0.02, "unit": "kg"},
        {"sku": "butter", "quantity": 0.01, "unit": "kg"},
        {"sku": "salt", "quantity": 0.002, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D005",
      "dish_name": "Roti",
      "category": "Bread",
      "avg_price": 20,
      "ingredients": [
        {"sku": "wheat_flour", "quantity": 0.06, "unit": "kg"},
        {"sku": "cooking_oil", "quantity": 0.005, "unit": "litre"},
        {"sku": "salt", "quantity": 0.001, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D006",
      "dish_name": "Raita",
      "category": "Side",
      "avg_price": 50,
      "ingredients": [
        {"sku": "yogurt", "quantity": 0.2, "unit": "kg"},
        {"sku": "onion", "quantity": 0.05, "unit": "kg"},
        {"sku": "cumin_powder", "quantity": 0.002, "unit": "kg"},
        {"sku": "salt", "quantity": 0.002, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D007",
      "dish_name": "Chicken Biryani",
      "category": "Main Course",
      "avg_price": 250,
      "ingredients": [
        {"sku": "chicken_breast", "quantity": 0.35, "unit": "kg"},
        {"sku": "rice_basmati", "quantity": 0.2, "unit": "kg"},
        {"sku": "onion", "quantity": 0.15, "unit": "kg"},
        {"sku": "yogurt", "quantity": 0.05, "unit": "kg"},
        {"sku": "ginger_garlic", "quantity": 0.02, "unit": "kg"},
        {"sku": "cooking_oil", "quantity": 0.03, "unit": "litre"},
        {"sku": "garam_masala", "quantity": 0.005, "unit": "kg"},
        {"sku": "turmeric_powder", "quantity": 0.002, "unit": "kg"},
        {"sku": "green_chili", "quantity": 0.01, "unit": "kg"},
        {"sku": "coriander_leaves", "quantity": 0.01, "unit": "kg"},
        {"sku": "salt", "quantity": 0.005, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D008",
      "dish_name": "Palak Paneer",
      "category": "Main Course",
      "avg_price": 180,
      "ingredients": [
        {"sku": "paneer", "quantity": 0.2, "unit": "kg"},
        {"sku": "onion", "quantity": 0.08, "unit": "kg"},
        {"sku": "tomato", "quantity": 0.08, "unit": "kg"},
        {"sku": "ginger_garlic", "quantity": 0.015, "unit": "kg"},
        {"sku": "green_chili", "quantity": 0.01, "unit": "kg"},
        {"sku": "cumin_powder", "quantity": 0.003, "unit": "kg"},
        {"sku": "garam_masala", "quantity": 0.002, "unit": "kg"},
        {"sku": "cooking_oil", "quantity": 0.02, "unit": "litre"},
        {"sku": "salt", "quantity": 0.003, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D009",
      "dish_name": "Jeera Rice",
      "category": "Rice",
      "avg_price": 100,
      "ingredients": [
        {"sku": "rice_basmati", "quantity": 0.15, "unit": "kg"},
        {"sku": "cumin_powder", "quantity": 0.005, "unit": "kg"},
        {"sku": "cooking_oil", "quantity": 0.01, "unit": "litre"},
        {"sku": "salt", "quantity": 0.003, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D010",
      "dish_name": "Tandoori Chicken",
      "category": "Appetizer",
      "avg_price": 260,
      "ingredients": [
        {"sku": "chicken_breast", "quantity": 0.5, "unit": "kg"},
        {"sku": "yogurt", "quantity": 0.08, "unit": "kg"},
        {"sku": "ginger_garlic", "quantity": 0.02, "unit": "kg"},
        {"sku": "red_chili_powder", "quantity": 0.005, "unit": "kg"},
        {"sku": "turmeric_powder", "quantity": 0.003, "unit": "kg"},
        {"sku": "cooking_oil", "quantity": 0.02, "unit": "litre"},
        {"sku": "salt", "quantity": 0.005, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D011",
      "dish_name": "Chole",
      "category": "Main Course",
      "avg_price": 130,
      "ingredients": [
        {"sku": "onion", "quantity": 0.12, "unit": "kg"},
        {"sku": "tomato", "quantity": 0.1, "unit": "kg"},
        {"sku": "ginger_garlic", "quantity": 0.015, "unit": "kg"},
        {"sku": "green_chili", "quantity": 0.01, "unit": "kg"},
        {"sku": "cumin_powder", "quantity": 0.005, "unit": "kg"},
        {"sku": "turmeric_powder", "quantity": 0.002, "unit": "kg"},
        {"sku": "red_chili_powder", "quantity": 0.003, "unit": "kg"},
        {"sku": "garam_masala", "quantity": 0.003, "unit": "kg"},
        {"sku": "cooking_oil", "quantity": 0.02, "unit": "litre"},
        {"sku": "coriander_leaves", "quantity": 0.01, "unit": "kg"},
        {"sku": "salt", "quantity": 0.005, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D012",
      "dish_name": "Matar Paneer",
      "category": "Main Course",
      "avg_price": 170,
      "ingredients": [
        {"sku": "paneer", "quantity": 0.18, "unit": "kg"},
        {"sku": "tomato", "quantity": 0.1, "unit": "kg"},
        {"sku": "onion", "quantity": 0.1, "unit": "kg"},
        {"sku": "ginger_garlic", "quantity": 0.015, "unit": "kg"},
        {"sku": "green_chili", "quantity": 0.008, "unit": "kg"},
        {"sku": "turmeric_powder", "quantity": 0.002, "unit": "kg"},
        {"sku": "garam_masala", "quantity": 0.003, "unit": "kg"},
        {"sku": "cooking_oil", "quantity": 0.02, "unit": "litre"},
        {"sku": "coriander_leaves", "quantity": 0.01, "unit": "kg"},
        {"sku": "salt", "quantity": 0.004, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D013",
      "dish_name": "Gulab Jamun",
      "category": "Dessert",
      "avg_price": 60,
      "ingredients": [
        {"sku": "wheat_flour", "quantity": 0.03, "unit": "kg"},
        {"sku": "cooking_oil", "quantity": 0.04, "unit": "litre"},
        {"sku": "cream", "quantity": 0.02, "unit": "kg"},
        {"sku": "salt", "quantity": 0.001, "unit": "kg"}
      ]
    },
    {
      "dish_id": "D014",
      "dish_name": "Masala Chai",
      "category": "Beverage",
      "avg_price": 30,
      "ingredients": [
        {"sku": "ginger_garlic", "quantity": 0.005, "unit": "kg"},
        {"sku": "salt", "quantity": 0.001, "unit": "kg"}
      ]
    }
  ]
}
```

**Validation Rules:**
- Every SKU referenced in recipes MUST exist in `ingredients.json`
- No recipe may have an empty `ingredients` array
- Quantity values represent per-serving amounts

---

### 2.3 Vendor Profiles & Time-Series Pricing

**File:** `data/vendor_pricing_history.json`
**Purpose:** Vendor master data + historical price snapshots (weekly). All 5 vendors must have pricing entries for every week.

```json
{
  "vendors": [
    {
      "vendor_id": "V001",
      "vendor_name": "Fresh Metro",
      "category": "Vegetables & Fruits",
      "contact": "+91-9876543210",
      "whatsapp": "9876543210",
      "delivery_time": "6:00 AM",
      "delivery_days": 1,
      "reliability_score": 0.92,
      "quality_score": 0.88,
      "credit_available": true,
      "credit_days": 7,
      "comm_preferences": {
        "channel": "whatsapp",
        "format": "text",
        "language": "en",
        "order_format_template": "Hi {vendor_name}, need: {items_list}. Delivery by {delivery_time} on {delivery_date}. Please confirm."
      }
    },
    {
      "vendor_id": "V002",
      "vendor_name": "Hyperpure",
      "category": "Mixed (Vegetables, Dairy, Dry Goods, Meat)",
      "contact": "+91-9876543211",
      "whatsapp": "9876543211",
      "delivery_time": "7:00 AM",
      "delivery_days": 1,
      "reliability_score": 0.95,
      "quality_score": 0.90,
      "credit_available": true,
      "credit_days": 10,
      "comm_preferences": {
        "channel": "whatsapp",
        "format": "structured",
        "language": "en",
        "order_format_template": "ORDER REQUEST\nRestaurant: {restaurant_name}\nItems:\n{items_table}\nDelivery: {delivery_date} by {delivery_time}\nPlease confirm availability."
      }
    },
    {
      "vendor_id": "V003",
      "vendor_name": "Local Meat Supplier",
      "category": "Meat & Poultry",
      "contact": "+91-9876543212",
      "whatsapp": "9876543212",
      "delivery_time": "6:30 AM",
      "delivery_days": 1,
      "reliability_score": 0.88,
      "quality_score": 0.85,
      "credit_available": true,
      "credit_days": 5,
      "comm_preferences": {
        "channel": "whatsapp",
        "format": "text",
        "language": "hi",
        "order_format_template": "Namaste {vendor_name}, {items_list} chahiye. {delivery_date} ko {delivery_time} tak delivery. Confirm karo."
      }
    },
    {
      "vendor_id": "V004",
      "vendor_name": "Dairy Delight",
      "category": "Dairy Products",
      "contact": "+91-9876543213",
      "whatsapp": "9876543213",
      "delivery_time": "7:30 AM",
      "delivery_days": 1,
      "reliability_score": 0.93,
      "quality_score": 0.92,
      "credit_available": true,
      "credit_days": 3,
      "comm_preferences": {
        "channel": "whatsapp",
        "format": "text",
        "language": "en",
        "order_format_template": "Hi {vendor_name}, please deliver: {items_list}. By {delivery_time} on {delivery_date}. Confirm?"
      }
    },
    {
      "vendor_id": "V005",
      "vendor_name": "Udaan Dry Goods",
      "category": "Dry Goods & Spices",
      "contact": "+91-9876543214",
      "whatsapp": "9876543214",
      "delivery_time": "8:00 AM",
      "delivery_days": 2,
      "reliability_score": 0.90,
      "quality_score": 0.87,
      "credit_available": true,
      "credit_days": 15,
      "comm_preferences": {
        "channel": "whatsapp",
        "format": "structured",
        "language": "en",
        "order_format_template": "ORDER\nFrom: {restaurant_name}\n{items_table}\nDelivery by: {delivery_date} {delivery_time}\nPayment: Credit ({credit_days} days)"
      }
    }
  ],
  "pricing_history": [
    {
      "snapshot_date": "2026-02-17",
      "week": 1,
      "prices": [
        {
          "vendor_id": "V001",
          "items": {
            "tomato": 28,
            "onion": 22,
            "ginger_garlic": 170,
            "coriander_leaves": 60,
            "green_chili": 45
          }
        },
        {
          "vendor_id": "V002",
          "items": {
            "tomato": 32,
            "onion": 26,
            "ginger_garlic": 180,
            "paneer": 410,
            "butter": 460,
            "cream": 390,
            "black_lentils": 118,
            "red_lentils": 78,
            "chicken_breast": 280,
            "yogurt": 58,
            "rice_basmati": 95,
            "cooking_oil": 140,
            "wheat_flour": 38
          }
        },
        {
          "vendor_id": "V003",
          "items": {
            "chicken_breast": 265
          }
        },
        {
          "vendor_id": "V004",
          "items": {
            "paneer": 395,
            "butter": 445,
            "cream": 370,
            "yogurt": 55
          }
        },
        {
          "vendor_id": "V005",
          "items": {
            "wheat_flour": 35,
            "rice_basmati": 90,
            "cooking_oil": 135,
            "salt": 18,
            "cumin_powder": 320,
            "turmeric_powder": 180,
            "red_chili_powder": 280,
            "garam_masala": 420,
            "black_lentils": 110,
            "red_lentils": 72
          }
        }
      ]
    },
    {
      "snapshot_date": "2026-02-24",
      "week": 2,
      "prices": [
        {
          "vendor_id": "V001",
          "items": {
            "tomato": 30,
            "onion": 20,
            "ginger_garlic": 175,
            "coriander_leaves": 65,
            "green_chili": 48
          }
        },
        {
          "vendor_id": "V002",
          "items": {
            "tomato": 34,
            "onion": 24,
            "ginger_garlic": 185,
            "paneer": 415,
            "butter": 465,
            "cream": 395,
            "black_lentils": 120,
            "red_lentils": 80,
            "chicken_breast": 285,
            "yogurt": 60,
            "rice_basmati": 98,
            "cooking_oil": 142,
            "wheat_flour": 40
          }
        },
        {
          "vendor_id": "V003",
          "items": {
            "chicken_breast": 270
          }
        },
        {
          "vendor_id": "V004",
          "items": {
            "paneer": 400,
            "butter": 450,
            "cream": 375,
            "yogurt": 56
          }
        },
        {
          "vendor_id": "V005",
          "items": {
            "wheat_flour": 36,
            "rice_basmati": 92,
            "cooking_oil": 138,
            "salt": 18,
            "cumin_powder": 325,
            "turmeric_powder": 182,
            "red_chili_powder": 285,
            "garam_masala": 425,
            "black_lentils": 112,
            "red_lentils": 74
          }
        }
      ]
    },
    {
      "snapshot_date": "2026-03-03",
      "week": 3,
      "prices": [
        {
          "vendor_id": "V001",
          "items": {
            "tomato": 33,
            "onion": 25,
            "ginger_garlic": 180,
            "coriander_leaves": 62,
            "green_chili": 50
          }
        },
        {
          "vendor_id": "V002",
          "items": {
            "tomato": 37,
            "onion": 28,
            "ginger_garlic": 190,
            "paneer": 420,
            "butter": 470,
            "cream": 400,
            "black_lentils": 122,
            "red_lentils": 82,
            "chicken_breast": 290,
            "yogurt": 62,
            "rice_basmati": 100,
            "cooking_oil": 145,
            "wheat_flour": 41
          }
        },
        {
          "vendor_id": "V003",
          "items": {
            "chicken_breast": 278
          }
        },
        {
          "vendor_id": "V004",
          "items": {
            "paneer": 405,
            "butter": 455,
            "cream": 380,
            "yogurt": 58
          }
        },
        {
          "vendor_id": "V005",
          "items": {
            "wheat_flour": 37,
            "rice_basmati": 94,
            "cooking_oil": 140,
            "salt": 19,
            "cumin_powder": 330,
            "turmeric_powder": 185,
            "red_chili_powder": 290,
            "garam_masala": 430,
            "black_lentils": 115,
            "red_lentils": 75
          }
        }
      ]
    },
    {
      "snapshot_date": "2026-03-10",
      "week": 4,
      "prices": [
        {
          "vendor_id": "V001",
          "items": {
            "tomato": 38,
            "onion": 28,
            "ginger_garlic": 190,
            "coriander_leaves": 68,
            "green_chili": 55
          }
        },
        {
          "vendor_id": "V002",
          "items": {
            "tomato": 42,
            "onion": 32,
            "ginger_garlic": 200,
            "paneer": 425,
            "butter": 475,
            "cream": 410,
            "black_lentils": 125,
            "red_lentils": 85,
            "chicken_breast": 295,
            "yogurt": 65,
            "rice_basmati": 105,
            "cooking_oil": 150,
            "wheat_flour": 43
          }
        },
        {
          "vendor_id": "V003",
          "items": {
            "chicken_breast": 285
          }
        },
        {
          "vendor_id": "V004",
          "items": {
            "paneer": 410,
            "butter": 460,
            "cream": 390,
            "yogurt": 60
          }
        },
        {
          "vendor_id": "V005",
          "items": {
            "wheat_flour": 38,
            "rice_basmati": 96,
            "cooking_oil": 142,
            "salt": 19,
            "cumin_powder": 340,
            "turmeric_powder": 190,
            "red_chili_powder": 295,
            "garam_masala": 440,
            "black_lentils": 118,
            "red_lentils": 78
          }
        }
      ]
    },
    {
      "snapshot_date": "2026-03-15",
      "week": 5,
      "note": "Holi Festival - Price Spike (+15-20% across all vendors)",
      "prices": [
        {
          "vendor_id": "V001",
          "items": {
            "tomato": 52,
            "onion": 38,
            "ginger_garlic": 210,
            "coriander_leaves": 85,
            "green_chili": 68
          }
        },
        {
          "vendor_id": "V002",
          "items": {
            "tomato": 58,
            "onion": 45,
            "ginger_garlic": 225,
            "paneer": 450,
            "butter": 500,
            "cream": 435,
            "black_lentils": 140,
            "red_lentils": 100,
            "chicken_breast": 320,
            "yogurt": 80,
            "rice_basmati": 120,
            "cooking_oil": 170,
            "wheat_flour": 50
          }
        },
        {
          "vendor_id": "V003",
          "items": {
            "chicken_breast": 310
          }
        },
        {
          "vendor_id": "V004",
          "items": {
            "paneer": 440,
            "butter": 490,
            "cream": 420,
            "yogurt": 72
          }
        },
        {
          "vendor_id": "V005",
          "items": {
            "wheat_flour": 44,
            "rice_basmati": 110,
            "cooking_oil": 162,
            "salt": 22,
            "cumin_powder": 380,
            "turmeric_powder": 215,
            "red_chili_powder": 335,
            "garam_masala": 500,
            "black_lentils": 132,
            "red_lentils": 88
          }
        }
      ]
    }
  ]
}
```

**Validation Rules:**
- V001 stocks ONLY vegetables/fruits — must NOT have chicken_breast, dairy, etc.
- All 5 vendors must have entries in every weekly snapshot
- Holi week (week 5) prices should be 15-20% higher than week 4
- Every SKU in pricing must map to a vendor whose category makes sense

---

### 2.4 POS Sales History (30 Days)

**File:** `data/pos_sales_history.json`
**Purpose:** Mock restaurant sales data that drives demand forecasting
**Generation:** Created by `scripts/generate_pos_data.py` (not hand-authored)

**Date Range:** February 17 - March 18, 2026 (30 days)

**Schema (every record MUST follow this exactly):**
```json
{
  "date": "2026-02-17",
  "day_of_week": "Tuesday",
  "weather": "sunny",
  "is_event": false,
  "event_name": null,
  "covers": 85,
  "sales": [
    {"dish_id": "D001", "dish_name": "Butter Chicken", "quantity": 21, "revenue": 4725}
  ],
  "total_revenue": 14325
}
```

**Required fields per sale record:** `dish_id`, `dish_name`, `quantity`, `revenue` — ALL four are mandatory, no optional fields.

**Generation Rules:**
- All 14 dishes must appear in every day's sales
- **Weekday base covers:** 80-95
- **Weekend multiplier:** x1.35
- **Holi (March 15, 2026):** x1.6
- **Rain days:** +15% hot dishes (Dal, Chai), -5% light dishes (Raita, Salad); hardcode 3 rainy days (Feb 18, Mar 5, Mar 12)
- **Dish popularity weights:** Roti 20%, Dal Makhani 18%, Butter Chicken 15%, Naan 12%, Jeera Rice 8%, Paneer Tikka 6%, Chicken Biryani 5%, Raita 4%, others distributed
- **Random noise:** +/-10% per dish per day
- Roti quantity should be ~2x Naan quantity (bread staple)

**Sample Records (for reference only — full 30-day dataset is generated):**

| Date | Day | Weather | Event | Covers |
|---|---|---|---|---|
| 2026-02-17 | Tuesday | sunny | — | 85 |
| 2026-02-18 | Wednesday | rainy | — | 90 |
| 2026-02-22 | Saturday | sunny | — | 120 |
| 2026-03-05 | Thursday | rainy | — | 88 |
| 2026-03-12 | Thursday | rainy | — | 92 |
| 2026-03-14 | Saturday | sunny | — | 125 |
| 2026-03-15 | Sunday | sunny | Holi | 155 |
| 2026-03-18 | Wednesday | sunny | — | 87 |

---

### 2.5 Current Inventory Snapshot

**File:** `data/current_inventory.json`
**Purpose:** Inventory on hand as of demo start. Used by AG-DPF to calculate order quantities.

```json
{
  "snapshot_date": "2026-03-19",
  "restaurant_id": "R001",
  "inventory": [
    {"sku": "tomato", "quantity_on_hand": 8.0, "unit": "kg"},
    {"sku": "onion", "quantity_on_hand": 12.0, "unit": "kg"},
    {"sku": "chicken_breast", "quantity_on_hand": 2.0, "unit": "kg", "note": "Intentionally low for demo stockout scenario"},
    {"sku": "paneer", "quantity_on_hand": 4.0, "unit": "kg"},
    {"sku": "butter", "quantity_on_hand": 3.0, "unit": "kg"},
    {"sku": "cream", "quantity_on_hand": 2.5, "unit": "kg"},
    {"sku": "black_lentils", "quantity_on_hand": 5.0, "unit": "kg"},
    {"sku": "red_lentils", "quantity_on_hand": 3.0, "unit": "kg"},
    {"sku": "ginger_garlic", "quantity_on_hand": 1.5, "unit": "kg"},
    {"sku": "yogurt", "quantity_on_hand": 3.0, "unit": "kg"},
    {"sku": "wheat_flour", "quantity_on_hand": 8.0, "unit": "kg"},
    {"sku": "rice_basmati", "quantity_on_hand": 6.0, "unit": "kg"},
    {"sku": "cooking_oil", "quantity_on_hand": 4.0, "unit": "litre"},
    {"sku": "salt", "quantity_on_hand": 5.0, "unit": "kg"},
    {"sku": "cumin_powder", "quantity_on_hand": 0.8, "unit": "kg"},
    {"sku": "turmeric_powder", "quantity_on_hand": 0.5, "unit": "kg"},
    {"sku": "red_chili_powder", "quantity_on_hand": 0.6, "unit": "kg"},
    {"sku": "garam_masala", "quantity_on_hand": 0.4, "unit": "kg"},
    {"sku": "coriander_leaves", "quantity_on_hand": 0.5, "unit": "kg"},
    {"sku": "green_chili", "quantity_on_hand": 0.8, "unit": "kg"}
  ]
}
```

**Design notes:** Chicken breast is at 2kg (daily need ~12kg) to trigger the stockout demo scenario. Other items are at 40-60% of estimated daily need.

---

### 2.6 Demo Configuration

**File:** `data/demo_config.json`
**Purpose:** Control demo date, weather, events, and timezone without code changes.

```json
{
  "current_date": "2026-03-19",
  "timezone": "Asia/Kolkata",
  "weather_today": "sunny",
  "is_event_today": false,
  "event_name_today": null,
  "upcoming_events": [
    {"date": "2026-03-15", "name": "Holi", "demand_multiplier": 1.6},
    {"date": "2026-03-30", "name": "Ugadi", "demand_multiplier": 1.3},
    {"date": "2026-04-14", "name": "Baisakhi", "demand_multiplier": 1.25}
  ],
  "weather_history": {
    "2026-02-18": "rainy",
    "2026-03-05": "rainy",
    "2026-03-12": "rainy"
  },
  "pos_data_range": {
    "start_date": "2026-02-17",
    "end_date": "2026-03-18",
    "total_days": 30
  }
}
```

---

## 3. Agent Architecture (Core Logic)

### 3.1 Agent Roles in MVP

Based on `step_4.5_solution_agents.md`, here are the **5 agents** used in the prototype:

| Agent | File | Role | Input | Output | Solutions Enabled |
|---|---|---|---|---|---|
| **AG-INT** | `agents/perception.py` | Intent Parser | User message (text) | Structured ParsedIntent | S-02, S-11 |
| **AG-DPF** | `agents/forecasting.py` | Demand Forecaster | POS sales history + inventory | Daily ingredient forecast | S-02 |
| **AG-MVR** | `agents/routing.py` | Vendor Router | Ingredient list + vendor pricing | Optimal vendor assignment | S-03 (implicit) |
| **AG-DSP** | `agents/dispatcher.py` | Outbound Dispatcher | Approved order + vendor preferences | Formatted messages for each vendor | S-11 |
| **Orchestrator** | `agents/orchestrator.py` | Agent Coordinator | ParsedIntent | Routed response via appropriate agents | All |

### 3.2 Agent Workflow Diagram

```
User Input (Chat)
      |
      v
+-------------------------------------+
| Orchestrator                        |
| Routes intent to correct agent chain|
+-------------------------------------+
      |
      v
+-------------------------------------+
| AG-INT: Perception Layer            |
| "We're out of chicken"              |
| -> ParsedIntent(action="low_stock", |
|    ingredient="chicken_breast")     |
+-------------------------------------+
      |
      v (Orchestrator reads intent.action)
      |
  [low_stock] --> AG-DPF -> AG-MVR -> build suggestion -> save to DB -> respond
  [approve]   --> load order -> AG-DSP -> dispatch -> update status -> respond
  [forecast]  --> AG-DPF(all) -> AG-MVR(all) -> build plan -> save -> respond
  [price_check] --> AG-MVR(lookup) -> respond
  [query]     --> direct Claude response -> respond
```

---

### 3.3 Agent Details

#### **AG-INT: Perception Layer**

**Purpose:** Parse unstructured user input into structured intent

```python
# Input
user_message = "We're out of chicken breast"

# Output → ParsedIntent
{
  "action": "low_stock",
  "ingredient": "chicken_breast",
  "context": "urgent",
  "additional_notes": null
}

# OR for approval:
user_message = "Approve the suggestion"
{
  "action": "approve_suggestion",
  "order_id": "ORD_20260319_001"
}
```

**Implementation:** Claude API (claude-sonnet-4-20250514, max 200 tokens). Per-restaurant conversation history (module-level dict keyed by restaurant_id, NOT a global list).

**Actions recognized:** `low_stock`, `order`, `approve_suggestion`, `forecast_today`, `price_check`, `query`

**Guardrail:** Single-turn parse only. No multi-turn confirmation loop. Claude's system prompt says "make reasonable assumptions and note them in additional_notes."

---

#### **AG-DPF: Demand Forecasting**

**Purpose:** Predict daily ingredient needs using POS data

```python
# Input
{
  "date": "2026-03-19",
  "days_history": 7,
  "ingredient": "chicken_breast"
}

# Process
1. Find all dishes using chicken_breast (D001, D007, D010)
2. Get last 7 days of sales for those dishes
3. Weighted average (recent days weighted more: day[-1]=1.4, day[-2]=1.2, day[-3]=1.1, day[-4..7]=1.0)
4. Sum ingredient qty = sum(avg_dish_qty * recipe_ingredient_qty) across all dishes
5. Check demo_config for event multiplier -> apply if target_date matches or is near event
6. Apply day-of-week adjustment (weekend +35%, weekday normal)
7. Add 15% safety stock
8. Subtract current inventory on hand
9. Return IngredientForecast with reasoning string

# Output
{
  "ingredient": "chicken_breast",
  "forecast_quantity": 12,
  "unit": "kg",
  "confidence": 0.85,
  "reasoning": "7-day weighted avg: 25 units across D001+D007+D010. Need 12.5kg. Inventory: 2kg. Order: 12kg (incl 15% safety)"
}
```

**Event-driven adjustment:** If `demo_config.upcoming_events` contains an event within 2 days of `target_date`, apply that event's `demand_multiplier` to the forecast.

**Guardrail:** No ML. Weighted average + multipliers only.

---

#### **AG-MVR: Vendor Routing**

**Purpose:** Assign order to best vendor(s)

```python
# Input
{
  "ingredient": "chicken_breast",
  "quantity": 12,
  "current_date": "2026-03-19"
}

# Process
1. get_vendors_for_sku("chicken_breast", date) -> validates vendor actually stocks it
   Returns: V002, V003 (NOT V001 — V001 is vegetables only)
2. Get current price per vendor from nearest pricing snapshot
   V002: Rs.320/kg (reliability: 0.95) -> Cost: Rs.3,840
   V003: Rs.310/kg (reliability: 0.88) -> Cost: Rs.3,720
3. Calculate adjusted score: total_cost / reliability_score (lower = better)
   V002: 3840 / 0.95 = Rs.4,042
   V003: 3720 / 0.88 = Rs.4,227
4. Credit days as tiebreaker
5. Mark best as is_recommended
6. Return all options (UI shows comparison)

# Output -> list[VendorOption]
[
  {"vendor_id": "V002", "vendor_name": "Hyperpure", "price_per_unit": 320,
   "total_cost": 3840, "reliability": 0.95, "adjusted_score": 4042,
   "credit_days": 10, "delivery_time": "7:00 AM", "is_recommended": true},
  {"vendor_id": "V003", "vendor_name": "Local Meat Supplier", "price_per_unit": 310,
   "total_cost": 3720, "reliability": 0.88, "adjusted_score": 4227,
   "credit_days": 5, "delivery_time": "6:30 AM", "is_recommended": false}
]
```

**SKU-vendor validation:** `get_vendors_for_sku(sku, date)` checks which vendors actually stock a given SKU in their pricing history. This prevents routing vegetables to a meat supplier or vice versa.

**Split-order handling:** Implicit via vendor grouping — when `route_order()` processes multiple ingredients, items naturally route to different vendors based on who stocks what. Explicit single-SKU splitting (splitting 12kg chicken across V002 + V003) is deferred for MVP.

---

#### **AG-DSP: Outbound Dispatcher**

**Purpose:** Format and return order messages for vendor channels (no actual HTTP calls)

```python
# Input
{
  "order": {
    "vendor_id": "V002",
    "items": [{"sku": "chicken_breast", "quantity": 12, "unit": "kg"}],
    "delivery_date": "2026-03-20",
    "delivery_time": "07:00"
  }
}

# Process
1. Load vendor comm_preferences from vendor data
2. Format message using vendor's order_format_template
3. Log to audit_log table
4. Update order status to "dispatched" in SQLite

# Output -> VendorMessage
{
  "vendor_id": "V002",
  "vendor_name": "Hyperpure",
  "channel": "whatsapp",
  "message": "ORDER REQUEST\nRestaurant: Spice Junction\nItems:\n- Chicken Breast: 12kg @ Rs.320/kg = Rs.3,840\nDelivery: 2026-03-20 by 07:00 AM\nPlease confirm availability.",
  "status": "formatted"
}
```

**Guardrail:** Does NOT send any HTTP requests. Just formats and returns messages. UI displays them.

---

### 3.4 Orchestrator

**File:** `agents/orchestrator.py`
**Purpose:** Chain agents together based on parsed intent. Single entry point for all chat interactions.

**Decision Tree:**

```
handle_message(message, restaurant_id):
  1. intent = AG-INT.parse_intent(message, restaurant_id)
  2. Route based on intent.action:

     "low_stock":
       forecast = AG-DPF.forecast_ingredient(intent.ingredient, target_date)
       options  = AG-MVR.route_ingredient(intent.ingredient, forecast.quantity, target_date)
       -> Build OrderSuggestion, save to DB with status="suggested"
       -> Return formatted suggestion with vendor comparison + Approve button

     "approve_suggestion":
       order = load_order(intent.order_id)  # status must be "suggested"
       messages = AG-DSP.dispatch_order(order)
       -> Update order status to "dispatched"
       -> Return dispatch confirmation with vendor messages

     "forecast_today":
       forecasts = AG-DPF.forecast_all_ingredients(target_date)
       assignments = AG-MVR.route_order(forecasts, target_date)
       -> Build full procurement plan, save to DB
       -> Return formatted daily plan with per-vendor totals

     "price_check":
       options = AG-MVR.route_ingredient(intent.ingredient, 1, target_date)
       -> Return price comparison (no order created)

     "query":
       -> Direct Claude API response (general question)

handle_approval(order_id):
  -> Shortcut for approve flow (called by Approve button)

handle_forecast_today(restaurant_id):
  -> Shortcut for forecast flow (called by Morning Forecast button)
```

**Response formatting:** `format_suggestion_text()` builds human-readable chat response with vendor comparisons, costs, delivery times, and action buttons.

---

### 3.5 Order Lifecycle State Machine

Orders progress through these states:

```
draft --> suggested --> approved --> dispatched --> confirmed
  |          |            |            |
  |          |            |            +--> (vendor confirms delivery - future)
  |          |            |
  |          |            +--> dispatched (AG-DSP formats & "sends" messages)
  |          |
  |          +--> approved (user taps Approve)
  |
  +--> suggested (AG-DPF + AG-MVR produce recommendation)

Transitions:
  draft -> suggested:    Orchestrator creates order after forecast + routing
  suggested -> approved: User approves via chat or Approve button
  approved -> dispatched: AG-DSP formats vendor messages, logs to audit
  dispatched -> confirmed: (Future: vendor confirms receipt — not in MVP)

For MVP, "confirmed" is set immediately after dispatch (simulated).
```

**State stored in:** `orders.status` column in SQLite.

---

## 4. Data Flow & API Contracts

### 4.1 Core API Endpoints

**Pydantic Request/Response Schemas:**

```python
from pydantic import BaseModel
from typing import Optional

# -- Chat --
class ChatRequest(BaseModel):
    message: str
    restaurant_id: str = "R001"

class ChatResponse(BaseModel):
    response_text: str
    order_id: Optional[str] = None
    action: str  # "suggestion", "dispatch_confirmation", "forecast_plan", "price_info", "general"
    data: Optional[dict] = None  # structured data for UI rendering

# -- Approve --
class ApproveRequest(BaseModel):
    order_id: str

class ApproveResponse(BaseModel):
    status: str  # "dispatched"
    order_id: str
    vendors_contacted: list[str]
    messages: list[dict]  # VendorMessage dicts

# -- Forecast --
# GET endpoint, no request body
class ForecastResponse(BaseModel):
    restaurant_id: str
    date: str
    forecasts: list[dict]  # IngredientForecast dicts
    vendor_assignments: list[dict]  # VendorAssignment dicts
    estimated_total_cost: float
    response_text: str

# -- Vendor Prices --
# GET endpoint, no request body
class VendorPriceResponse(BaseModel):
    ingredient: str
    date: str
    options: list[dict]  # VendorOption dicts
```

**Endpoints:**

```
POST /chat
  Request:  ChatRequest { message, restaurant_id }
  Response: ChatResponse { response_text, order_id?, action, data? }
  Flow:     AG-INT -> route by intent -> appropriate agents -> formatted response

POST /approve-order
  Request:  ApproveRequest { order_id }
  Response: ApproveResponse { status, order_id, vendors_contacted, messages }
  Flow:     Load order -> AG-DSP -> update status -> return

GET /forecast-today?restaurant_id=R001
  Response: ForecastResponse { forecasts, vendor_assignments, estimated_total_cost, response_text }
  Flow:     AG-DPF(all) -> AG-MVR(all) -> build plan -> save -> return

GET /vendor-prices?ingredient=chicken_breast&date=2026-03-19
  Response: VendorPriceResponse { ingredient, date, options }
  Flow:     AG-MVR lookup -> return options

GET /health
  Response: { "status": "ok", "version": "0.1.0" }
```

---

### 4.2 Data Store (SQLite)

**Tables:**

```sql
-- Restaurant profile (loaded from JSON, cached in DB)
CREATE TABLE restaurants (
  restaurant_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  cuisine TEXT,
  location TEXT,
  config JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Orders placed
CREATE TABLE orders (
  order_id TEXT PRIMARY KEY,
  restaurant_id TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  items JSON NOT NULL,
  total_cost FLOAT,
  status TEXT NOT NULL DEFAULT 'draft',
  vendors_assigned JSON,
  FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
);

-- Forecasts generated
CREATE TABLE forecasts (
  forecast_id TEXT PRIMARY KEY,
  restaurant_id TEXT NOT NULL,
  date DATE NOT NULL,
  ingredients JSON NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
);

-- Vendor assignments per order
CREATE TABLE vendor_assignments (
  assignment_id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  vendor_id TEXT NOT NULL,
  items JSON NOT NULL,
  estimated_cost FLOAT,
  routing_reason TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (order_id) REFERENCES orders(order_id)
);

-- Conversation history per restaurant
CREATE TABLE conversations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  restaurant_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (restaurant_id) REFERENCES restaurants(restaurant_id)
);

-- Audit trail for all agent actions
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  agent TEXT NOT NULL,
  action TEXT NOT NULL,
  restaurant_id TEXT,
  order_id TEXT,
  input_summary TEXT,
  output_summary TEXT,
  duration_ms INTEGER,
  success BOOLEAN DEFAULT TRUE,
  error_message TEXT
);
```

---

## 5. Demo Scenarios (Script for CEO)

### Scenario 1: Emergency Stockout (5 minutes)

**Setup:** Show POS data -> Highlight that chicken is running low

**Kitchen Manager Message:**
```
"Bhai, we're out of chicken! We have 3-4 orders waiting."
```

**System Response (via chat UI):**
```
Detected: Chicken Breast Low Stock

Last 7 days average: 24 units/day
Current available: 2kg
Recommendation: Order 12kg

Options:
> V002 (Hyperpure) - Rs.320/kg = Rs.3,840
  Delivery: 7:00 AM tomorrow (95% on-time)
  Credit: 10 days

  V003 (Local Meat Supplier) - Rs.310/kg = Rs.3,720
  Delivery: 6:30 AM tomorrow (88% on-time)
  Credit: 5 days

Recommended: V002 (best reliability-adjusted cost)
[Approve Order]
```

**Manager Action:** [Taps "Approve"]

**System Output:**
```
Order confirmed (ORD_20260319_XXXXXX)
WhatsApp sent to V002 (Hyperpure):
  "ORDER REQUEST
   Restaurant: Spice Junction
   Items: Chicken Breast 12kg @ Rs.320/kg
   Delivery: 2026-03-20 by 07:00 AM
   Please confirm availability."

Cost tracked: Rs.3,840
Estimated delivery: Mar 20, 7:00 AM
```

**CEO Insight:** "Without the system, the manager would spend 30 minutes calling 3-4 vendors individually. This took 10 seconds."

---

### Scenario 2: Pre-Dawn Predictive Ordering (7 minutes)

**Setup:** Show 30-day sales history -> Click "Run Morning Forecast"

**System Alert:**
```
Good morning! Daily Procurement Plan for Mar 19

Based on 30-day sales history & current inventory:

Tomatoes: Need 8kg (have 8kg, need 16kg total)
  Best: V001 @ Rs.38/kg = Rs.304

Chicken Breast: Need 12kg (have 2kg, need 14kg total)
  Best: V002 @ Rs.320/kg = Rs.3,840

Onions: Need 6kg (have 12kg, need 18kg total)
  Best: V001 @ Rs.28/kg = Rs.168

Paneer: Need 5kg (have 4kg, need 9kg total)
  Best: V004 @ Rs.410/kg = Rs.2,050

... (all ingredients with shortfall)

Routing Summary:
  V001: Tomatoes + Onions = Rs.472
  V002: Chicken Breast = Rs.3,840
  V004: Paneer = Rs.2,050

Total Estimated Cost: Rs.6,362
[Approve Full Plan]
```

**Manager:** [Reviews, taps "Approve Full Plan"]

**CEO Insight:** "The system doesn't replace the manager's judgment—it gives them options in 15 seconds instead of 45 minutes."

---

### Scenario 3: Price Fluctuation & Intelligent Routing (5 minutes)

**Setup:** Show price history -> Demonstrate how system responds to market changes

**Show Price Snapshot (Normal Week vs. Holi Week):**
```
CHICKEN BREAST PRICE COMPARISON

Week 2 (Feb 24):  V003 Rs.270/kg, V002 Rs.285/kg -> Route to V003
Week 4 (Mar 10):  V003 Rs.285/kg, V002 Rs.295/kg -> Route to V003
Holi Week (Mar 15): V003 Rs.310/kg, V002 Rs.320/kg -> Route to V003
                    (Both more expensive, but V003 still better)

System recommendation for Holi:
"Prices are 15-20% higher due to festival. Consider:
 - Ordering 2-3 days early (prices lower)
 - Reducing portion sizes on premium dishes
 - Promoting dal/paneer dishes (lower cost impact)"
```

**CEO Insight:** "The system doesn't just route today—it shows price trends and can recommend operational adjustments for profitability."

---

## 6. Technical Architecture

### 6.1 Project Structure

```
proto/
├── main.py                      # FastAPI server + startup
├── requirements.txt             # Dependencies (pinned)
├── .env.example                 # Environment variable template
├── .gitignore                   # .env, __pycache__, *.db
├── Procfile                     # Railway deployment command
├── railway.json                 # Railway build/deploy config
├── runtime.txt                  # Python version pin for Railway
├── agents/
│   ├── __init__.py
│   ├── perception.py           # AG-INT: Intent parser (Claude API)
│   ├── forecasting.py          # AG-DPF: Demand forecaster
│   ├── routing.py              # AG-MVR: Vendor router
│   ├── dispatcher.py           # AG-DSP: Message formatter
│   └── orchestrator.py         # Agent coordinator + response formatter
├── models/
│   └── schemas.py              # Pydantic models (shared)
├── data/
│   ├── restaurant_profile.json
│   ├── ingredients.json
│   ├── recipes.json
│   ├── vendor_pricing_history.json
│   ├── pos_sales_history.json  # Generated by script
│   ├── current_inventory.json
│   └── demo_config.json
├── db/
│   ├── __init__.py
│   └── init_db.py              # SQLite schema creation
├── scripts/
│   └── generate_pos_data.py    # POS data generator
├── ui/
│   ├── index.html              # Chat UI (WhatsApp-style)
│   └── styles.css
├── utils/
│   ├── __init__.py
│   ├── data_loader.py          # Load JSON files + helper queries
│   └── helpers.py              # parse_json, generate_order_id, audit_log
├── tests/
│   └── test_scenarios.py       # 3 end-to-end demo scenario tests
└── README.md
```

---

### 6.2 Technology Stack

| Component | Choice | Reason |
|---|---|---|
| **Backend** | Python FastAPI | Lightweight, async, easy to integrate agents |
| **LLM** | Claude API (claude-sonnet-4-20250514) | Context-aware intent parsing |
| **Database** | SQLite | Zero setup, perfect for local demo |
| **Frontend** | Vanilla HTML/JS/CSS | WhatsApp-like chat UI, no build system |
| **Data Format** | JSON files | Easy to load, modify, and share |
| **Deployment** | Railway (free tier) + local dev (`uvicorn main:app --reload`) | CEO accesses via Railway URL; no laptop dependency |

---

### 6.3 Key Implementation Notes

**For AG-INT (Intent Parser):**
```python
from anthropic import Anthropic

client = Anthropic()

# Per-restaurant conversation history (NOT global)
_conversation_histories: dict[str, list] = {}

async def parse_intent(user_message: str, restaurant_id: str) -> ParsedIntent:
    if restaurant_id not in _conversation_histories:
        _conversation_histories[restaurant_id] = []

    history = _conversation_histories[restaurant_id]
    history.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        system="""You are a restaurant procurement assistant.
        Parse user messages into structured JSON with:
        - action: "low_stock" | "order" | "approve_suggestion" | "forecast_today" | "price_check" | "query"
        - ingredient: SKU from available list (if applicable)
        - quantity: number (if specified)
        - context: "urgent" | "normal"
        - additional_notes: any assumptions you made

        Available SKUs: tomato, onion, chicken_breast, paneer, butter, cream,
        black_lentils, red_lentils, ginger_garlic, yogurt, wheat_flour,
        rice_basmati, cooking_oil, salt, cumin_powder, turmeric_powder,
        red_chili_powder, garam_masala, coriander_leaves, green_chili

        Make reasonable assumptions and note them in additional_notes.
        Respond ONLY with valid JSON.
        """,
        messages=history,
        max_tokens=200
    )

    assistant_message = response.content[0].text
    history.append({"role": "assistant", "content": assistant_message})

    return ParsedIntent(**parse_json(assistant_message))
```

**For AG-DPF (Forecasting):**
```python
def forecast_ingredient(sku: str, target_date: str, num_days: int = 7) -> IngredientForecast:
    # Get recipes using this ingredient
    recipes_using = get_recipes_using_ingredient(sku)

    # Get last 7 days of sales
    recent_sales = get_last_n_days_sales(num_days, target_date)

    # Weighted average per dish (recent days weighted more)
    weights = [1.0, 1.0, 1.0, 1.0, 1.1, 1.2, 1.4]  # oldest to newest
    total_ingredient_qty = 0.0

    for recipe in recipes_using:
        dish_quantities = []
        for day in recent_sales:
            for sale in day["sales"]:
                if sale["dish_id"] == recipe["dish_id"]:
                    dish_quantities.append(sale["quantity"])

        if dish_quantities:
            weighted_avg = sum(q * w for q, w in zip(dish_quantities, weights)) / sum(weights[:len(dish_quantities)])
            # Find ingredient qty per serving in this recipe
            ing_per_serving = next(
                ing["quantity"] for ing in recipe["ingredients"]
                if ing["sku"] == sku
            )
            total_ingredient_qty += weighted_avg * ing_per_serving

    # Event adjustment
    config = load_demo_config()
    for event in config.get("upcoming_events", []):
        days_until = abs((parse_date(event["date"]) - parse_date(target_date)).days)
        if days_until <= 2:
            total_ingredient_qty *= event["demand_multiplier"]
            break

    # Day-of-week adjustment
    if parse_date(target_date).weekday() >= 5:  # Saturday/Sunday
        total_ingredient_qty *= 1.35

    # Safety stock
    total_ingredient_qty *= 1.15

    # Subtract current inventory
    inventory = get_current_inventory(sku)
    order_qty = max(0, total_ingredient_qty - inventory)

    return IngredientForecast(
        ingredient=sku,
        forecast_quantity=round(order_qty, 1),
        unit=get_ingredient_unit(sku),
        confidence=0.85,
        reasoning=f"7-day weighted avg across {len(recipes_using)} dishes. "
                  f"Need {round(total_ingredient_qty, 1)}. Have {inventory}. "
                  f"Order: {round(order_qty, 1)}"
    )
```

**For AG-MVR (Routing):**
```python
def route_ingredient(sku: str, quantity: float, target_date: str) -> list[VendorOption]:
    # Validate which vendors actually stock this SKU
    vendors = get_vendors_for_sku(sku, target_date)

    options = []
    best_score = float('inf')
    best_idx = 0

    for i, vendor in enumerate(vendors):
        price = get_current_price(vendor["vendor_id"], sku, target_date)
        cost = price * quantity

        # Score: cost / reliability (lower is better)
        score = cost / vendor["reliability_score"]

        if score < best_score:
            best_score = score
            best_idx = i

        options.append(VendorOption(
            vendor_id=vendor["vendor_id"],
            vendor_name=vendor["vendor_name"],
            price_per_unit=price,
            total_cost=round(cost, 2),
            reliability=vendor["reliability_score"],
            adjusted_score=round(score, 2),
            credit_days=vendor.get("credit_days", 0),
            delivery_time=vendor["delivery_time"],
            is_recommended=False
        ))

    if options:
        options[best_idx].is_recommended = True

    return options
```

---

### 6.4 Environment Setup

**`.env.example`:**
```
ANTHROPIC_API_KEY=sk-ant-xxxxx
DATABASE_PATH=db/prototype.db
LOG_LEVEL=INFO
PORT=8000
```

**`requirements.txt`:**
```
fastapi==0.115.0
uvicorn==0.30.0
anthropic==0.40.0
pydantic==2.9.0
python-dotenv==1.0.1
sse-starlette==2.1.0
gunicorn==22.0.0
```

> **Railway Note:** On Railway, set `ANTHROPIC_API_KEY` as a service variable via the dashboard. `PORT` is auto-injected by Railway. SQLite lives in ephemeral storage (resets on redeploy) — acceptable since `init_database()` rebuilds schema and seed data on every startup.

**CORS:** Allow all origins in FastAPI middleware (demo only — Railway URL is randomly generated and not publicly discoverable).

---

### 6.5 Error Handling Strategy

All agent functions return an `AgentResult` wrapper:

```python
class AgentResult(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None
    agent: str
    duration_ms: int
```

On error, the orchestrator returns a user-friendly message and logs the error to `audit_log`. No stack traces in chat responses.

---

### 6.6 Audit Trail

Decorator pattern for automatic logging:

```python
def audit_logged(agent_name: str):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                audit_log(agent_name, func.__name__, success=True,
                          duration_ms=int((time.time()-start)*1000))
                return result
            except Exception as e:
                audit_log(agent_name, func.__name__, success=False,
                          error_message=str(e),
                          duration_ms=int((time.time()-start)*1000))
                raise
        return wrapper
    return decorator
```

Every agent call is logged to `audit_log` table with: agent name, action, input summary, output summary, duration, success/failure.

---

### 6.7 Pre-Dawn Trigger

For MVP, no scheduler. Two ways to trigger the morning forecast:

1. **UI button:** "Run Morning Forecast" in the chat header → calls `GET /forecast-today`
2. **Chat message:** User types "what do I need today?" → AG-INT routes to `forecast_today` action

Both call the same `handle_forecast_today()` orchestrator method.

---

### 6.8 Chat Communication

Simple POST/response pattern:

1. UI sends `POST /chat` with message text
2. Backend processes synchronously (agents run in sequence)
3. Backend returns `ChatResponse` with formatted text
4. UI renders response as a chat bubble

**SSE (optional stretch):** If response time exceeds 3 seconds, stream partial updates via Server-Sent Events using `sse-starlette`. Not required for MVP demo.

---

### 6.9 Railway Deployment

**`Procfile`:**
```
web: gunicorn main:app -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
```

**`railway.json`:**
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn main:app -w 1 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

**`runtime.txt`:**
```
python-3.12.3
```

**Key Details:**
- `PORT` environment variable is auto-injected by Railway; app must bind to `0.0.0.0:$PORT`
- SQLite is ephemeral (resets on each deploy) — acceptable because `init_database()` rebuilds schema and seeds data on every startup
- Single worker (`-w 1`) required for SQLite concurrency safety (no WAL mode needed)
- Static files (HTML/CSS/JS) served via FastAPI `StaticFiles` mount — works on Railway without additional config

**Deploy Instructions:**
1. Push code to a GitHub repository
2. Create a new project on [railway.app](https://railway.app)
3. Connect the GitHub repo; set root directory to `proto/`
4. Add `ANTHROPIC_API_KEY` as a service variable in the Railway dashboard
5. Deploy — Railway auto-detects Python, installs dependencies, runs Procfile
6. Share the generated Railway URL (e.g., `https://<app-name>.up.railway.app`) with CEO

---

## 7. MVP Build Tasks

### Scope & Guardrails

**IN SCOPE:** 4 agents + orchestrator, FastAPI backend, SQLite, HTML/JS chat UI, 30-day generated POS data, 3 demo scenarios working end-to-end.

**OUT OF SCOPE:** Real vendor APIs, auth, multi-restaurant, ML forecasting, voice input, production-grade deployment (CI/CD, monitoring, auto-scaling), automated test suite beyond smoke tests.

**GUARDRAILS — What NOT To Do:**
1. Do NOT build an ML model — 7-day weighted average is sufficient
2. Do NOT use WebSocket — simple POST/response (SSE optional stretch)
3. Do NOT add authentication — Railway URL is randomly generated and not publicly discoverable; acceptable for demo
4. Do NOT integrate real vendor APIs — mock everything
5. Do NOT use a frontend framework — vanilla HTML/JS/CSS only
6. Do NOT over-engineer agent interfaces — simple functions, not class hierarchies
7. Do NOT spend more than 2 hours on UI polish
8. Do NOT implement multi-language — English only
9. Do NOT build a separate admin panel

---

### Phase 0: Project Setup & Data Foundation (Day 1-2)

#### B-0.1: Initialize Project Structure
**Scope:** Create full directory tree under `proto/` (agents/, data/, db/, models/, scripts/, ui/, utils/, tests/)
**Output:** All directories + empty `__init__.py` files exist
**Dependencies:** None

#### B-0.2: Create requirements.txt, .env.example, .gitignore
**Scope:** `requirements.txt` with fastapi, uvicorn, anthropic, pydantic, python-dotenv, sse-starlette, gunicorn (all pinned). `.env.example` with ANTHROPIC_API_KEY placeholder and PORT=8000. `.gitignore` for .env, __pycache__, *.db. `Procfile`, `railway.json`, `runtime.txt` for Railway deployment (see Section 6.9).
**Acceptance:** `pip install -r requirements.txt` succeeds in fresh venv
**Dependencies:** None

#### B-0.3: Create All Static Data Files (7 JSON files)
**Scope:** Manually create based on specs in Sections 2.0-2.6:
- `data/restaurant_profile.json` — 1 restaurant profile
- `data/ingredients.json` — 20 SKUs, no pricing
- `data/recipes.json` — 14 dishes with complete ingredient lists (no empty arrays)
- `data/vendor_pricing_history.json` — 5 vendors + 5 weeks of pricing (all vendors in all weeks)
- `data/current_inventory.json` — Snapshot with chicken_breast at 2kg, others at 40-60%
- `data/demo_config.json` — Current date, weather, events, upcoming_events array

**Validation rules:**
- Every SKU in recipes.json must exist in ingredients.json
- Every vendor in pricing must have entries for ALL 5 weeks
- Every SKU in pricing must map to a vendor whose category makes sense
- V001 must NOT have chicken_breast (it's a vegetables vendor)
- No recipe may have an empty ingredients array

**Dependencies:** None (uses this design doc as spec)

#### B-0.4: Build POS Data Generator Script
**File:** `proto/scripts/generate_pos_data.py`
**Scope:** Python script that reads recipes.json and demo_config.json, outputs 30-day `pos_sales_history.json` (Feb 17 - Mar 18, 2026)
**Logic:**
- Weekday base covers: 80-95, Weekend: x1.35, Holi: x1.6
- Dish popularity weights (Butter Chicken 15%, Roti 20%, Dal 18%, etc.)
- Rain days: +15% hot dishes, -5% light dishes (3 rainy days hardcoded)
- +/-10% random noise per dish per day
- Every record: `{date, day_of_week, weather, is_event, event_name, covers, sales[], total_revenue}`
- Every sale: `{dish_id, dish_name, quantity, revenue}` — NO optional fields

**Acceptance:** `python scripts/generate_pos_data.py` creates valid 30-entry JSON. Saturday covers > weekday covers. Holi day has highest covers.
**Dependencies:** B-0.3

#### B-0.5: Build Data Loader Utility
**File:** `proto/utils/data_loader.py`
**Scope:** Functions to load all JSON files with `@lru_cache`. Plus helper functions:
- `get_recipes_using_ingredient(sku)` -> list of recipe dicts
- `get_vendors_for_sku(sku, date)` -> list of vendor dicts that stock this SKU
- `get_current_price(vendor_id, sku, date)` -> float (finds nearest pricing snapshot)
- `get_last_n_days_sales(num_days, target_date)` -> list of daily sales records

**Acceptance:** `get_recipes_using_ingredient("chicken_breast")` returns D001, D007, D010. `get_vendors_for_sku("chicken_breast", "2026-03-19")` returns V002 and V003 (NOT V001).
**Dependencies:** B-0.3, B-0.4

#### B-0.6: Initialize SQLite Database
**File:** `proto/db/init_db.py`
**Scope:** Create 6 tables: restaurants, orders, forecasts, vendor_assignments, conversations, audit_log. With proper types, foreign keys, defaults.
**Acceptance:** `python db/init_db.py` creates `db/prototype.db` with all 6 tables
**Dependencies:** None

---

### Phase 1: Agent Implementation (Day 2-5)

#### B-1.1: Pydantic Schemas
**File:** `proto/models/schemas.py`
**Scope:** Define all shared data models: ParsedIntent, IngredientForecast, VendorOption, VendorAssignment, OrderSuggestion, VendorMessage, AgentResult, ChatRequest, ChatResponse, ApproveRequest, ApproveResponse
**Dependencies:** None

#### B-1.2: AG-INT — Intent Parser (uses Claude API)
**File:** `proto/agents/perception.py`
**Function:** `async def parse_intent(message: str, restaurant_id: str) -> ParsedIntent`
**Scope:**
- Per-restaurant conversation history (module-level dict, NOT global list)
- Claude API call with system prompt containing available SKUs + action schema
- Parse response via `helpers.parse_json()`
- Actions: low_stock, order, approve_suggestion, forecast_today, price_check, query
- Max 200 tokens per Claude call, use claude-sonnet-4-20250514

**Guardrail:** No multi-turn confirmation. Single-turn parse only.
**Acceptance:** `parse_intent("We're out of chicken", "R001")` -> `ParsedIntent(action="low_stock", ingredient="chicken_breast")`
**Dependencies:** B-0.5, B-1.1, B-2.3

#### B-1.3: AG-DPF — Demand Forecasting
**File:** `proto/agents/forecasting.py`
**Functions:**
- `forecast_ingredient(sku, target_date, num_days=7) -> IngredientForecast`
- `forecast_all_ingredients(target_date) -> list[IngredientForecast]`

**Logic:** See Section 3.3 AG-DPF for full algorithm (weighted average, event multiplier, day-of-week, safety stock, subtract inventory).

**Guardrail:** No ML. Weighted average + multipliers only.
**Acceptance:** `forecast_ingredient("chicken_breast", "2026-03-19")` returns qty > 0 (inventory is only 2kg)
**Dependencies:** B-0.4, B-0.5, B-1.1

#### B-1.4: AG-MVR — Vendor Routing
**File:** `proto/agents/routing.py`
**Functions:**
- `route_ingredient(sku, quantity, target_date) -> list[VendorOption]`
- `route_order(ingredients: list[IngredientForecast], target_date) -> list[VendorAssignment]`

**Logic:** See Section 3.3 AG-MVR for full algorithm (SKU validation, cost/reliability scoring, credit tiebreaker).

**Guardrail:** No explicit single-SKU splitting.
**Acceptance:** `route_ingredient("chicken_breast", 12, "2026-03-19")` returns V002 and V003 options (NOT V001)
**Dependencies:** B-0.5, B-1.1

#### B-1.5: AG-DSP — Outbound Dispatcher
**File:** `proto/agents/dispatcher.py`
**Function:** `dispatch_order(order: OrderSuggestion) -> list[VendorMessage]`
**Scope:**
- For each VendorAssignment: load vendor comm_preferences
- Format message based on channel/format/order_format_template
- Log each message to audit_log
- Update order status to "dispatched" in SQLite
- Return list of VendorMessage

**Guardrail:** Do NOT send any HTTP requests. Just format and return messages.
**Acceptance:** Given V002 assigned chicken 12kg, returns message containing "chicken", "12", vendor name
**Dependencies:** B-0.5, B-0.6, B-1.1, B-2.3

#### B-1.6: Orchestrator
**File:** `proto/agents/orchestrator.py`
**Functions:**
- `async handle_message(message, restaurant_id) -> ChatResponse`
- `async handle_approval(order_id) -> ApproveResponse`
- `async handle_forecast_today(restaurant_id) -> ChatResponse`

**Decision tree:** See Section 3.4 for full routing logic.

**Also contains:** `format_suggestion_text()` — builds human-readable chat response.

**Acceptance:** Full flow works: message -> intent -> forecast -> route -> suggestion with formatted text
**Dependencies:** B-1.2, B-1.3, B-1.4, B-1.5, B-0.6, B-2.3

---

### Phase 2: API & Chat UI (Day 5-7)

#### B-2.1: FastAPI Server
**File:** `proto/main.py`
**Scope:**
- 5 endpoints: POST /chat, POST /approve-order, GET /forecast-today, GET /vendor-prices, GET /health
- CORS middleware (allow all origins)
- Static file serving for UI
- Startup event: init_database()
- Error handlers for 400/422/500
- Read PORT from environment variable (default 8000) for Railway compatibility

**Acceptance:** `uvicorn main:app --reload` starts. `curl localhost:8000/health` returns 200. Server binds to `0.0.0.0:$PORT` when PORT env var is set (Railway compatibility).
**Dependencies:** B-1.6

#### B-2.2: Chat UI
**Files:** `proto/ui/index.html`, `proto/ui/styles.css`
**Scope:**
- WhatsApp-style chat (green/white bubbles, dark header)
- Text input + send button at bottom
- Scrollable message container
- Inline "Approve" button when suggestion is returned
- "Run Morning Forecast" button in header
- `fetch()` for API calls, vanilla JS DOM manipulation
- Format responses with bold, line breaks, simple tables
- All fetch() calls use relative URLs (e.g., /chat, /approve-order) — no hardcoded localhost

**Guardrail:** No frontend framework. Max 2 hours on styling. Responsive for laptop and mobile (CEO may test on phone).
**Acceptance:** Type "We're out of chicken" -> see formatted suggestion with Approve button -> click Approve -> see dispatch confirmation
**Dependencies:** B-2.1

#### B-2.3: Helpers Utility
**File:** `proto/utils/helpers.py`
**Scope:**
- `parse_json(text)` — extract JSON from Claude response (try direct parse -> markdown block -> regex)
- `generate_order_id()` — format: ORD_YYYYMMDD_XXXXXX
- `audit_log(agent, action, ...)` — write to SQLite audit_log table
- `@audit_logged(agent_name)` — decorator for wrapping agent functions

**Acceptance:** `parse_json('{"action": "low_stock"}')` works. `parse_json('```json\n{"a":1}\n```')` works.
**Dependencies:** B-0.6

---

### Phase 3: Testing & Demo Polish (Day 7-9)

#### B-3.1: End-to-End Scenario Tests
**File:** `proto/tests/test_scenarios.py`
**Scope:** 3 test functions matching the 3 demo scenarios:
1. Emergency stockout: POST /chat "out of chicken" -> suggestion -> POST /approve -> dispatched
2. Pre-dawn forecast: GET /forecast-today -> multi-ingredient plan with routing
3. Price comparison: GET /vendor-prices?ingredient=chicken_breast -> multiple vendor options

**Acceptance:** All 3 pass with server running
**Dependencies:** B-2.1

#### B-3.2: Demo Polish
**Scope:**
- Run all 3 scenarios manually, tune response formatting
- Ensure numbers are realistic (match vendor data, sensible quantities)
- Ensure Approve button flow is smooth (no page reload)
- Verify response time < 5 seconds per message

**Acceptance:** Non-technical person can run all 3 scenarios from the UI
**Dependencies:** B-3.1

#### B-3.3: README
**File:** `proto/README.md`
**Scope:** Quick start (6 steps from clone to running), demo scenario instructions, architecture overview
**Dependencies:** Everything

---

### Phase 4: Railway Deployment (Day 9, ~1 hour)

#### B-4.1: Deploy to Railway
**Scope:**
- Push code to GitHub repository
- Create Railway project, connect to GitHub repo
- Set root directory to `proto/` (or configure RAILWAY_ROOT_DIR=proto)
- Add ANTHROPIC_API_KEY as Railway service variable
- Verify: hit `<railway-url>/health` from browser
- Run all 3 demo scenarios via deployed URL on mobile
- Share URL with CEO

**Acceptance:** CEO opens Railway URL on phone, types "We're out of chicken", sees full agent response with vendor options and Approve button.
**Dependencies:** B-3.3

---

### Task Dependency Graph

```
Phase 0 (Parallel):
  B-0.1 (dirs)   --+
  B-0.2 (reqs)   --+
  B-0.6 (SQLite)  -+
  B-1.1 (schemas) -+

Phase 0 (Sequential):
  B-0.3 (data files) --> B-0.4 (POS gen) --> B-0.5 (data loader)

Phase 1 (Parallel, after Phase 0):
  B-1.2 (AG-INT)  --+
  B-1.3 (AG-DPF)  --+
  B-1.4 (AG-MVR)  --+--> B-1.6 (Orchestrator)
  B-1.5 (AG-DSP)  --+
  B-2.3 (helpers)  --+

Phase 2 (Sequential):
  B-1.6 --> B-2.1 (FastAPI) --> B-2.2 (Chat UI)

Phase 3 (Sequential):
  B-2.2 --> B-3.1 (tests) --> B-3.2 (polish) --> B-3.3 (README)

Phase 4 (Deployment):
  B-3.3 --> B-4.1 (Railway deploy)
```

---

### Verification Plan

1. **After Phase 0:** Run `python scripts/generate_pos_data.py` -> verify 30-day JSON. Run `python db/init_db.py` -> verify tables exist. Manually validate all JSON files parse correctly.
2. **After Phase 1:** Call each agent function directly with test data, verify return types match Pydantic schemas.
3. **After Phase 2:** Start server, open UI, type "hello" -> verify response. Type "We're out of chicken" -> verify suggestion appears.
4. **After Phase 3:** Run all 3 demo scenarios end-to-end. Check audit_log table has entries. Verify response times < 5s.
5. **After Phase 4:** Open Railway URL on mobile. Verify chat UI renders correctly on phone. Run all 3 demo scenarios via deployed URL. Confirm response times < 8s (allowing Railway cold start on first request).

---

## 8. Success Criteria for CEO Demo

**The CEO should see:**

1. **Automation in Action:** Manager types one message -> System handles 3-4 vendors automatically
2. **Data-Driven Decisions:** Recommendations based on 30 days of sales history, not guesswork
3. **Cost Optimization:** System finds savings through intelligent routing across vendors
4. **Scalability:** One AI agent can serve many restaurants (vs. one KAM per 30-50 restaurants)
5. **Market Realism:** Prices fluctuate, system responds intelligently (Holi spike demo)

**The CEO should hear:**

- "This saves 45 minutes/day per restaurant = significant annual value"
- "POS data is the moat—competitors can't replicate this without sales data"
- "Same logic works for hotels, hospitals, offices (TAM expansion)"
- "One AI agent costs near-zero marginal cost, scales to 100+ restaurants"

---

## 9. What's NOT in This MVP

- No real vendor APIs (mock HTTP calls)
- No JFSL credit processing (out of scope)
- No full ML demand forecasting (simplified 7-day average)
- No multi-language speech-to-text (text input only, Claude handles intent)
- No vendor scorecards (reliability scores are static)
- No authentication (Railway URL is not publicly discoverable; acceptable for demo)
- No multi-restaurant support
- No automated scheduler (manual trigger only)

**But it demonstrates the core loop that works.**

---

## 10. Next Steps Post-MVP

Once CEO approves the concept:
1. Add JFSL credit integration (Phase 3)
2. Build vendor scoring system (Phase 3)
3. Integrate with real POS systems (Petpooja, Dineout, etc.)
4. Expand to multi-language voice input
5. Add analytics dashboard (spend tracking)
6. Production-hardening (auth, persistent database, compliance, security, custom domain)
7. Multi-restaurant support with tenant isolation
8. Automated pre-dawn scheduler (cron/celery)

---

**Document Version:** 2.1
**Date:** March 20, 2026
**Author:** Claude Code (Prototype Architecture)
