#!/usr/bin/env python3
"""
AG-DSP: Dispatcher Agent
Formats and dispatches orders to vendors (no actual HTTP sending).
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List

from models.schemas import VendorAssignment, VendorMessage
from utils.data_loader import get_vendor_by_id
from utils.helpers import audit_log


def dispatch_order(order_id: str, vendor_assignments: List[VendorAssignment],
                   restaurant_name: str, target_date: str) -> List[VendorMessage]:
    """
    Format and dispatch order messages to vendors.

    For each VendorAssignment:
    1. Build items_list (comma-separated) AND items_table (bulleted with prices)
    2. Fill order_format_template using str.format_map()
    3. Write to audit_log
    4. Update order status to "dispatched"

    Returns list of VendorMessage objects (formatted messages, no HTTP sent).
    """
    messages = []
    db_path = "db/prototype.db"

    # Parse target date to calculate delivery date
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    delivery_dt = target_dt + timedelta(days=1)
    delivery_date = delivery_dt.strftime("%Y-%m-%d")

    for assignment in vendor_assignments:
        vendor = get_vendor_by_id(assignment.vendor_id)
        if not vendor:
            continue

        # Build items_list (comma-separated)
        items_list = ", ".join([
            f"{item['quantity']} {item['unit']} {item['ingredient_name']}"
            for item in assignment.items
        ])

        # Build items_table (bulleted with prices)
        items_table = "\n".join([
            f"• {item['ingredient_name']}: {item['quantity']} {item['unit']} @ ₹{item['price_per_unit']}/unit"
            for item in assignment.items
        ])

        # Get communication preferences
        channel = vendor.get("comm_preferences", {}).get("channel", "whatsapp")
        template = vendor.get("comm_preferences", {}).get("order_format_template", "")

        # Fill template using str.format_map (unused keys silently ignored)
        message_text = template.format_map({
            "items_list": items_list,
            "items_table": items_table,
            "vendor_name": vendor["vendor_name"],
            "restaurant_name": restaurant_name,
            "delivery_time": vendor.get("delivery_time", "24h"),
            "delivery_date": delivery_date,
            "credit_days": vendor.get("credit_days", 0),
            "order_id": order_id
        })

        # Create VendorMessage
        vendor_message = VendorMessage(
            vendor_id=assignment.vendor_id,
            vendor_name=assignment.vendor_name,
            channel=channel,
            message_text=message_text
        )
        messages.append(vendor_message)

        # Write to audit log
        audit_log(
            agent_name="AG-DSP",
            action="dispatch_order",
            restaurant_id="R001",
            order_id=order_id,
            data={
                "vendor_id": assignment.vendor_id,
                "items_count": len(assignment.items),
                "estimated_cost": assignment.estimated_cost
            },
            duration_ms=0
        )

    # Update order status to "placed" in database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE order_id = ?",
            ("placed", datetime.now().isoformat(), order_id)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        audit_log(
            agent_name="AG-DSP",
            action="update_order_status_error",
            error=str(e),
            order_id=order_id,
            duration_ms=0
        )

    return messages
