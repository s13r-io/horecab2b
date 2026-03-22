#!/usr/bin/env python3
"""
Background scheduler for auto-dispatching queued orders.
Runs as an asyncio task in the main event loop.
"""

import asyncio
import json
import sqlite3
import logging
from datetime import datetime

from agents.dispatcher import dispatch_order
from models.schemas import VendorAssignment
from utils.data_loader import get_demo_config
from utils.helpers import audit_log

logger = logging.getLogger(__name__)

_scheduler_task = None


def get_current_time() -> datetime:
    """Get current time (demo-aware)."""
    config = get_demo_config()
    demo_time = config.get("current_time")
    demo_date = config.get("current_date", datetime.now().strftime("%Y-%m-%d"))

    if demo_time:
        return datetime.strptime(f"{demo_date} {demo_time}", "%Y-%m-%d %H:%M")
    return datetime.now()


async def scheduler_loop():
    """Background loop checking for queued orders to dispatch."""
    logger.info("Order scheduler started")
    while True:
        try:
            now = get_current_time()
            now_str = now.strftime("%Y-%m-%d %H:%M")

            conn = sqlite3.connect("db/prototype.db")
            cursor = conn.cursor()

            # Find queued orders whose send time has arrived
            cursor.execute(
                """SELECT order_id, restaurant_id, vendors_assigned
                   FROM orders
                   WHERE status = 'queued'
                     AND scheduled_send_time <= ?""",
                (now_str,)
            )
            rows = cursor.fetchall()

            for order_id, restaurant_id, vendors_json in rows:
                logger.info(f"Scheduler dispatching order {order_id}")
                vendors_assigned = json.loads(vendors_json)

                assignments = [
                    VendorAssignment(
                        vendor_id=v["vendor_id"],
                        vendor_name=v["vendor_name"],
                        items=v["items"],
                        estimated_cost=v["estimated_cost"],
                        routing_reason="Scheduled dispatch"
                    )
                    for v in vendors_assigned
                ]

                config = get_demo_config()
                dispatch_order(order_id, assignments, "Spice Junction", config["current_date"])

                audit_log(
                    agent_name="SCHEDULER",
                    action="auto_dispatch",
                    order_id=order_id,
                    restaurant_id=restaurant_id
                )

            conn.close()

        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)

        await asyncio.sleep(60)


def start_scheduler():
    """Start the background scheduler task."""
    global _scheduler_task
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    _scheduler_task = loop.create_task(scheduler_loop())
    logger.info("Scheduler task created")


def stop_scheduler():
    """Stop the background scheduler task."""
    global _scheduler_task
    if _scheduler_task:
        _scheduler_task.cancel()
        _scheduler_task = None
