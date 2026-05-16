from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StrategySpec:
    name: str
    signal_col: str
    description: str
    top_n: int = 10
    keep_rank: int = 15
    hold_days: int = 6
    use_market_gate: bool = False
    market_gate_col: str | None = None
    exposure_col: str | None = None
    weighting: str = "equal"
    weight_floor: float | None = None
    weight_cap: float | None = None
    drawdown_pause: bool = False
    pause_window: int = 3
    pause_threshold: float = -0.06
    replace_blocked_buys: bool = False
    sell_delay_on_limit_down: bool = False
    max_sell_delay_days: int = 0


SCENARIOS = {
    "base": {"buy_fee": 0.00025, "sell_fee": 0.00025, "stamp_duty": 0.00100, "slippage": 0.00050},
    "conservative": {"buy_fee": 0.00025, "sell_fee": 0.00025, "stamp_duty": 0.00100, "slippage": 0.00150},
    "stress": {"buy_fee": 0.00035, "sell_fee": 0.00035, "stamp_duty": 0.00100, "slippage": 0.00250},
}


def _max_drawdown(nav: pd.Series) -> float:
    peak = nav.cummax()
    return float((nav / peak - 1.0).min())


def _choose_targets(day: pd.DataFrame, holdings: set[str], top_n: int, keep_rank: int) -> tuple[list[str], list[str], list[str]]:
    ranked = day.sort_values("signal", ascending=False).reset_index(drop=True)
    ranked["rank_pos"] = np.arange(1, len(ranked) + 1)
    keep_candidates = set(ranked.loc[ranked["rank_pos"] <= keep_rank, "stock_code"])
    final = [code for code in holdings if code in keep_candidates]
    for code in ranked.loc[ranked["rank_pos"] <= top_n, "stock_code"]:
        if len(final) >= top_n:
            break
        if code not in final:
            final.append(code)
    if len(final) < top_n:
        for code in ranked["stock_code"]:
            if len(final) >= top_n:
                break
            if code not in final:
                final.append(code)
    final_set = set(final)
    buys = [code for code in final if code not in holdings]
    sells = [code for code in holdings if code not in final_set]
    return final, buys, sells


def _replace_blocked_buys(day: pd.DataFrame, final: list[str], holdings: set[str], top_n: int) -> list[str]:
    ranked = day.sort_values("signal", ascending=False)
    final_set = set(final)
    blocked = set(
        ranked.loc[
            ranked["stock_code"].isin(final_set - holdings)
            & ranked["next_limit_up"].notna()
            & (ranked["next_open"] >= ranked["next_limit_up"]),
            "stock_code",
        ]
    )
    if not blocked:
        return final

    adjusted = [code for code in final if code not in blocked]
    adjusted_set = set(adjusted)
    for _, row in ranked.iterrows():
        code = row["stock_code"]
        if len(adjusted) >= top_n:
            break
        if code in adjusted_set:
            continue
        is_new = code not in holdings
        is_blocked = bool(
            is_new
            and pd.notna(row["next_limit_up"])
            and pd.notna(row["next_open"])
            and row["next_open"] >= row["next_limit_up"]
        )
        if is_blocked:
            continue
        adjusted.append(code)
        adjusted_set.add(code)
    return adjusted


def _portfolio_weights(chosen: pd.DataFrame, spec: StrategySpec) -> pd.Series:
    if chosen.empty:
        return pd.Series(dtype=float)

    if spec.weighting == "legacy_cap_floor":
        cap = spec.weight_cap if spec.weight_cap is not None else 0.28
        floor = spec.weight_floor if spec.weight_floor is not None else 0.02
        raw = chosen["signal"].astype(float).to_numpy()
        shifted = raw - np.nanmin(raw) + 1e-6
        if not np.isfinite(shifted).all() or float(np.nansum(shifted)) <= 0.0:
            return pd.Series(1.0 / len(chosen), index=chosen.index)
        base = shifted / np.nansum(shifted)
        residual = 1.0 - floor * len(base)
        weights = floor + residual * base
        for _ in range(50):
            over = weights > cap
            if not over.any():
                break
            excess = float((weights[over] - cap).sum())
            weights[over] = cap
            free = (weights > floor + 1e-12) & (weights < cap - 1e-12)
            if not free.any() or excess <= 1e-12:
                break
            alloc = weights[free] - floor
            denom = float(alloc.sum())
            if denom <= 1e-12:
                break
            weights[free] += excess * (alloc / denom)
        weights = weights / weights.sum()
        return pd.Series(weights, index=chosen.index)

    if spec.weighting == "inverse_vol":
        raw = 1.0 / chosen["volatility_20"].replace(0.0, np.nan)
    elif spec.weighting in {"signal", "signal_cap_floor"}:
        raw = chosen["signal"] - chosen["signal"].min() + 1e-6
    else:
        raw = pd.Series(1.0, index=chosen.index)

    raw = raw.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if float(raw.sum()) <= 0.0:
        weights = pd.Series(1.0 / len(chosen), index=chosen.index)
    else:
        weights = raw / raw.sum()

    if spec.weighting == "signal_cap_floor":
        floor = spec.weight_floor if spec.weight_floor is not None else 0.03
        cap = spec.weight_cap if spec.weight_cap is not None else 0.18
        weights = weights.clip(lower=floor, upper=cap)
        weights = weights / weights.sum()
    return weights


def _resolve_exit_prices(
    chosen: pd.DataFrame,
    spec: StrategySpec,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    exit_price = chosen["exit_close"].astype(float).copy()
    sell_blocked = pd.Series(False, index=chosen.index)
    sell_delay_days = pd.Series(0, index=chosen.index, dtype=int)
    unresolved = pd.Series(False, index=chosen.index)

    if not spec.sell_delay_on_limit_down or spec.max_sell_delay_days <= 0 or "exit_limit_down" not in chosen.columns:
        return exit_price, sell_blocked, sell_delay_days, unresolved

    exit_limit_down = pd.to_numeric(chosen["exit_limit_down"], errors="coerce")
    blocked = exit_limit_down.notna() & (chosen["exit_close"].astype(float) <= exit_limit_down + 1e-12)
    if not blocked.any():
        return exit_price, sell_blocked, sell_delay_days, unresolved

    sell_blocked = blocked.copy()
    remaining = blocked.copy()
    last_open_col = None

    for delay in range(1, spec.max_sell_delay_days + 1):
        open_col = f"exit_next_open_d{delay}"
        limit_down_col = f"exit_next_limit_down_d{delay}"
        if open_col not in chosen.columns:
            break
        last_open_col = open_col
        future_open = pd.to_numeric(chosen[open_col], errors="coerce")
        future_limit_down = pd.to_numeric(chosen.get(limit_down_col), errors="coerce")
        tradable = remaining & future_open.notna() & (future_limit_down.isna() | (future_open > future_limit_down + 1e-12))
        if tradable.any():
            exit_price.loc[tradable] = future_open.loc[tradable]
            sell_delay_days.loc[tradable] = delay
            remaining = remaining & ~tradable

    unresolved = remaining.copy()
    if unresolved.any() and last_open_col is not None:
        fallback_open = pd.to_numeric(chosen[last_open_col], errors="coerce")
        fallback_mask = unresolved & fallback_open.notna()
        if fallback_mask.any():
            exit_price.loc[fallback_mask] = fallback_open.loc[fallback_mask]
            sell_delay_days.loc[fallback_mask] = spec.max_sell_delay_days

    return exit_price, sell_blocked, sell_delay_days, unresolved


def run_strategy_backtest(
    panel: pd.DataFrame,
    spec: StrategySpec,
    scenario_name: str = "base",
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    scenario = SCENARIOS[scenario_name]
    exit_col = f"exit_close_{spec.hold_days}"
    all_dates = sorted(pd.to_datetime(panel["trade_date"]).drop_duplicates().tolist())
    required = ["trade_date", "stock_code", "next_open", "next_limit_up", exit_col, spec.signal_col]
    rename_map = {spec.signal_col: "signal", exit_col: "exit_close"}
    if spec.sell_delay_on_limit_down:
        exit_limit_down_col = f"exit_limit_down_{spec.hold_days}"
        required.append(exit_limit_down_col)
        rename_map[exit_limit_down_col] = "exit_limit_down"
        for delay in range(1, spec.max_sell_delay_days + 1):
            open_col = f"exit_next_open_{spec.hold_days}_d{delay}"
            limit_down_col = f"exit_next_limit_down_{spec.hold_days}_d{delay}"
            required.extend([open_col, limit_down_col])
            rename_map[open_col] = f"exit_next_open_d{delay}"
            rename_map[limit_down_col] = f"exit_next_limit_down_d{delay}"
    gate_col = spec.market_gate_col or ("risk_on_gate" if spec.use_market_gate else None)
    if gate_col:
        required.append(gate_col)
    if spec.exposure_col:
        required.append(spec.exposure_col)
    if spec.weighting == "inverse_vol":
        required.append("volatility_20")
    work = panel[required].copy()
    work = work.rename(columns=rename_map)
    work["stock_code"] = work["stock_code"].astype(str).str.upper()
    work = work.dropna(subset=["next_open", "exit_close", "signal"])

    dates = all_dates
    rebalance_dates = dates[:: spec.hold_days]

    holdings: set[str] = set()
    nav = 1.0
    rows: list[dict] = []
    trade_rows: list[dict] = []
    pause_remaining = 0

    for dt in rebalance_dates:
        day = work[work["trade_date"] == dt].copy()
        if day.empty:
            sell_ratio = len(holdings) / max(1, spec.top_n)
            total_cost = (scenario["sell_fee"] + scenario["stamp_duty"] + scenario["slippage"]) * sell_ratio
            nav *= 1.0 - total_cost
            rows.append({"trade_date": dt, "year": pd.Timestamp(dt).year, "net_return": -total_cost, "cost": total_cost, "nav": nav, "active": 0, "paused": 0, "exposure": 0.0})
            holdings = set()
            continue

        if pause_remaining > 0:
            sell_ratio = len(holdings) / max(1, spec.top_n)
            total_cost = (scenario["sell_fee"] + scenario["stamp_duty"] + scenario["slippage"]) * sell_ratio
            nav *= 1.0 - total_cost
            rows.append({"trade_date": dt, "year": pd.Timestamp(dt).year, "net_return": -total_cost, "cost": total_cost, "nav": nav, "active": 0, "paused": 1, "exposure": 0.0})
            holdings = set()
            pause_remaining -= 1
            continue

        gate_ok = True
        if gate_col:
            gate_ok = bool(day[gate_col].dropna().iloc[0]) if not day[gate_col].dropna().empty else False
        if not gate_ok:
            sell_ratio = len(holdings) / max(1, spec.top_n)
            total_cost = (scenario["sell_fee"] + scenario["stamp_duty"] + scenario["slippage"]) * sell_ratio
            nav *= 1.0 - total_cost
            rows.append({"trade_date": dt, "year": pd.Timestamp(dt).year, "net_return": -total_cost, "cost": total_cost, "nav": nav, "active": 0, "paused": 0, "exposure": 0.0})
            holdings = set()
            continue

        exposure = 1.0
        if spec.exposure_col:
            exposure_values = day[spec.exposure_col].dropna()
            exposure = float(exposure_values.iloc[0]) if not exposure_values.empty else 1.0
            exposure = min(max(exposure, 0.0), 1.0)
        if exposure <= 0.0:
            sell_ratio = len(holdings) / max(1, spec.top_n)
            total_cost = (scenario["sell_fee"] + scenario["stamp_duty"] + scenario["slippage"]) * sell_ratio
            nav *= 1.0 - total_cost
            rows.append({"trade_date": dt, "year": pd.Timestamp(dt).year, "net_return": -total_cost, "cost": total_cost, "nav": nav, "active": 0, "paused": 0, "exposure": 0.0})
            holdings = set()
            continue

        prev_holdings = set(holdings)
        final, buys, sells = _choose_targets(day, holdings, spec.top_n, spec.keep_rank)
        if spec.replace_blocked_buys:
            final = _replace_blocked_buys(day, final, holdings, spec.top_n)
            final_set = set(final)
            buys = [code for code in final if code not in holdings]
            sells = [code for code in holdings if code not in final_set]
        chosen = day[day["stock_code"].isin(final)].copy()
        if chosen.empty:
            sell_ratio = len(holdings) / max(1, spec.top_n)
            total_cost = (scenario["sell_fee"] + scenario["stamp_duty"] + scenario["slippage"]) * sell_ratio
            nav *= 1.0 - total_cost
            rows.append({"trade_date": dt, "year": pd.Timestamp(dt).year, "net_return": -total_cost, "cost": total_cost, "nav": nav, "active": 0, "paused": 0, "exposure": 0.0})
            holdings = set()
            continue

        chosen["is_new_buy"] = ~chosen["stock_code"].isin(prev_holdings)
        chosen["buy_blocked"] = chosen["is_new_buy"] & chosen["next_limit_up"].notna() & (chosen["next_open"] >= chosen["next_limit_up"])
        exit_price, sell_blocked, sell_delay_days, unresolved_sell_blocked = _resolve_exit_prices(chosen, spec)
        chosen["exit_price_exec"] = exit_price
        chosen["sell_blocked"] = sell_blocked
        chosen["sell_delay_days"] = sell_delay_days
        chosen["unresolved_sell_blocked"] = unresolved_sell_blocked
        chosen["gross_return"] = np.where(
            chosen["buy_blocked"],
            0.0,
            chosen["exit_price_exec"].astype(float) / chosen["next_open"].astype(float) - 1.0,
        )
        chosen["weight"] = _portfolio_weights(chosen, spec)
        gross = float((chosen["gross_return"] * chosen["weight"]).sum()) * exposure
        executed_buys = int((~chosen["buy_blocked"] & chosen["is_new_buy"]).sum())
        buy_ratio = executed_buys / max(1, spec.top_n)
        sell_ratio = len(sells) / max(1, spec.top_n)
        total_cost = (scenario["buy_fee"] + scenario["slippage"]) * buy_ratio + (
            scenario["sell_fee"] + scenario["stamp_duty"] + scenario["slippage"]
        ) * sell_ratio
        total_cost *= exposure
        net = gross - total_cost
        nav *= 1.0 + net

        rows.append(
            {
                "trade_date": dt,
                "year": pd.Timestamp(dt).year,
                "gross_return": gross,
                "cost": total_cost,
                "net_return": net,
                "nav": nav,
                "active": int(exposure > 0),
                "paused": 0,
                "exposure": exposure,
                "buy_count": len(buys),
                "executed_buy_count": executed_buys,
                "sell_count": len(sells),
                "buy_blocked_count": int(chosen["buy_blocked"].sum()),
                "sell_blocked_count": int(chosen["sell_blocked"].sum()),
                "unresolved_sell_blocked_count": int(chosen["unresolved_sell_blocked"].sum()),
                "avg_sell_delay_days": float(chosen["sell_delay_days"].mean()),
            }
        )
        for _, row in chosen.iterrows():
            trade_rows.append(
                {
                    "trade_date": dt,
                    "stock_code": row["stock_code"],
                    "signal": row["signal"],
                    "weight": row["weight"],
                    "next_open": row["next_open"],
                    "exit_close": row["exit_close"],
                    "exit_price_exec": row["exit_price_exec"],
                    "gross_return": row["gross_return"],
                    "is_new_buy": bool(row["is_new_buy"]),
                    "buy_blocked": bool(row["buy_blocked"]),
                    "sell_blocked": bool(row["sell_blocked"]),
                    "sell_delay_days": int(row["sell_delay_days"]),
                    "unresolved_sell_blocked": bool(row["unresolved_sell_blocked"]),
                }
            )
        holdings = set(chosen.loc[~chosen["buy_blocked"], "stock_code"].astype(str))
        if spec.drawdown_pause and len(rows) >= spec.pause_window:
            recent = pd.Series([r.get("net_return", 0.0) for r in rows[-spec.pause_window:]], dtype=float)
            if float((1.0 + recent).prod() - 1.0) <= spec.pause_threshold:
                pause_remaining = 1

    detail = pd.DataFrame(rows)
    trades = pd.DataFrame(trade_rows)
    if detail.empty:
        return detail, {}, trades

    yearly = detail.groupby("year")["net_return"].apply(lambda s: float((1.0 + s).prod() - 1.0)).reset_index(name="year_return")
    start = pd.Timestamp(detail["trade_date"].min())
    end = pd.Timestamp(detail["trade_date"].max())
    years = max((end - start).days / 365.25, 1.0 / 12.0)
    ending_nav = float(detail["nav"].iloc[-1])
    cagr = ending_nav ** (1.0 / years) - 1.0 if ending_nav > 0 else -1.0
    vol = float(detail["net_return"].std(ddof=1) * (245 / spec.hold_days) ** 0.5) if len(detail) > 1 else np.nan
    summary = {
        "strategy": spec.name,
        "description": spec.description,
        "signal_col": spec.signal_col,
        "scenario": scenario_name,
        "top_n": spec.top_n,
        "keep_rank": spec.keep_rank,
        "hold_days": spec.hold_days,
        "use_market_gate": spec.use_market_gate,
        "market_gate_col": gate_col or "",
        "exposure_col": spec.exposure_col or "",
        "weighting": spec.weighting,
        "drawdown_pause": spec.drawdown_pause,
        "replace_blocked_buys": spec.replace_blocked_buys,
        "sell_delay_on_limit_down": spec.sell_delay_on_limit_down,
        "max_sell_delay_days": spec.max_sell_delay_days,
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "calendar_cagr": cagr,
        "annualized_vol": vol,
        "sharpe_like": cagr / vol if vol and not np.isnan(vol) else np.nan,
        "max_drawdown": _max_drawdown(detail["nav"]),
        "ending_nav": ending_nav,
        "periods": int(len(detail)),
        "active_periods": int(detail["active"].sum()),
        "active_ratio": float(detail["active"].mean()),
        "positive_year_ratio": float((yearly["year_return"] > 0).mean()),
        "worst_year_return": float(yearly["year_return"].min()),
        "best_year_return": float(yearly["year_return"].max()),
        "mean_year_return": float(yearly["year_return"].mean()),
        "avg_cost": float(detail.get("cost", pd.Series(dtype=float)).fillna(0).mean()),
        "avg_buy_blocked": float(detail.get("buy_blocked_count", pd.Series(dtype=float)).fillna(0).mean()),
        "avg_sell_blocked": float(detail.get("sell_blocked_count", pd.Series(dtype=float)).fillna(0).mean()),
        "avg_unresolved_sell_blocked": float(detail.get("unresolved_sell_blocked_count", pd.Series(dtype=float)).fillna(0).mean()),
        "avg_sell_delay_days": float(detail.get("avg_sell_delay_days", pd.Series(dtype=float)).fillna(0).mean()),
        "avg_exposure": float(detail.get("exposure", pd.Series(dtype=float)).fillna(0).mean()),
        "paused_periods": int(detail.get("paused", pd.Series(dtype=float)).fillna(0).sum()),
    }
    return detail, summary, trades


def factor_ic_summary(panel: pd.DataFrame, factor_cols: list[str], hold_days: int = 6) -> pd.DataFrame:
    exit_col = f"exit_close_{hold_days}"
    work = panel[["trade_date", "stock_code", "next_open", exit_col] + factor_cols].copy()
    work["fwd_return"] = work[exit_col] / work["next_open"] - 1.0
    rows = []
    for factor in factor_cols:
        ic = (
            work.dropna(subset=[factor, "fwd_return"])
            .groupby("trade_date")
            .apply(lambda g: g[factor].corr(g["fwd_return"], method="spearman") if len(g) >= 30 else np.nan)
            .dropna()
        )
        rows.append(
            {
                "factor": factor,
                "ic_mean": float(ic.mean()) if not ic.empty else np.nan,
                "ic_std": float(ic.std(ddof=1)) if len(ic) > 1 else np.nan,
                "ic_ir": float(ic.mean() / ic.std(ddof=1)) if len(ic) > 1 and ic.std(ddof=1) else np.nan,
                "positive_ic_ratio": float((ic > 0).mean()) if not ic.empty else np.nan,
                "observations": int(len(ic)),
            }
        )
    return pd.DataFrame(rows)
