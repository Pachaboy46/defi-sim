"""
dashboard.py — Streamlit web dashboard.

Run locally:  streamlit run dashboard.py
Deployed via: Streamlit Cloud → connect GitHub → select this file.
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config

# ─────────────────────────────────────────────
LOG_FILE = Path(__file__).parent / "simulation_log.json"

st.set_page_config(
    page_title="DeFi Yield Sim",
    page_icon="📈",
    layout="wide",
)


# ─────────────────────────────────────────────
#  Data Loader
# ─────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_data() -> dict:
    if not LOG_FILE.exists():
        return {}
    with open(LOG_FILE, "r") as fh:
        return json.load(fh)


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def fmt_usd(val: float) -> str:
    return f"${val:,.2f}"


def delta_str(current: float, start: float) -> str:
    diff = current - start
    pct  = (diff / start) * 100
    sign = "+" if diff >= 0 else ""
    return f"{sign}{fmt_usd(diff)} ({sign}{pct:.2f}%)"


# ─────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────

def main() -> None:
    data = load_data()

    # ── Empty state ───────────────────────────────────────────────────
    if not data or not data.get("daily_log"):
        st.title("📈 DeFi Yield Simulation")
        st.info(
            "Simulation hasn't started yet. "
            "The first run will happen automatically at 08:00 UTC, "
            "or trigger it manually via GitHub Actions → Run workflow."
        )
        return

    meta      = data["meta"]
    daily_log = data["daily_log"]
    df        = pd.DataFrame(daily_log)

    days_elapsed  = meta["days_elapsed"]
    days_total    = config.SIMULATION_DAYS
    is_complete   = meta["is_complete"]
    start_balance = config.STARTING_BALANCE

    # ── Header ────────────────────────────────────────────────────────
    st.title("📈 DeFi Yield Simulation — $10,000 USDC on Base")
    status_label = "✅ Complete" if is_complete else "🟢 Running"
    st.caption(
        f"Day **{days_elapsed}** of **{days_total}** &nbsp;|&nbsp; "
        f"Started **{meta['started_at']}** &nbsp;|&nbsp; {status_label}"
    )
    st.divider()

    # ── Metric cards ─────────────────────────────────────────────────
    agent_bal   = meta["current_balance"]
    passive_bal = data["benchmark_passive"]["balance"]
    cb_bal      = data["benchmark_coinbase"]["balance"]

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric(
            "🤖 Agent (active)",
            fmt_usd(agent_bal),
            delta_str(agent_bal, start_balance),
        )
    with c2:
        st.metric(
            "😴 Passive hold",
            fmt_usd(passive_bal),
            delta_str(passive_bal, start_balance),
        )
    with c3:
        st.metric(
            "🏦 Coinbase Lending (10.3%)",
            fmt_usd(cb_bal),
            delta_str(cb_bal, start_balance),
        )

    st.divider()

    # ── Balance chart ─────────────────────────────────────────────────
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["balance"],
        name="Agent", line=dict(color="#00b4d8", width=2),
        hovertemplate="Agent: $%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["benchmark_passive"],
        name="Passive hold", line=dict(color="#90e0ef", width=1.5, dash="dot"),
        hovertemplate="Passive: $%{y:,.2f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["benchmark_coinbase"],
        name="Coinbase 10.3%", line=dict(color="#ffd166", width=1.5, dash="dash"),
        hovertemplate="Coinbase: $%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        title="Balance over time",
        xaxis_title="Date",
        yaxis_title="USD",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hovermode="x unified",
        height=380,
        margin=dict(t=60, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── APY chart ─────────────────────────────────────────────────────
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["date"], y=df["apy"],
        name="Agent APY", line=dict(color="#06d6a0", width=1.5),
        hovertemplate="APY: %{y:.2f}%<extra></extra>",
    ))
    fig2.add_hline(
        y=config.BENCHMARK_COINBASE_APY,
        line_dash="dash", line_color="#ffd166",
        annotation_text=f"Coinbase {config.BENCHMARK_COINBASE_APY}%",
        annotation_position="top right",
    )
    fig2.update_layout(
        title="Daily APY — Agent vs Coinbase benchmark",
        xaxis_title="Date",
        yaxis_title="APY %",
        height=280,
        margin=dict(t=60, b=40),
    )
    st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # ── Current position ──────────────────────────────────────────────
    st.subheader("Current position")
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Pool", meta["current_pool_name"])
    p2.metric("APY (live)", f"{meta['current_apy']:.2f}%" if meta.get("current_apy") else "—")
    p3.metric("Total moves", meta["total_moves"])
    p4.metric("Gas spent (sim)", fmt_usd(meta["total_simulated_gas_spent"]))

    st.divider()

    # ── Today's pool snapshot ─────────────────────────────────────────
    st.subheader("Today's pool APY snapshot")
    if daily_log and daily_log[-1].get("pool_snapshot"):
        snap = daily_log[-1]["pool_snapshot"]
        snap_df = pd.DataFrame(snap)[["name", "apy", "tvlUsd"]]
        snap_df.columns = ["Pool", "APY %", "TVL USD"]
        snap_df["TVL USD"] = snap_df["TVL USD"].apply(lambda x: f"${x:,.0f}")
        snap_df["APY %"]   = snap_df["APY %"].apply(lambda x: f"{x:.2f}%")
        # Highlight active pool
        active_id = meta["current_pool_id"]
        active_names = [p["name"] for p in daily_log[-1]["pool_snapshot"] if p["id"] == active_id]

        def highlight_active(row):
            style = "background-color: #1a3a4a; font-weight: bold" if row["Pool"] in active_names else ""
            return [style] * len(row)

        st.dataframe(
            snap_df.style.apply(highlight_active, axis=1),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.caption("Pool snapshot not available for today.")

    st.divider()

    # ── Decision log ──────────────────────────────────────────────────
    st.subheader("Daily decision log")
    with st.expander("Show last 14 days", expanded=True):
        log_cols = ["date", "day", "balance", "pool_name", "apy", "daily_yield",
                    "gas_deducted", "moved", "decision_reason"]
        visible_cols = [c for c in log_cols if c in df.columns]
        recent = df[visible_cols].tail(14).copy()
        recent["balance"]     = recent["balance"].apply(fmt_usd)
        recent["daily_yield"] = recent["daily_yield"].apply(lambda x: f"${x:.4f}")
        recent["apy"]         = recent["apy"].apply(lambda x: f"{x:.2f}%")
        st.dataframe(recent.iloc[::-1], use_container_width=True, hide_index=True)

    st.divider()

    # ── Run statistics ────────────────────────────────────────────────
    st.subheader("Run statistics")
    s1, s2, s3, s4, s5 = st.columns(5)
    total_yield = agent_bal - start_balance - meta["total_simulated_gas_spent"]
    avg_apy     = df["apy"].mean() if len(df) else 0
    best_apy    = df["apy"].max()  if len(df) else 0
    worst_apy   = df["apy"].min()  if len(df) else 0
    s1.metric("Avg APY (agent)",   f"{avg_apy:.2f}%")
    s2.metric("Best APY seen",     f"{best_apy:.2f}%")
    s3.metric("Worst APY seen",    f"{worst_apy:.2f}%")
    s4.metric("Total yield earned", fmt_usd(total_yield))
    s5.metric("vs Passive",        delta_str(agent_bal, passive_bal))

    # ── 10-Year Projection (only after simulation ends) ───────────────
    if is_complete:
        st.divider()
        st.subheader("10-Year projection (based on simulation avg APY)")
        st.caption(
            f"Assumes average APY of **{avg_apy:.2f}%** sustained over 10 years "
            f"with no monthly contributions, daily compounding."
        )

        def project(principal: float, apy: float, years: int = 10) -> float:
            daily_rate = apy / 100 / 365
            return principal * ((1 + daily_rate) ** (years * 365))

        capitals = [100, 500, 1_000, 5_000, 10_000]
        rows = []
        for cap in capitals:
            end_val = project(cap, avg_apy)
            rows.append({
                "Starting capital": fmt_usd(cap),
                "End value (10yr)":  fmt_usd(end_val),
                "Total gain":        fmt_usd(end_val - cap),
                "Multiplier":        f"{end_val / cap:.1f}×",
            })
        proj_df = pd.DataFrame(rows)
        st.dataframe(proj_df, use_container_width=True, hide_index=True)

        if avg_apy < config.BENCHMARK_COINBASE_APY:
            st.warning(
                f"⚠️ The agent's average APY ({avg_apy:.2f}%) was **below** the Coinbase "
                f"Lending benchmark ({config.BENCHMARK_COINBASE_APY}%). "
                "Consider whether active rebalancing adds enough value to justify complexity."
            )
        else:
            st.success(
                f"✅ The agent outperformed the passive Coinbase benchmark "
                f"({avg_apy:.2f}% vs {config.BENCHMARK_COINBASE_APY}%)."
            )


if __name__ == "__main__":
    main()
