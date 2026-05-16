from __future__ import annotations

from trading_system.utils.main_board import is_main_board
from trading_system.context.cards import CandidateCard, MarketRegimeSnapshot
from trading_system.decision.account import AccountConstraints
from trading_system.signal.scanners.base import ModuleSignal


def aggregate_module_signals(signals: list[ModuleSignal]) -> dict[str, list[ModuleSignal]]:
    """按 stock_code 聚合模块信号。"""
    result: dict[str, list[ModuleSignal]] = {}
    for signal in signals:
        result.setdefault(signal.stock_code, []).append(signal)
    return result


def merge_signals_for_stock(signals: list[ModuleSignal]) -> dict:
    """合并同一支票的多个模块信号，返回聚合摘要。

    Returns:
        {
            "active_module_ids": list[str],
            "best_strength": float,
            "avg_strength": float,
            "has_avoid": bool,
            "has_strong": bool,
            "technical_state": str,
            "invalidation_hint": str,
        }
    """
    if not signals:
        return {
            "active_module_ids": [],
            "best_strength": 0.0,
            "avg_strength": 0.0,
            "has_avoid": False,
            "has_strong": False,
            "technical_state": "",
            "invalidation_hint": "",
        }

    active_module_ids = [s.module_id for s in signals]
    strengths = [s.strength for s in signals]
    confidences = [s.confidence for s in signals]
    total_conf = sum(confidences) or 1.0
    avg_strength = sum(s * c for s, c in zip(strengths, confidences)) / total_conf
    best_strength = max(strengths)
    has_avoid = any(s.signal_type == "avoid" for s in signals)
    has_strong = any(s.signal_type == "strong" for s in signals)

    # technical_state: 取最强信号的，或用组合描述
    best_signal = max(signals, key=lambda s: s.strength * s.confidence)
    technical_state = best_signal.technical_state
    if len(signals) > 1:
        other_ids = [s.module_id.replace("TM", "").replace("_", "") for s in signals if s.module_id != best_signal.module_id]
        if other_ids:
            technical_state = f"{best_signal.technical_state} + {'/'.join(other_ids)}"

    # invalidation_hint: 收集所有非空的 hint
    hints = [s.invalidation_hint for s in signals if s.invalidation_hint]
    invalidation_hint = hints[0] if hints else ""

    return {
        "active_module_ids": active_module_ids,
        "best_strength": best_strength,
        "avg_strength": avg_strength,
        "has_avoid": has_avoid,
        "has_strong": has_strong,
        "technical_state": technical_state,
        "invalidation_hint": invalidation_hint,
    }


def compute_module_score(signals: list[ModuleSignal]) -> float:
    """计算模块维度得分，参与候选评分。"""
    if not signals:
        return 0.25

    best = max(s.strength for s in signals)
    confidences = [s.confidence for s in signals]
    total_conf = sum(confidences) or 1.0
    avg = sum(s.strength * s.confidence for s in signals) / total_conf
    has_avoid = any(s.signal_type == "avoid" for s in signals)
    has_strong = any(s.signal_type == "strong" for s in signals)

    score = 0.35 + best * 0.30 + avg * 0.20
    if has_strong:
        score += 0.08
    if has_avoid:
        score -= 0.25
    return max(0.0, min(1.0, score))


def filter_universe_by_account(
    universe: list[str],
    account: AccountConstraints | None,
) -> list[str]:
    """根据账户约束过滤股票池。"""
    if account is None or not account.main_board_only:
        return universe
    return [code for code in universe if is_main_board(code)]
