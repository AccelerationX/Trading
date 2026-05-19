from __future__ import annotations

import json
import re
from pathlib import Path

from trading_system.config.paths import OUTPUTS_DIR


def trade_execution_output_dir() -> Path:
    directory = OUTPUTS_DIR / "trade_execution"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_pct_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _normalize_holding_days(days: int) -> str:
    if days <= 1:
        return "1天以内"
    if days <= 3:
        return "1-3天"
    if days <= 5:
        return "3-5天"
    return f"{days}天左右"


def _clean_text(text: object) -> str:
    return str(text or "").strip()


def _reference_price(text: object, fallback: object = None) -> float | None:
    if fallback not in (None, ""):
        try:
            return round(float(fallback), 4)
        except (TypeError, ValueError):
            pass
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", str(text or ""))]
    if len(numbers) >= 2:
        return round((numbers[0] + numbers[1]) / 2.0, 4)
    if numbers:
        return round(numbers[0], 4)
    return None


def build_trade_execution_payload(preopen_payload: dict, account_payload: dict) -> dict:
    trade_date = _clean_text(preopen_payload.get("trade_date"))
    account_view = dict(preopen_payload.get("account_view", {}))
    action_summary = dict(preopen_payload.get("action_summary", {}))
    portfolio = dict(preopen_payload.get("portfolio", {}))
    holdings = list(preopen_payload.get("holding_assessments", []))
    top_new_ideas = list(preopen_payload.get("top_new_ideas", []))
    preferred_days = int(account_payload.get("preferred_holding_horizon_days", 3) or 3)

    buy_orders: list[dict] = []
    sell_orders: list[dict] = []
    hold_orders: list[dict] = []

    for item in top_new_ideas:
        if _clean_text(item.get("action")) != "buy_pilot":
            continue
        instruction = dict(item.get("trade_instruction", {}))
        pilot_shares = instruction.get("pilot_shares")
        if pilot_shares in (None, 0, "", "0"):
            continue
        buy_orders.append(
            {
                "stock_code": _clean_text(item.get("stock_code")),
                "stock_name": _clean_text(item.get("stock_name")),
                "order_action": "buy",
                "target_shares": int(pilot_shares),
                "max_shares": int(instruction.get("max_shares") or pilot_shares),
                "buy_zone": _clean_text(instruction.get("buy_zone")),
                "stop_loss": _clean_text(instruction.get("stop_loss")),
                "take_profit": _clean_text(instruction.get("take_profit")),
                "price_reference": _reference_price(instruction.get("buy_zone"), item.get("last_close_price")),
                "suggested_holding_days": preferred_days,
                "suggested_holding_label": _normalize_holding_days(preferred_days),
                "reason": _clean_text(instruction.get("instruction")) or _clean_text(item.get("candidate_diagnosis")),
                "setup_type": _clean_text(item.get("setup_type")),
                "theme_name": _clean_text(dict(item.get("theme_context", {})).get("theme_name")),
            }
        )

    for item in holdings:
        stock_code = _clean_text(item.get("stock_code"))
        stock_name = _clean_text(item.get("stock_name"))
        summary_action = _clean_text(item.get("summary_action"))
        available_shares = int(item.get("available_shares") or 0)
        recommendation = _clean_text(item.get("recommendation"))
        rationale = _clean_text(item.get("rationale"))
        current_return = item.get("unrealized_return_pct")
        risk_notes = list(item.get("risk_notes", []))

        if summary_action == "reduce_or_exit_review" and available_shares > 0:
            sell_orders.append(
                {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "order_action": "sell",
                    "target_shares": available_shares,
                    "sell_scope": "full_available",
                    "price_reference": _reference_price("", item.get("last_close_price")),
                    "reason": recommendation or "系统不支持继续激进持有，建议卖出可卖部分。",
                    "rationale": rationale,
                    "unrealized_return_pct": current_return,
                    "risk_notes": risk_notes,
                }
            )
            continue

        hold_orders.append(
            {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "order_action": "hold",
                "shares": int(item.get("shares") or 0),
                "available_shares": available_shares,
                "reason": recommendation or "继续观察，不主动操作。",
                "rationale": rationale,
                "unrealized_return_pct": current_return,
            }
        )

    actionable = bool(buy_orders or sell_orders)
    preferred_posture = _clean_text(action_summary.get("preferred_posture"))
    posture_note = _clean_text(action_summary.get("posture_note"))
    if actionable:
        overall_instruction = (
            f"今日执行 {len(buy_orders)} 条买入指令、{len(sell_orders)} 条卖出指令。"
            " 其余标的按持有/观察处理。"
        )
    elif hold_orders:
        overall_instruction = "今日不新增买卖指令，只按持仓观察建议处理现有仓位。"
    else:
        overall_instruction = "今日无明确买卖机会，建议不操作，保持空仓观察。"

    return {
        "trade_date": trade_date,
        "market_close_date": _clean_text(dict(preopen_payload.get("data_basis", {})).get("market_close_date")),
        "profile_name": _clean_text(account_view.get("profile_name")),
        "capital_total": account_view.get("capital_total"),
        "cash_cny": portfolio.get("cash_cny"),
        "preferred_posture": preferred_posture,
        "posture_note": posture_note,
        "overall_instruction": overall_instruction,
        "actionable": actionable,
        "buy_count": len(buy_orders),
        "sell_count": len(sell_orders),
        "hold_count": len(hold_orders),
        "buy_orders": buy_orders,
        "sell_orders": sell_orders,
        "hold_orders": hold_orders,
    }


def save_trade_execution_payload(trade_date: str, payload: dict, path: Path | None = None) -> Path:
    output_path = path or (trade_execution_output_dir() / f"trade_execution_{trade_date}.json")
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def render_trade_execution_markdown(payload: dict) -> str:
    lines = [
        f"# 今日交易指令 - {payload.get('trade_date', '')}",
        "",
        f"- 数据交易日：`{payload.get('market_close_date', '')}`",
        f"- 账户：`{payload.get('profile_name', '')}`",
        f"- 总资金：`{payload.get('capital_total')}`",
        f"- 当前现金：`{payload.get('cash_cny')}`",
        f"- 今日姿态：`{payload.get('preferred_posture', '')}`",
        f"- 姿态说明：{payload.get('posture_note', '') or '无'}",
        "",
        "## 总指令",
        f"- {payload.get('overall_instruction', '')}",
        "",
        "## 买入指令",
    ]

    buy_orders = list(payload.get("buy_orders", []))
    if not buy_orders:
        lines.append("- 无明确买入指令")
    else:
        for index, item in enumerate(buy_orders, start=1):
            lines.extend(
                [
                    f"### BUY {index}: {item.get('stock_code', '')} {item.get('stock_name', '')}".rstrip(),
                    f"- 买入股数：`{item.get('target_shares')}`",
                    f"- 最大股数：`{item.get('max_shares')}`",
                    f"- 参考买入区间：`{item.get('buy_zone', 'n/a')}`",
                    f"- 止损：`{item.get('stop_loss', 'n/a')}`",
                    f"- 止盈：`{item.get('take_profit', 'n/a')}`",
                    f"- 建议持仓周期：`{item.get('suggested_holding_label', '')}`",
                    f"- 原因：{item.get('reason', '') or '无'}",
                    "",
                ]
            )

    lines.append("## 卖出指令")
    sell_orders = list(payload.get("sell_orders", []))
    if not sell_orders:
        lines.append("- 无明确卖出指令")
    else:
        for index, item in enumerate(sell_orders, start=1):
            lines.extend(
                [
                    f"### SELL {index}: {item.get('stock_code', '')} {item.get('stock_name', '')}".rstrip(),
                    f"- 卖出股数：`{item.get('target_shares')}`",
                    f"- 卖出范围：`{item.get('sell_scope', '')}`",
                    f"- 当前浮盈亏：`{_safe_pct_text(item.get('unrealized_return_pct'))}`",
                    f"- 原因：{item.get('reason', '') or '无'}",
                    f"- 依据：{item.get('rationale', '') or '无'}",
                    "",
                ]
            )

    lines.append("## 持仓处理")
    hold_orders = list(payload.get("hold_orders", []))
    if not hold_orders:
        lines.append("- 当前无需要持有处理的仓位")
    else:
        for item in hold_orders:
            lines.extend(
                [
                    f"### HOLD: {item.get('stock_code', '')} {item.get('stock_name', '')}".rstrip(),
                    f"- 持有股数：`{item.get('shares')}`",
                    f"- 当前浮盈亏：`{_safe_pct_text(item.get('unrealized_return_pct'))}`",
                    f"- 建议：{item.get('reason', '') or '无'}",
                    "",
                ]
            )

    if not payload.get("actionable"):
        lines.extend(
            [
                "## 今日结论",
                "- 不操作。看完这份指令单后，不需要再执行新的买卖单。",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
