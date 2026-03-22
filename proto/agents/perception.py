#!/usr/bin/env python3
"""
AG-INT: Intent Perception Agent
Parses user messages to extract intent using Claude API.
"""

import json
import os
from anthropic import Anthropic

from models.schemas import ParsedIntent
from utils.helpers import parse_json
from utils.data_loader import get_all_ingredients


# Module-level conversation histories
_conversation_histories: dict[str, list[dict]] = {}

# Initialize Anthropic client
_client = Anthropic()


def parse_intent(message: str, restaurant_id: str) -> ParsedIntent:
    """
    Parse user message to extract intent.

    Uses Claude API with claude-sonnet-4-20250514.
    Returns JSON with: action, ingredient, quantity, context, additional_notes, order_id

    Actions: low_stock, approve_suggestion, forecast_today, price_check, query
    """
    # Get all ingredient names for the system prompt
    ingredients = get_all_ingredients()
    ingredient_list = ", ".join([f"{ing['name']} (SKU: {ing['sku']})" for ing in ingredients])

    # Ensure conversation history exists
    if restaurant_id not in _conversation_histories:
        _conversation_histories[restaurant_id] = []

    # Add user message to history
    _conversation_histories[restaurant_id].append({
        "role": "user",
        "content": message
    })

    system_prompt = f"""You are an intent parser for a restaurant procurement system.
Extract the user's intent from their message and respond ONLY with valid JSON.

Available ingredients: {ingredient_list}

Available actions:
- "low_stock": User reports insufficient inventory of an ingredient
- "approve_suggestion": User approves a suggested order
- "forecast_today": User wants to see today's demand forecast
- "price_check": User wants to compare prices for an ingredient
- "place_order": User wants to place/create an order based on previous conversation (e.g., "place the order", "order it", "go ahead and order")
- "confirm_order": User confirms a proposed order (e.g., "yes", "confirm", "looks good") after seeing order details
- "query": General question or chat

For "place_order": Examine the FULL conversation history. If forecast was discussed, set context to "forecast". If specific ingredient was discussed, extract ingredient and quantity.

For "confirm_order": Extract order_id if present in context.

Response format (JSON only, no other text):
{{
  "action": "low_stock|approve_suggestion|forecast_today|price_check|place_order|confirm_order|query",
  "ingredient": "ingredient_name or null",
  "quantity": number or null,
  "context": "forecast|ingredient|null",
  "additional_notes": "any notes or null",
  "order_id": "order ID if mentioned or null",
  "items": [list of items] or null
}}

Always respond with valid JSON only."""

    try:
        response = _client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system=system_prompt,
            messages=_conversation_histories[restaurant_id]
        )

        # Get response text
        response_text = response.content[0].text

        # Store raw response in history (not parsed object)
        _conversation_histories[restaurant_id].append({
            "role": "assistant",
            "content": response_text
        })

        # Parse JSON response
        parsed = parse_json(response_text)

        # Validate and create ParsedIntent
        intent = ParsedIntent(
            action=parsed.get("action", "query"),
            ingredient=parsed.get("ingredient"),
            quantity=parsed.get("quantity"),
            context=parsed.get("context"),
            additional_notes=parsed.get("additional_notes"),
            order_id=parsed.get("order_id"),
            items=parsed.get("items")
        )

        return intent

    except Exception as e:
        # If parsing fails, return default "query" intent
        return ParsedIntent(action="query")


def get_conversation_history(restaurant_id: str) -> list[dict]:
    """Get conversation history for a restaurant."""
    return _conversation_histories.get(restaurant_id, [])


def clear_conversation_history(restaurant_id: str):
    """Clear conversation history for a restaurant."""
    if restaurant_id in _conversation_histories:
        del _conversation_histories[restaurant_id]
