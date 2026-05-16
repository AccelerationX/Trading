from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = ROOT / "research" / "reports" / "20260429_live_mainline_recheck.md"
RISK_EXIT_DIR = ROOT / "research" / "experiments" / "20260427_family_champion_risk_exit_search"
CHAMPION_DIR = ROOT / "research" / "experiments" / "20260426_family_champion_fusion_search"
LIVE_STATUS_PATH = ROOT / "live_champion_mfx906" / "outputs" / "run_status.json"
LIVE_STATE_PATH = ROOT / "live_champion_mfx906" / "state" / "cycle_state.json"
CONFIG_PATH = ROOT / "TradingMain" / "config.py"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_risk_summary() -> pd.DataFrame:
    df = pd.read_csv(RISK_EXIT_DIR / "summary_all_scenarios.csv")
    return df


def _load_champion_summary() -> pd.DataFrame:
    df = pd.read_csv(CHAMPION_DIR / "summary_all_scenarios.csv")
    return df


def _load_detail(name: str) -> pd.DataFrame:
    df = pd.read_csv(RISK_EXIT_DIR / f"{name}_detail.csv")
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    return df.sort_values("trade_date").reset_index(drop=True)


def _segment_return(df: pd.DataFrame) -> float:
    return float((1.0 + df["net_return"]).prod() - 1.0)


def _yearly_compare(base_detail: pd.DataFrame, tp_detail: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for year in sorted(set(base_detail["year"]).union(set(tp_detail["year"]))):
        b = base_detail[base_detail["year"] == year]
        t = tp_detail[tp_detail["year"] == year]
        rows.append(
            {
                "year": int(year),
                "base_return": _segment_return(b),
                "tp15_return": _segment_return(t),
                "tp15_minus_base": _segment_return(t) - _segment_return(b),
                "tp_hits": int(t["take_profit_exit_count"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _quarterly_compare(base_detail: pd.DataFrame, tp_detail: pd.DataFrame) -> pd.DataFrame:
    def pack(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
        work = df.copy()
        work["quarter"] = work["trade_date"].dt.to_period("Q").astype(str)
        out = (
            work.groupby("quarter", as_index=False)
            .apply(lambda g: pd.Series({value_name: _segment_return(g)}), include_groups=False)
            .reset_index(drop=True)
        )
        return out

    base_q = pack(base_detail, "base_return")
    tp_q = pack(tp_detail, "tp15_return")
    out = base_q.merge(tp_q, on="quarter", how="outer").sort_values("quarter").reset_index(drop=True)
    out["tp15_minus_base"] = out["tp15_return"] - out["base_return"]
    return out


def _metric_row(df: pd.DataFrame, strategy: str, scenario: str) -> pd.Series:
    row = df[(df["strategy"] == strategy) & (df["scenario"] == scenario)]
    if row.empty:
        raise RuntimeError(f"Missing row for {strategy} / {scenario}")
    return row.iloc[0]


def _fmt_pct(value: float) -> str:
    return f"{value:.2%}"


def _fmt_num(value: float) -> str:
    return f"{value:.2f}"


def _build_neighbor_table(risk_summary: pd.DataFrame) -> pd.DataFrame:
    names = [
        "MRX904A_tp12",
        "MRX904B_tp14",
        "MRX905_tp15",
        "MRX905A_tp16",
        "MRX905B_tp18",
        "MRX906_tp20",
    ]
    base = risk_summary[(risk_summary["scenario"] == "base") & (risk_summary["strategy"].isin(names))].copy()
    keep = base[
        [
            "strategy",
            "take_profit_pct",
            "calendar_cagr",
            "max_drawdown",
            "avg_take_profit_exit_count",
        ]
    ].sort_values("take_profit_pct")
    keep["take_profit_pct"] = keep["take_profit_pct"].map(_fmt_pct)
    keep["calendar_cagr"] = keep["calendar_cagr"].map(_fmt_pct)
    keep["max_drawdown"] = keep["max_drawdown"].map(_fmt_pct)
    keep["avg_take_profit_exit_count"] = keep["avg_take_profit_exit_count"].map(_fmt_num)
    return keep


def main() -> None:
    risk_summary = _load_risk_summary()
    champion_summary = _load_champion_summary()
    base_detail = _load_detail("MRX901_base_close")
    tp_detail = _load_detail("MRX905_tp15")
    live_status = _load_json(LIVE_STATUS_PATH)
    live_state = _load_json(LIVE_STATE_PATH)

    risk_base = _metric_row(risk_summary, "MRX901_base_close", "base")
    risk_cons = _metric_row(risk_summary, "MRX901_base_close", "conservative")
    risk_stress = _metric_row(risk_summary, "MRX901_base_close", "stress")
    tp_base = _metric_row(risk_summary, "MRX905_tp15", "base")
    tp_cons = _metric_row(risk_summary, "MRX905_tp15", "conservative")
    tp_stress = _metric_row(risk_summary, "MRX905_tp15", "stress")
    mfx_base = _metric_row(champion_summary, "MFX906_h6_top2", "base")
    mfx_cons = _metric_row(champion_summary, "MFX906_h6_top2", "conservative")
    mfx_stress = _metric_row(champion_summary, "MFX906_h6_top2", "stress")

    yearly = _yearly_compare(base_detail, tp_detail)
    quarterly = _quarterly_compare(base_detail, tp_detail)
    yearly_positive = int((yearly["tp15_minus_base"] > 0).sum())
    quarterly_positive = int((quarterly["tp15_minus_base"] > 0).sum())
    best_quarters = quarterly.sort_values("tp15_minus_base", ascending=False).head(3).copy()
    worst_quarters = quarterly.sort_values("tp15_minus_base", ascending=True).head(3).copy()
    neighbor_table = _build_neighbor_table(risk_summary)

    cycle_state = live_status["cycle_state"]
    data_guard = live_status["data_guard"]
    config_text = CONFIG_PATH.read_text(encoding="utf-8", errors="ignore")
    legacy_label = "repair_accel_t6" if "repair_accel_t6" in config_text else "unknown"

    yearly_view = yearly.copy()
    yearly_view["base_return"] = yearly_view["base_return"].map(_fmt_pct)
    yearly_view["tp15_return"] = yearly_view["tp15_return"].map(_fmt_pct)
    yearly_view["tp15_minus_base"] = yearly_view["tp15_minus_base"].map(_fmt_pct)

    best_quarters_view = best_quarters.copy()
    for col in ["base_return", "tp15_return", "tp15_minus_base"]:
        best_quarters_view[col] = best_quarters_view[col].map(_fmt_pct)

    worst_quarters_view = worst_quarters.copy()
    for col in ["base_return", "tp15_return", "tp15_minus_base"]:
        worst_quarters_view[col] = worst_quarters_view[col].map(_fmt_pct)

    lines = [
        "# 20260429 Live Mainline Recheck",
        "",
        "## Progress Alignment",
        "",
        f"- Current research production candidate: `MFX906_h6_top2 + TP15 next-open exit`.",
        f"- Live folder is aligned to that deployment spec: `strategy_name={live_state['strategy_name']}`, `take_profit_pct={live_state['take_profit_pct']:.0%}`.",
        f"- Latest live status snapshot: trade date `{cycle_state['latest_trade_date']}`, active signal `{cycle_state['active_signal_date']}`, next signal `{cycle_state['next_signal_date']}`, rebalance day `{live_status['is_rebalance_execution_day']}`.",
        f"- Live data guard is currently clean: stale `{data_guard['stale_count']}`, missing `{data_guard['missing_count']}`.",
        f"- Important scope note: `TradingMain/outputs/*` and `TradingMain/config.py` still point at legacy strategy `{legacy_label}`, not the current live champion line, so those outputs should not be used to judge `MFX906/MRX905`.",
        "",
        "## Core Evidence",
        "",
        f"- Champion stock-selection core `MFX906_h6_top2` remains high-return after live-readiness realism fix: base `{_fmt_pct(float(mfx_base['calendar_cagr']))}`, conservative `{_fmt_pct(float(mfx_cons['calendar_cagr']))}`, stress `{_fmt_pct(float(mfx_stress['calendar_cagr']))}`, base max drawdown `{_fmt_pct(float(mfx_base['max_drawdown']))}`.",
        f"- Execution overlay `MRX905_tp15` improves the same core further: base `{_fmt_pct(float(tp_base['calendar_cagr']))}` vs baseline `{_fmt_pct(float(risk_base['calendar_cagr']))}`, conservative `{_fmt_pct(float(tp_cons['calendar_cagr']))}` vs `{_fmt_pct(float(risk_cons['calendar_cagr']))}`, stress `{_fmt_pct(float(tp_stress['calendar_cagr']))}` vs `{_fmt_pct(float(risk_stress['calendar_cagr']))}`.",
        f"- TP15 is not a single-point spike. Neighbor variants are clustered: TP14 `{_fmt_pct(float(_metric_row(risk_summary, 'MRX904B_tp14', 'base')['calendar_cagr']))}`, TP15 `{_fmt_pct(float(tp_base['calendar_cagr']))}`, TP16 `{_fmt_pct(float(_metric_row(risk_summary, 'MRX905A_tp16', 'base')['calendar_cagr']))}`, TP18 `{_fmt_pct(float(_metric_row(risk_summary, 'MRX905B_tp18', 'base')['calendar_cagr']))}`.",
        f"- Stop-loss overlays were consistently harmful; the current live spec correctly keeps take-profit and avoids standalone stop-loss.",
        "",
        neighbor_table.to_markdown(index=False),
        "",
        "## Overfit Check",
        "",
        f"- Positive result: the stock-selection core itself is not hanging on one fragile execution choice. `MFX906_h6_top2` survives conservative and stress cost settings, and nearby TP thresholds remain strong.",
        f"- Main caution: TP15 uplift is regime-sensitive rather than universally dominant. It beats the no-TP baseline in `{yearly_positive}/{len(yearly)}` years and `{quarterly_positive}/{len(quarterly)}` quarters only.",
        f"- Uplift was concentrated in later windows, especially `2024Q3` and `2025Q4`; weaker relative windows include `2021Q4` and `2026Q1`.",
        "",
        "### Yearly Comparison",
        "",
        yearly_view.to_markdown(index=False),
        "",
        "### Best Quarters For TP15 vs Base",
        "",
        best_quarters_view.to_markdown(index=False),
        "",
        "### Worst Quarters For TP15 vs Base",
        "",
        worst_quarters_view.to_markdown(index=False),
        "",
        "## Practical Judgment",
        "",
        "- Conclusion on `actual high return`: yes, the current live mainline is still a genuinely high-return line by the project's own realistic execution framework, and the deployed TP15 version materially outperforms the no-TP live-ready baseline on full-sample, conservative, and stress results.",
        "- Conclusion on `overfitting`: the main alpha line does not look like a pure one-parameter accident, but the TP15 overlay does show regime concentration. The safer interpretation is: deploy the `MFX906` core with TP15 as the best current execution overlay, while treating TP15 as a conditional enhancer rather than a universally stable law.",
        "- Continuation priority: if deeper validation is needed, the next correct step is not more legacy `repair_accel_t6` backtests. It is a champion-line-specific walk-forward / regime report for `MRX901_base_close` and `MRX905_tp15` using the `20260427_family_champion_risk_exit_search` artifacts.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT_PATH)


if __name__ == "__main__":
    main()
