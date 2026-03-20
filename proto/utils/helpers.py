#!/usr/bin/env python3
"""
Helper utilities for JSON parsing, ID generation, auditing, and decoration.
"""

import json
import re
import sqlite3
import time
import uuid
from datetime import datetime
from functools import wraps
from pathlib import Path


# ============================================================================
# JSON Parsing (3-strategy fallback)
# ============================================================================

def parse_json(text: str) -> dict:
    """
    Parse JSON from text with 3 fallback strategies:
    1. Direct parse
    2. Markdown code block extraction (```json ... ```)
    3. Braces regex fallback {... }
    """
    text = text.strip()

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Markdown code block (re.DOTALL for cross-line)
    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Strategy 3: Extract braces
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from text: {text[:100]}")


# ============================================================================
# Order ID Generation
# ============================================================================

def generate_order_id() -> str:
    """Generate order ID in format: ORD_YYYYMMDD_XXXXXX"""
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    random_hex = uuid.uuid4().hex[:6].upper()
    return f"ORD_{date_str}_{random_hex}"


# ============================================================================
# Audit Logging
# ============================================================================

def audit_log(agent_name: str, action: str, data: dict = None, error: str = None,
              restaurant_id: str = None, order_id: str = None, duration_ms: int = None):
    """
    Write to audit log in SQLite.
    Opens its own connection per call (MVP simplicity), never raises.
    """
    try:
        db_path = Path(__file__).parent.parent / "db" / "prototype.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        success = error is None
        input_summary = json.dumps(data) if data else None

        cursor.execute(
            """
            INSERT INTO audit_log (agent, action, restaurant_id, order_id,
                                   input_summary, duration_ms, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (agent_name, action, restaurant_id, order_id, input_summary, duration_ms, success, error)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        # Never raise from audit_log
        pass


def audit_logged(agent_name: str):
    """
    Decorator: wraps async/sync functions, auto-times, catches errors.
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = int((time.time() - start) * 1000)
                audit_log(
                    agent_name=agent_name,
                    action=f"{func.__name__}_success",
                    data={"duration_ms": duration_ms}
                )
                return result
            except Exception as e:
                duration_ms = int((time.time() - start) * 1000)
                audit_log(
                    agent_name=agent_name,
                    action=f"{func.__name__}_error",
                    error=str(e),
                    data={"duration_ms": duration_ms}
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start) * 1000)
                audit_log(
                    agent_name=agent_name,
                    action=f"{func.__name__}_success",
                    data={"duration_ms": duration_ms}
                )
                return result
            except Exception as e:
                duration_ms = int((time.time() - start) * 1000)
                audit_log(
                    agent_name=agent_name,
                    action=f"{func.__name__}_error",
                    error=str(e),
                    data={"duration_ms": duration_ms}
                )
                raise

        # Determine if function is async
        if hasattr(func, '__code__'):
            if func.__code__.co_flags & 0x100:  # CO_COROUTINE
                return async_wrapper

        return sync_wrapper

    return decorator
