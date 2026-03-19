"""
simulate.py — Daily simulation runner.

Run once per day (via GitHub Actions cron or manually).
Reads simulation_log.json, fetches live APYs from DeFiLlama,
decides whether to rebalance, accrues daily yield, and writes
the updated log back to disk.
"""

import json
import time
import logging
from datetime import date, datetime
from pathlib import Path

import requests

import config

# ─────────────────────────────────────────────
LOG_FILE  = Path(__file__).parent / "simulation_log.json"
DATE_FMT  = "%Y-%m-%d"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Data Layer
# ─────────────────────────────────────────────

def load_log() -> dict:
    with open(LOG_FILE, "r") as fh:
        return json.load(fh)


def save_log(data: dict) -> None:
    with open(LOG_FILE, "w") as fh:
        json.dump(data, fh, indent=2)


# ─────────────────────────────────────────────
#  DeFiLlama API
# ─────────────────────────────────────────────

def fetch_pool_data() -> list[dict]:
    """
    Fetch all pools from DeFiLlama and return only the ones
    listed in config.WATCHED_POOLS.

    Retries up to API_MAX_RETRIES times on failure.
    Returns an empty list if all retries fail (caller handles fallback).
    """
    watched_ids = {p["id"] for p in config.WATCHED_POOLS}

    for attempt in range(1, config.API_MAX_RETRIES + 1):
        try:
            resp = requests.get(
                config.DEFILLAMA_POOLS_URL,
                timeout=config.API_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            all_pools = resp.json().get("data", [])
            matched = [p for p in all_pools if p.get("pool") in watched_ids]
            log.info("DeFiLlama: fetched %d pools, matched %d watched", len(all_pools), len(matched))
            return matched
        except Exception as exc:
            log.warning("API attempt %d/%d failed: %s", attempt, config.API_MAX_RETRIES, exc)
            if attempt < config.API_MAX_RETRIES:
                time.sleep(config.API_RETRY_DELAY_SECS)

    log.error("All API attempts failed — will use yesterday's APY as fallback")
    return []


def enrich_pools(raw_pools: list[dict]) -> list[dict]:
    """
    Merge live API data with our config metadata.
    Returns a list of dicts with guaranteed keys.
    """
    id_to_live = {p["pool"]: p for p in raw_pools}
    enriched = []
    for cfg in config.WATCHED_POOLS:
        live = id_to_live.get(cfg["id"], {})
        tvl  = live.get("tvlUsd", 0) or 0
        apy  = live.get("apyBase", 0) or 0          # apyBase only — no reward token dependency
        enriched.append({
            "id":       cfg["id"],
            "name":     cfg["name"],
            "protocol": cfg["protocol"],
            "symbol":   cfg["symbol"],
            "tvlUsd":   tvl,
            "apy":      round(apy, 4),
            "api_ok":   bool(live),
        })
    return enriched


# ─────────────────────────────────────────────
#  Rebalance Logic
# ─────────────────────────────────────────────

def find_best_pool(pools: list[dict]) -> dict | None:
    """Return the highest-APY pool that clears the TVL floor."""
    eligible = [p for p in pools if p["tvlUsd"] >= config.MIN_POOL_TVL_USD and p["apy"] > 0]
    if not eligible:
        return None
    return max(eligible, key=lambda p: p["apy"])


def should_rebalance(
    current_pool_id: str | None,
    current_apy: float,
    best_pool: dict | None,
    days_since_last_move: int,
    balance: float,
) -> tuple[bool, str]:
    """
    Returns (move: bool, reason: str).

    Rules (ALL must pass to trigger a move):
      1. We have a valid best pool and it's different from current.
      2. Improvement exceeds REBALANCE_THRESHOLD.
      3. Enough days have elapsed since last move.
      4. Break-even period is within MAX_BREAK_EVEN_DAYS.
    """
    if best_pool is None:
        return False, "No eligible pool found"

    if best_pool["id"] == current_pool_id:
        return False, "Already in best pool"

    improvement = best_pool["apy"] - current_apy
    if improvement < config.REBALANCE_THRESHOLD:
        return False, f"Improvement {improvement:.2f}pp below threshold {config.REBALANCE_THRESHOLD}pp"

    if days_since_last_move < config.MIN_DAYS_BEFORE_MOVE:
        return False, f"Only {days_since_last_move}d since last move (min {config.MIN_DAYS_BEFORE_MOVE}d)"

    # Break-even: how many days until the extra yield covers gas cost?
    daily_extra = balance * (improvement / 100) / 365
    if daily_extra <= 0:
        return False, "Zero daily extra yield"
    break_even_days = config.GAS_COST_USD / daily_extra
    if break_even_days > config.MAX_BREAK_EVEN_DAYS:
        return False, f"Break-even {break_even_days:.0f}d > max {config.MAX_BREAK_EVEN_DAYS}d"

    return True, f"Moving: +{improvement:.2f}pp APY, break-even in {break_even_days:.1f}d"


# ─────────────────────────────────────────────
#  Core Runner
# ─────────────────────────────────────────────

def run_daily_simulation() -> None:
    today_str = date.today().strftime(DATE_FMT)
    log.info("=== Simulation run for %s ===", today_str)

    data = load_log()
    meta = data["meta"]

    # ── Guard: don't run twice on the same calendar day ──────────────
    if data["daily_log"] and data["daily_log"][-1]["date"] == today_str:
        log.info("Already ran today (%s). Skipping.", today_str)
        return

    # ── Guard: simulation complete ────────────────────────────────────
    if meta["is_complete"]:
        log.info("Simulation already completed after %d days.", meta["days_elapsed"])
        return

    # ── Initialise on Day 1 ───────────────────────────────────────────
    if meta["started_at"] is None:
        meta["started_at"] = today_str
        default = config.WATCHED_POOLS[config.DEFAULT_POOL_INDEX]
        meta["current_pool_id"]   = default["id"]
        meta["current_pool_name"] = default["name"]
        log.info("Day 1: starting in %s", default["name"])

    # ── Fetch live APYs ───────────────────────────────────────────────
    raw  = fetch_pool_data()
    pools = enrich_pools(raw)
    api_available = any(p["api_ok"] for p in pools)

    # Find current pool in enriched list
    current_pool = next((p for p in pools if p["id"] == meta["current_pool_id"]), None)

    if api_available and current_pool and current_pool["apy"] > 0:
        current_apy = current_pool["apy"]
        meta["current_apy"] = current_apy
    else:
        # Fallback: carry yesterday's APY
        current_apy = meta.get("current_apy") or 3.0
        log.warning("Using fallback APY %.2f%% for today", current_apy)

    # ── Rebalance decision ────────────────────────────────────────────
    last_move_date = meta.get("last_move_date")
    days_since_move = 999  # treat None as "been a long time"
    if last_move_date:
        days_since_move = (date.today() - date.fromisoformat(last_move_date)).days

    best_pool = find_best_pool(pools) if api_available else None
    move, decision_reason = should_rebalance(
        current_pool_id=meta["current_pool_id"],
        current_apy=current_apy,
        best_pool=best_pool,
        days_since_last_move=days_since_move,
        balance=meta["current_balance"],
    )

    if move and best_pool:
        log.info("REBALANCE → %s (%.2f%%) | %s", best_pool["name"], best_pool["apy"], decision_reason)
        meta["current_pool_id"]   = best_pool["id"]
        meta["current_pool_name"] = best_pool["name"]
        meta["current_apy"]       = best_pool["apy"]
        meta["last_move_date"]    = today_str
        meta["total_moves"]      += 1
        meta["total_simulated_gas_spent"] = round(
            meta["total_simulated_gas_spent"] + config.GAS_COST_USD, 6
        )
        current_apy = best_pool["apy"]

    # ── Accrue daily yield ────────────────────────────────────────────
    gas_deducted = config.GAS_COST_USD if move else 0.0
    daily_yield  = round((meta["current_balance"] * (current_apy / 100)) / 365, 6)
    meta["current_balance"] = round(meta["current_balance"] + daily_yield - gas_deducted, 6)
    meta["days_elapsed"]   += 1

    # ── Benchmarks ────────────────────────────────────────────────────
    # Passive: stay in the default pool forever, no gas
    passive = data["benchmark_passive"]
    passive_apy = current_pool["apy"] if (current_pool and current_pool["apy"] > 0) else current_apy
    passive_yield = round((passive["balance"] * (passive_apy / 100)) / 365, 6)
    passive["balance"]  = round(passive["balance"] + passive_yield, 6)
    passive["last_apy"] = passive_apy

    # Coinbase Lending (fixed APY, no gas, no moves)
    cb = data["benchmark_coinbase"]
    cb_yield    = round((cb["balance"] * (cb["fixed_apy"] / 100)) / 365, 6)
    cb["balance"] = round(cb["balance"] + cb_yield, 6)

    # ── Completion check ──────────────────────────────────────────────
    if meta["days_elapsed"] >= config.SIMULATION_DAYS:
        meta["is_complete"] = True
        log.info("🎉 Simulation complete after %d days!", config.SIMULATION_DAYS)

    # ── Append daily log entry ────────────────────────────────────────
    # Snapshot of every watched pool's live APY for dashboard display
    pool_snapshot = [
        {"id": p["id"], "name": p["name"], "apy": p["apy"], "tvlUsd": p["tvlUsd"]}
        for p in pools
    ]

    entry = {
        "date":             today_str,
        "day":              meta["days_elapsed"],
        "balance":          meta["current_balance"],
        "pool_id":          meta["current_pool_id"],
        "pool_name":        meta["current_pool_name"],
        "apy":              current_apy,
        "daily_yield":      daily_yield,
        "gas_deducted":     gas_deducted,
        "moved":            move,
        "decision_reason":  decision_reason,
        "api_available":    api_available,
        "benchmark_passive":  passive["balance"],
        "benchmark_coinbase": cb["balance"],
        "pool_snapshot":    pool_snapshot,
    }
    data["daily_log"].append(entry)

    # ── Persist ───────────────────────────────────────────────────────
    data["meta"] = meta
    data["benchmark_passive"]  = passive
    data["benchmark_coinbase"] = cb
    save_log(data)

    log.info(
        "Day %d done | Balance $%.2f | APY %.2f%% | Moved=%s | Passive $%.2f | Coinbase $%.2f",
        meta["days_elapsed"],
        meta["current_balance"],
        current_apy,
        move,
        passive["balance"],
        cb["balance"],
    )


if __name__ == "__main__":
    run_daily_simulation()
