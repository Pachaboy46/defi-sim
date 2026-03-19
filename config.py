# ─────────────────────────────────────────────
#  Simulation Configuration
#  All tunable parameters live here.
# ─────────────────────────────────────────────

STARTING_BALANCE = 10_000.00          # USD
SIMULATION_WEEKS = 8
SIMULATION_DAYS  = SIMULATION_WEEKS * 7  # 56

# A rebalance only fires when the new pool beats the current pool by at least
# this many percentage points (guards against thrashing on tiny differences).
REBALANCE_THRESHOLD = 1.5             # APY percentage points

# Minimum days to stay in a pool before considering a move.
# Prevents churning when APY fluctuates day-to-day.
MIN_DAYS_BEFORE_MOVE = 3

# Simulated gas cost per rebalance on Base L2 (round trip, USD).
GAS_COST_USD = 0.08

# Only consider pools with TVL above this — filters out illiquid ghost pools.
MIN_POOL_TVL_USD = 5_000_000

# Break-even guard: only move if gas cost pays itself back within this many days.
MAX_BREAK_EVEN_DAYS = 30

# Benchmark: Coinbase USDC Lending via Morpho (flexible, no lockup, verified 2026-03).
BENCHMARK_COINBASE_APY = 10.3

# DeFiLlama yield API
DEFILLAMA_POOLS_URL   = "https://yields.llama.fi/pools"
API_TIMEOUT_SECONDS   = 10
API_MAX_RETRIES       = 3
API_RETRY_DELAY_SECS  = 5

# ─────────────────────────────────────────────
#  Watched Pools  (verified 2026-03-18 via DeFiLlama API)
#
#  All pools use apyBase only — no reward token dependency.
#  Sorted by TVL descending so index 0 = most liquid = default.
# ─────────────────────────────────────────────
WATCHED_POOLS = [
    {
        "id":       "7820bd3c-461a-4811-9f0b-1d39c1503c3f",
        "name":     "Morpho StEakUSDC",
        "protocol": "morpho-v1",
        "chain":    "Base",
        "symbol":   "STEAKUSDC",
    },
    {
        "id":       "c043062f-fcd6-47aa-b063-70691dc25c1c",
        "name":     "Gauntlet GTUSDA",
        "protocol": "gauntlet",
        "chain":    "Base",
        "symbol":   "GTUSDA",
    },
    {
        "id":       "305edf0e-a304-42db-b2f1-7a427841bc80",
        "name":     "Morpho GTUSDCF",
        "protocol": "morpho-v1",
        "chain":    "Base",
        "symbol":   "GTUSDCF",
    },
    {
        "id":       "bf346d43-ef94-4277-b159-ebadb93caef1",
        "name":     "Morpho BBQUSDC",
        "protocol": "morpho-v1",
        "chain":    "Base",
        "symbol":   "BBQUSDC",
    },
    {
        "id":       "7e0661bf-8cf3-45e6-9424-31916d4c7b84",
        "name":     "Aave v3 USDC",
        "protocol": "aave-v3",
        "chain":    "Base",
        "symbol":   "USDC",
    },
]

# Default pool index (used on Day 1 before any rebalance decision is made).
DEFAULT_POOL_INDEX = 0  # Morpho StEakUSDC — highest TVL
