# DeFi Yield Simulation

Simulates a **$10,000 USDC** position across real stablecoin pools on Base L2 for **8 weeks**.

Fetches live APYs from [DeFiLlama](https://defillama.com/yields), simulates daily rebalancing, and tracks results against two benchmarks:
- **Passive hold** — stay in the starting pool, never move
- **Coinbase Lending** — fixed 10.3% APY benchmark

---

## Live Dashboard

> _Link appears here after Streamlit Cloud deployment_

---

## How It Works

| Component | Description |
|---|---|
| `config.py` | All tunable parameters + verified pool IDs |
| `simulate.py` | Daily runner — fetch APYs, decide rebalance, accrue yield |
| `dashboard.py` | Streamlit web UI |
| `simulation_log.json` | Persistent state (committed by GitHub Actions daily) |
| `.github/workflows/daily_simulate.yml` | Cron job — runs at 08:00 UTC every day |

---

## Setup

### 1. Fix GitHub Actions permissions (one-time)

Go to **Settings → Actions → General → Workflow permissions** → select **"Read and write permissions"** → Save.

Without this the daily commit silently fails.

### 2. Deploy dashboard to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Connect your GitHub account
3. New app → select this repo → main branch → `dashboard.py`
4. Deploy

### 3. Trigger first run

GitHub → **Actions** tab → **Daily Simulation Run** → **Run workflow**

---

## Pool Selection (as of 2026-03-18)

All pools use `apyBase` only — no reward token dependency.

| Pool | Protocol | TVL | Typical APY |
|---|---|---|---|
| STEAKUSDC | Morpho v1 | ~$420M | ~3.6% |
| GTUSDA | Gauntlet | ~$81M | ~4.2% |
| GTUSDCF | Morpho v1 | ~$14M | ~3.9% |
| BBQUSDC | Morpho v1 | ~$13M | ~4.1% |
| USDC | Aave v3 | ~$97M | ~2.6% |

---

## Rebalance Rules

A move only fires when **all** of these pass:
1. Best available pool beats current by ≥ 1.5 percentage points
2. At least 3 days since last move
3. Gas break-even ≤ 30 days (at $0.08 simulated gas)
4. Best pool TVL ≥ $5M

---

## Local Development

```bash
pip install -r requirements.txt
python simulate.py           # run one day manually
streamlit run dashboard.py   # view dashboard locally
```
