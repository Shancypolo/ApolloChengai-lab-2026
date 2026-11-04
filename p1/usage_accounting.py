"""Track OpenAI token usage and estimated cost for one browser session."""

from __future__ import annotations

import threading
import time
from typing import Any


PRICE_UNITS_PER_TOKEN = {
    "input": 100,
    "cached_input": 10,
    "cache_write_30m": 125,
    "cache_write_12h": 250,
    "output": 500,
}
LONG_INPUT_THRESHOLD = 272_000
USD_UNITS_PER_DOLLAR = 1_000_000_000
SESSION_IDLE_SECONDS = 86_400
MAX_TRACKED_SESSIONS = 1_000


def read_field(value: Any, name: str) -> Any:
    """Read a field from an SDK object or a plain dictionary."""
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def valid_count(value: Any) -> int | None:
    """Return a nonnegative token count or mark it invalid."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def usage_from_response(response: Any) -> dict[str, Any] | None:
    """Extract the reported token breakdown without counting subsets twice."""
    usage = read_field(response, "usage")
    if usage is None:
        return None
    input_tokens = valid_count(read_field(usage, "input_tokens"))
    output_tokens = valid_count(read_field(usage, "output_tokens"))
    total_tokens = valid_count(read_field(usage, "total_tokens"))
    if input_tokens is None or output_tokens is None:
        return None

    input_details = read_field(usage, "input_tokens_details")
    output_details = read_field(usage, "output_tokens_details")
    cached_value = read_field(input_details, "cached_tokens")
    cache_write_value = read_field(input_details, "cache_write_tokens")
    reasoning_value = read_field(output_details, "reasoning_tokens")
    reported_cached_tokens = valid_count(cached_value)
    reported_cache_write_tokens = valid_count(cache_write_value)
    reported_reasoning_tokens = valid_count(reasoning_value)
    cached_is_valid = reported_cached_tokens is not None and reported_cached_tokens <= input_tokens
    write_is_valid = reported_cache_write_tokens is not None
    reasoning_is_valid = reported_reasoning_tokens is not None and reported_reasoning_tokens <= output_tokens
    cached_tokens = reported_cached_tokens if cached_is_valid else 0
    cache_write_tokens = reported_cache_write_tokens if write_is_valid else 0
    reasoning_tokens = reported_reasoning_tokens if reasoning_is_valid else 0
    if cached_tokens + cache_write_tokens > input_tokens:
        write_is_valid = False
        cache_write_tokens = 0
    write_details = read_field(input_details, "cache_write_tokens_details")
    reported_30m = valid_count(read_field(write_details, "ttl_30m_tokens"))
    reported_12h = valid_count(read_field(write_details, "ttl_12h_tokens"))
    write_breakdown_is_valid = cache_write_tokens == 0 or (
        reported_30m is not None and reported_12h is not None
        and reported_30m + reported_12h == cache_write_tokens
    )
    cache_write_detail_complete = write_is_valid and write_breakdown_is_valid
    cache_write_30m_tokens = reported_30m if cache_write_detail_complete and cache_write_tokens else 0
    cache_write_12h_tokens = reported_12h if cache_write_detail_complete and cache_write_tokens else 0
    computed_total = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": computed_total,
        "cached_tokens": cached_tokens,
        "cache_write_tokens": cache_write_tokens,
        "cache_write_30m_tokens": cache_write_30m_tokens,
        "cache_write_12h_tokens": cache_write_12h_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cached_detail_complete": cached_is_valid,
        "cache_write_detail_complete": cache_write_detail_complete,
        "details_complete": (
            cached_is_valid and cache_write_detail_complete
            and reasoning_is_valid and total_tokens == computed_total
        ),
    }


def cost_units(usage: dict[str, Any]) -> int:
    """Calculate cost in exact 1e-9 USD units from published token rates."""
    uncached_tokens = usage["input_tokens"] - usage["cached_tokens"] - usage.get("cache_write_tokens", 0)
    input_cost = (
        uncached_tokens * PRICE_UNITS_PER_TOKEN["input"]
        + usage["cached_tokens"] * PRICE_UNITS_PER_TOKEN["cached_input"]
        + usage.get("cache_write_30m_tokens", 0) * PRICE_UNITS_PER_TOKEN["cache_write_30m"]
        + usage.get("cache_write_12h_tokens", 0) * PRICE_UNITS_PER_TOKEN["cache_write_12h"]
    )
    output_cost = usage["output_tokens"] * PRICE_UNITS_PER_TOKEN["output"]
    if usage["input_tokens"] > LONG_INPUT_THRESHOLD:
        return input_cost * 2 + output_cost * 3 // 2
    return input_cost + output_cost


def format_usd(units: int) -> str:
    """Round exact nano-dollar units to eight visible USD decimals."""
    dollars, fraction = divmod((units + 5) // 10, USD_UNITS_PER_DOLLAR // 10)
    return f"${dollars}.{fraction:08d}"


def empty_usage() -> dict[str, Any]:
    """Create the in-memory counters for a new browser session."""
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
        "reasoning_tokens": 0,
        "cost_units": 0,
        "api_calls": 0,
        "unreported_calls": 0,
        "incomplete_details_calls": 0,
        "unpriced_calls": 0,
        "updated_at": time.monotonic(),
    }


def usage_snapshot(record: dict[str, Any]) -> dict[str, Any]:
    """Return display values without exposing the mutable ledger record."""
    snapshot = {
        **record,
        "cost_usd": format_usd(record["cost_units"]),
        "is_partial": bool(record["unreported_calls"] or record["incomplete_details_calls"] or record["unpriced_calls"]),
    }
    for name in ("total_tokens", "input_tokens", "cached_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens"):
        snapshot[f"{name}_label"] = f"{record[name]:,}"
    return snapshot


class SessionUsageLedger:
    """Hold token totals in memory and discard idle browser sessions."""

    def __init__(self):
        """Start an empty ledger protected for background worker updates."""
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def snapshot(self, session_id: str) -> dict[str, Any]:
        """Return this browser session's current token and USD totals."""
        now = time.monotonic()
        with self._lock:
            self._remove_idle_sessions(now)
            record = self._sessions.get(session_id)
            if record is None:
                self._make_room()
                record = empty_usage()
                self._sessions[session_id] = record
            record["updated_at"] = now
            return usage_snapshot(record)

    def record(self, session_id: str, usage: dict[str, Any] | None) -> None:
        """Add one API attempt and its reported usage, if available."""
        now = time.monotonic()
        with self._lock:
            self._remove_idle_sessions(now)
            record = self._sessions.get(session_id)
            if record is None:
                self._make_room()
                record = empty_usage()
                self._sessions[session_id] = record
            record["api_calls"] += 1
            record["updated_at"] = now
            if usage is None:
                record["unreported_calls"] += 1
                return
            for name in ("input_tokens", "output_tokens", "total_tokens", "cached_tokens", "cache_write_tokens", "reasoning_tokens"):
                record[name] += usage[name]
            if usage.get("cached_detail_complete", False) and usage.get("cache_write_detail_complete", False):
                record["cost_units"] += cost_units(usage)
            else:
                record["unpriced_calls"] += 1
            if not usage["details_complete"]:
                record["incomplete_details_calls"] += 1

    def _remove_idle_sessions(self, now: float) -> None:
        """Drop old entries and bound memory used by abandoned sessions."""
        expired = [
            key for key, value in self._sessions.items()
            if now - value["updated_at"] > SESSION_IDLE_SECONDS
        ]
        for key in expired:
            self._sessions.pop(key, None)

    def _make_room(self) -> None:
        """Evict the least recently used session when the ledger is full."""
        if len(self._sessions) >= MAX_TRACKED_SESSIONS:
            oldest = min(self._sessions, key=lambda key: self._sessions[key]["updated_at"])
            self._sessions.pop(oldest, None)
