from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from trading_system.config.paths import INBOX_DIR, OUTPUTS_DIR
from trading_system.context.cards import CandidateCard, MacroEventCard, MarketRegimeSnapshot, ThemeCard, TradePlanCard
from trading_system.decision.account import AccountConstraints
from trading_system.decision.holdings import HoldingAssessment, PortfolioSnapshot
from trading_system.decision.market_gate import evaluate_market_gate
from trading_system.ingest.simple_tabular import read_records


def preopen_summary_output_dir() -> Path:
    directory = OUTPUTS_DIR / "preopen"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2%}"


def _safe_num(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.2f}"


def _safe_score(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}"


def _safe_price(value: float | None) -> str:
    if value is None:
        return "暂无"
    return f"{value:.2f}元"


def _safe_price_band(low: float | None, high: float | None) -> str:
    if low is None or high is None:
        return "暂无"
    return f"{low:.2f} - {high:.2f} 元"


def _cn_value(value: str) -> str:
    mapping = {
        "risk_on": "偏进攻",
        "selective": "选择性参与",
        "risk_off": "偏防守",
        "bullish": "偏多",
        "neutral": "中性",
        "bearish": "偏空",
        "large_cap_lead": "大盘/权重领先",
        "small_cap_lead": "小票领先",
        "mixed": "混合",
        "balanced": "均衡",
        "strong": "强",
        "medium": "中",
        "weak": "弱",
        "high": "高",
        "low": "低",
        "warm": "温和",
        "hot": "偏热",
        "cool": "偏冷",
        "contraction": "收缩",
        "expansion": "扩张",
        "fragile_leaders": "龙头不稳",
        "stable_leaders": "龙头较稳",
        "theme_momentum": "主题驱动",
        "defensive": "防守驱动",
        "strong_mainline": "强主线",
        "tradable_branch": "可交易分支",
        "event_pulse": "事件脉冲",
        "leader": "前排",
        "core": "中军/次前排",
        "follower": "跟风观察",
        "avoid": "回避",
        "confirm_then_trade": "先确认后出手",
        "mainline_focus": "聚焦主线",
        "small_probe": "小仓试错",
        "defensive_wait": "偏防守等待",
        "buy_pilot": "试仓买入",
        "watch_only": "仅观察",
        "broad_uptrend": "指数普遍上行",
        "broad_downtrend": "指数普遍下行",
        "stabilizing": "止跌企稳",
        "mixed_range": "震荡分化",
        "broadly_aligned_up": "主要指数同步偏强",
        "broadly_aligned_down": "主要指数同步偏弱",
        "divergent": "指数分化",
        "cross_border_diplomacy": "跨境外交",
        "geopolitical_conflict": "地缘冲突",
        "tariff_or_sanction": "关税或制裁",
        "fiscal_or_consumption_stimulus": "财政或消费刺激",
        "monetary_easing": "货币宽松",
        "market_rule_or_reform": "市场规则或改革",
        "macro_cross_border": "跨境宏观影响",
        "global_risk_aversion": "全球风险偏好压制",
        "global_trade_friction": "全球贸易摩擦",
        "domestic_demand": "内需驱动",
        "liquidity": "流动性驱动",
        "market_structure": "市场结构影响",
        "medium_term_policy_line": "中期政策主线",
        "multi_day": "多日延续",
        "multi_day_follow_up": "多日跟随",
        "event_follow_up": "事件跟踪",
        "needs_review": "待观察",
        "none": "无",
    }
    return mapping.get(str(value or "").strip(), str(value or "").strip())


def _cn_display_text(text: str) -> str:
    normalized = str(text or "")
    replacements = {
        "Speculation is contracting. Prioritize defense, avoid weak follow-through, and treat rebounds skeptically.": "情绪收缩，优先防守，避免追逐弱一致性，反弹也要谨慎对待。",
        "risk_on": "偏进攻",
        "risk_off": "偏防守",
        "large_cap_lead": "大盘/权重领先",
        "small_cap_lead": "小票领先",
        "event_breakout_watch": "事件突破观察",
        "event_theme_resonance": "事件与主题共振",
        "group_1_rotation": "轮动修复",
        "high_capital_inflow": "高资金流入",
        "theme_rotation_watch": "主题轮动观察",
        "selective_repair_watch": "选择性修复观察",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _load_stock_name_map(trade_date: str) -> dict[str, str]:
    compact = trade_date.replace("-", "")
    paths = [
        INBOX_DIR / "equity_reference_master" / f"equity_reference_master_{compact}.csv",
        INBOX_DIR / "market_equity_daily" / f"market_equity_daily_{compact}.csv",
    ]
    name_map: dict[str, str] = {}
    for path in paths:
        if not path.exists():
            continue
        for record in read_records(path):
            stock_code = str(record.get("stock_code", "") or record.get("ts_code", "")).strip().upper()
            stock_name = str(record.get("name", "") or record.get("stock_name", "")).strip()
            if stock_code and stock_name and stock_code not in name_map:
                name_map[stock_code] = stock_name
    return name_map


def _price_plan(card: CandidateCard, action: str) -> tuple[float | None, float | None, float | None, float | None, float | None]:
    close = card.last_close_price
    if close is None or close <= 0:
        return None, None, None, None, None
    if card.technical_state in {"event_breakout_watch", "event_theme_resonance"}:
        return round(close * 0.995, 2), round(close * 1.015, 2), round(close * 0.97, 2), round(close * 1.04, 2), round(close * 1.08, 2)
    if card.technical_state in {"group_1_rotation", "theme_rotation_watch", "selective_repair_watch"}:
        return round(close * 0.985, 2), round(close * 1.005, 2), round(close * 0.965, 2), round(close * 1.03, 2), round(close * 1.06, 2)
    return round(close * 0.99, 2), round(close * 1.01, 2), round(close * 0.97, 2), round(close * 1.04, 2), round(close * 1.07, 2)


def _share_plan(card: CandidateCard, account: AccountConstraints, max_position_pct: float | None) -> tuple[int | None, int | None]:
    if card.last_close_price is None or card.last_close_price <= 0 or not max_position_pct:
        return None, None
    lot_size = max(1, int(card.board_lot_size or 100))
    lot_cost = card.estimated_min_lot_cost or (card.last_close_price * lot_size)
    if lot_cost <= 0:
        return None, None
    pilot_budget = float(account.capital_total or 0.0) * max_position_pct * 0.5
    max_budget = float(account.capital_total or 0.0) * max_position_pct
    pilot_lots = int(pilot_budget // lot_cost)
    max_lots = int(max_budget // lot_cost)
    if pilot_lots <= 0:
        return None, None
    max_lots = max(max_lots, pilot_lots)
    return pilot_lots * lot_size, max_lots * lot_size


def _focus_themes(theme_cards: list[ThemeCard], *, limit: int = 5) -> list[ThemeCard]:
    def looks_garbled(text: str) -> bool:
        markers = ("锛", "銆", "鈥", "鏈€", "闂", "璇", "鍏", "鐨", "鎴", "浜", "涓", "鏄")
        return not text or sum(text.count(marker) for marker in markers) >= 2

    def score_theme(card: ThemeCard) -> float:
        if not card.priority_stocks and not card.priority_industries and not card.llm_tradeability_verdict:
            return 0.0
        score = 0.0
        score += len(card.priority_stocks) * 3.0
        score += len(card.priority_industries) * 2.0
        if card.continuation_guess in {"multi_day", "multi_day_follow_up", "medium_term_policy_line"}:
            score += 2.0
        if card.llm_tradeability_verdict:
            score += 1.0
        return score

    ranked = sorted(
        [
            card
            for card in theme_cards
            if not looks_garbled(card.theme_name) and score_theme(card) > 0.0
        ],
        key=lambda card: (
            -score_theme(card),
            card.theme_name,
        ),
    )
    return ranked[:limit]


def _top_new_ideas(trade_plans: list[TradePlanCard], held_codes: set[str]) -> list[TradePlanCard]:
    return [plan for plan in trade_plans if plan.action == "buy_pilot" and plan.stock_code not in held_codes]


def _watchlist(trade_plans: list[TradePlanCard], held_codes: set[str], *, limit: int = 8) -> list[TradePlanCard]:
    return [plan for plan in trade_plans if plan.action == "watch_only" and plan.stock_code not in held_codes][:limit]


def _theme_conviction_label(theme_card: ThemeCard, candidate_count: int, leader_count: int) -> str:
    if theme_card.continuation_guess in {"multi_day", "multi_day_follow_up", "medium_term_policy_line"} and leader_count >= 1:
        return "high"
    if candidate_count >= 2 or leader_count >= 1:
        return "medium"
    return "low"


def _fallback_theme_family(label: str) -> tuple[str, str]:
    text = str(label or "").strip()
    if any(token in text for token in ("回购", "增持", "股东支持", "鍥炶喘", "澧炴寔")):
        return "shareholder_support", "股东支持与回购"
    if any(token in text for token in ("减持", "解禁", "鍑忔寔", "瑙ｇ")):
        return "shareholder_overhang", "股东减持与解禁压力"
    if any(token in text for token in ("合同", "中标", "订单", "鍚堝悓", "涓爣", "璁㈠崟")):
        return "order_and_contract", "订单合同驱动"
    if any(token in text for token in ("业绩", "预增", "快报", "涓氱哗", "棰勫", "蹇姤")):
        return "earnings_momentum", "业绩驱动"
    if any(token in text for token in ("重组", "并购", "閲嶇粍", "骞惰喘")):
        return "restructuring", "重组并购驱动"
    if any(token in text for token in ("监管", "风险", "问询", "处罚", "鐩戠", "椋庨櫓", "闂", "澶勭綒")):
        return "regulatory_risk", "监管与风险压力"
    return text or "other", text or "其他事件"


def _leader_sort_key(item: dict) -> tuple[float, float, float]:
    action_bonus = 1.0 if item.get("plan_action") == "buy_pilot" else 0.0
    info_score = float(item.get("information_edge_score") or 0.0)
    candidate_score = float(item.get("candidate_score") or 0.0)
    return (action_bonus, info_score, candidate_score)


def _theme_role_label(item: dict) -> tuple[str, str]:
    action = str(item.get("plan_action", "")).strip()
    tradeability = str(item.get("tradeability_verdict", "")).strip()
    source = str(item.get("candidate_source", "")).strip()
    candidate_score = float(item.get("candidate_score") or 0.0)
    info_score = float(item.get("information_edge_score") or 0.0)

    if tradeability in {"too_concentrated", "blocked_by_budget"}:
        return "avoid", "账户约束不匹配"
    if action == "buy_pilot" and info_score >= 0.35 and candidate_score >= 0.60:
        return "leader", "事件确认较强，可作为前排观察或试仓"
    if action == "buy_pilot":
        return "core", "具备交易价值，但仍需确认主线持续性"
    if source in {"event_theme_resonance", "full_resonance", "module_event_resonance"} and candidate_score >= 0.58:
        return "core", "有主线共振，可作为中军或次前排跟踪"
    return "follower", "更适合作为跟风观察，不宜抢先出手"


def _theme_strength_snapshot(item: dict, market_regime: MarketRegimeSnapshot) -> tuple[str, str]:
    leaders = list(item.get("leader_candidates", []))
    core = list(item.get("core_candidates", []))
    followers = list(item.get("follower_candidates", []))
    continuation = str(item.get("continuation_guess", "")).strip()

    strength_score = len(leaders) * 2.0 + len(core) * 1.2 + len(followers) * 0.5
    if continuation in {"multi_day", "multi_day_follow_up", "medium_term_policy_line"}:
        strength_score += 1.0
    if market_regime.event_driven_bias == "theme_momentum":
        strength_score += 0.8
    if market_regime.sentiment_cycle == "contraction":
        strength_score -= 0.6
    if market_regime.leader_stability == "fragile_leaders":
        strength_score -= 0.5

    if strength_score >= 5.0:
        return "strong_mainline", "主线强度较高，可优先围绕前排和中军寻找交易机会"
    if strength_score >= 3.0:
        return "tradable_branch", "具备交易性，但更适合控制节奏，优先做确认后的前排"
    return "event_pulse", "更像事件脉冲，适合观察，不宜过度扩散到跟风票"


def _beneficiary_mapping(item: dict) -> tuple[list[str], list[str]]:
    direct: list[str] = []
    indirect: list[str] = []

    for leader in item.get("leader_candidates", []):
        stock_code = str(leader.get("stock_code", "")).strip()
        if stock_code and stock_code not in direct:
            direct.append(stock_code)

    for core in item.get("core_candidates", []):
        stock_code = str(core.get("stock_code", "")).strip()
        source = str(core.get("candidate_source", "")).strip()
        if not stock_code:
            continue
        if source in {"event_direct", "event_theme_resonance", "full_resonance"}:
            if stock_code not in direct:
                direct.append(stock_code)
        elif stock_code not in indirect:
            indirect.append(stock_code)

    for follower in item.get("follower_candidates", []):
        stock_code = str(follower.get("stock_code", "")).strip()
        if stock_code and stock_code not in direct and stock_code not in indirect:
            indirect.append(stock_code)

    return direct[:4], indirect[:6]


def _theme_context_map(theme_board: list[dict]) -> dict[str, dict]:
    context_map: dict[str, dict] = {}

    def add_items(items: list[dict], theme_item: dict, beneficiary_type: str) -> None:
        for item in items:
            stock_code = str(item.get("stock_code", "")).strip()
            if not stock_code:
                continue
            context_map[stock_code] = {
                "theme_name": theme_item.get("theme_name", ""),
                "theme_role": item.get("theme_role", ""),
                "role_note": item.get("role_note", ""),
                "strength_label": theme_item.get("strength_label", ""),
                "strength_note": theme_item.get("strength_note", ""),
                "beneficiary_type": beneficiary_type,
            }

    for theme_item in theme_board:
        direct_set = set(theme_item.get("direct_beneficiaries", []))
        indirect_set = set(theme_item.get("indirect_beneficiaries", []))
        for bucket_name in ("leader_candidates", "core_candidates", "follower_candidates", "avoid_candidates"):
            bucket = list(theme_item.get(bucket_name, []))
            enriched_bucket: list[dict] = []
            for item in bucket:
                stock_code = str(item.get("stock_code", "")).strip()
                beneficiary_type = "related"
                if stock_code in direct_set:
                    beneficiary_type = "direct"
                elif stock_code in indirect_set:
                    beneficiary_type = "indirect"
                enriched_bucket.append({**item, "beneficiary_type": beneficiary_type})
            add_items(enriched_bucket, theme_item, "direct")
            for enriched in enriched_bucket:
                stock_code = str(enriched.get("stock_code", "")).strip()
                if stock_code:
                    context_map[stock_code]["beneficiary_type"] = enriched.get("beneficiary_type", "related")

    return context_map


def _beneficiary_note(context: dict) -> str:
    beneficiary_type = str(context.get("beneficiary_type", "")).strip()
    role = str(context.get("theme_role", "")).strip()
    if beneficiary_type == "direct" and role == "leader":
        return "主线前排，且属于直接受益对象"
    if beneficiary_type == "direct":
        return "属于主线直接受益对象"
    if beneficiary_type == "indirect" and role == "core":
        return "属于主线中军或次前排，更偏间接受益"
    if beneficiary_type == "indirect":
        return "更偏间接受益或跟随受益"
    return "与主线相关，但受益路径仍需盘中确认"


def _direct_trade_opinion(
    *,
    plan: TradePlanCard,
    card: CandidateCard | None,
    account: AccountConstraints,
    theme_context: dict,
) -> dict:
    if card is None:
        return {
            "instruction": "今天不做，先观察。",
            "buy_zone": "暂无",
            "stop_loss": "暂无",
            "take_profit": "暂无",
            "pilot_shares": None,
            "max_shares": None,
        }

    buy_low, buy_high, stop_price, tp_low, tp_high = _price_plan(card, plan.action)
    pilot_shares, max_shares = _share_plan(card, account, plan.max_position_pct)
    role = str(theme_context.get("theme_role", "")).strip()

    if role == "avoid" or card.tradeability_verdict in {"too_concentrated", "blocked_by_budget"}:
        instruction = "今天不买，直接回避。如果你已经持有，优先按防守思路处理，不建议新增。"
    elif plan.action == "buy_pilot":
        if pilot_shares is None:
            instruction = "今天理论上可关注，但以你当前账户约束看不适合直接买入。"
        else:
            instruction = (
                f"今天可以小仓试错，优先在 {_safe_price_band(buy_low, buy_high)} 区间内等待确认后买入。"
                f" 首笔建议 {pilot_shares} 股，最多不超过 {max_shares} 股。"
                f" 若跌破 {_safe_price(stop_price)} 附近应止损；若上冲到 {_safe_price_band(tp_low, tp_high)} 可分批止盈。"
            )
        if role == "leader":
            instruction = "主线前排。" + instruction
        elif role == "core":
            instruction = "主线中军/次前排。" + instruction
    elif plan.action == "watch_only":
        instruction = (
            f"今天先不直接买入，只观察。若回到 {_safe_price_band(buy_low, buy_high)} 后重新转强，"
            f"且主线仍保持强势，再考虑转入备选。止损参考 {_safe_price(stop_price)}，止盈参考 {_safe_price_band(tp_low, tp_high)}。"
        )
    else:
        instruction = "今天不买，直接回避。若已有持仓，优先按弱势处理。"

    return {
        "instruction": instruction,
        "buy_zone": _safe_price_band(buy_low, buy_high),
        "stop_loss": _safe_price(stop_price),
        "take_profit": _safe_price_band(tp_low, tp_high),
        "pilot_shares": pilot_shares,
        "max_shares": max_shares,
    }


def _action_summary(
    market_regime: MarketRegimeSnapshot,
    account: AccountConstraints,
    theme_board: list[dict],
    top_new_ideas: list[TradePlanCard],
    watchlist: list[TradePlanCard],
) -> dict:
    gate = evaluate_market_gate(market_regime, account)
    focus_theme = theme_board[0] if theme_board else {}
    posture = "small_probe"
    note = "优先小仓位试错，等待开盘后确认。"
    if market_regime.risk_mode == "risk_off":
        posture = "defensive_wait"
        note = "市场偏防守，优先观望和处理已有持仓。"
    elif market_regime.sentiment_cycle == "contraction":
        posture = "confirm_then_trade"
        note = "情绪收缩，先确认主线和前排稳定，再考虑出手。"
    elif focus_theme.get("strength_label") == "strong_mainline":
        posture = "mainline_focus"
        note = "可优先围绕最强主线的前排和中军寻找交易机会。"

    theme_count = len(theme_board)
    if theme_count <= 1 and focus_theme:
        concentration_note = "当前可交易主线较集中，属于机会面偏窄的交易日，不宜随意扩散到无关方向。"
    elif theme_count == 0:
        concentration_note = "当前没有清晰可交易主线，优先观望或只做最强确认。"
    else:
        concentration_note = "当前存在多条可观察方向，但仍应优先围绕最强主线。"

    return {
        "preferred_posture": posture,
        "posture_note": note,
        "best_setup": top_new_ideas[0].setup_type if top_new_ideas else "",
        "blocked_setups": list(gate.blocked_setups),
        "allowed_setups": list(gate.allowed_setups),
        "focus_theme": focus_theme.get("theme_name", ""),
        "focus_theme_strength": focus_theme.get("strength_label", ""),
        "tradable_theme_count": theme_count,
        "concentration_note": concentration_note,
        "new_idea_count": len(top_new_ideas),
        "watchlist_count": len(watchlist),
        "avoid_count": sum(len(item.get("avoid_candidates", [])) for item in theme_board),
    }


def _collapse_theme_board(board: list[dict]) -> list[dict]:
    grouped: dict[str, dict] = {}

    def upsert_item(bucket: dict[str, dict], category: str, item: dict) -> None:
        stock_code = str(item.get("stock_code", "")).strip()
        if not stock_code:
            return
        current = bucket.get(stock_code)
        if current is None:
            bucket[stock_code] = {**item, "_category": category}
            return
        precedence = {"secondary": 1, "leader": 2, "avoid": 3}
        current_rank = precedence.get(current.get("_category", "secondary"), 0)
        incoming_rank = precedence.get(category, 0)
        if incoming_rank > current_rank or (
            incoming_rank == current_rank and _leader_sort_key(item) > _leader_sort_key(current)
        ):
            bucket[stock_code] = {**item, "_category": category}

    for item in board:
        original_name = str(item.get("theme_name", "")).strip()
        family_key, family_name = _fallback_theme_family(original_name)
        bucket = grouped.setdefault(
            family_key,
            {
                "theme_name": family_name,
                "continuation_guess": item.get("continuation_guess", ""),
                "conviction": item.get("conviction", "low"),
                "priority_industries": [],
                "trigger_labels": [],
                "_items": {},
            },
        )
        if original_name and original_name != family_name and original_name not in bucket["trigger_labels"]:
            bucket["trigger_labels"].append(original_name)
        for label in item.get("trigger_labels", []):
            cleaned = str(label or "").strip()
            if cleaned and cleaned not in bucket["trigger_labels"]:
                bucket["trigger_labels"].append(cleaned)
        for industry in item.get("priority_industries", []):
            cleaned = str(industry or "").strip()
            if cleaned and cleaned not in bucket["priority_industries"]:
                bucket["priority_industries"].append(cleaned)
        if item.get("continuation_guess") in {"multi_day", "multi_day_follow_up", "medium_term_policy_line"}:
            bucket["continuation_guess"] = item.get("continuation_guess")
            bucket["conviction"] = "high"
        elif item.get("conviction") == "medium" and bucket["conviction"] == "low":
            bucket["conviction"] = "medium"

        for leader in item.get("leader_candidates", []):
            upsert_item(bucket["_items"], "leader", leader)
        for secondary in item.get("secondary_candidates", []):
            upsert_item(bucket["_items"], "secondary", secondary)
        for avoid in item.get("avoid_candidates", []):
            upsert_item(bucket["_items"], "avoid", avoid)

    collapsed: list[dict] = []
    for bucket in grouped.values():
        merged_items = list(bucket["_items"].values())
        merged_items.sort(key=_leader_sort_key, reverse=True)
        leaders: list[dict] = []
        core: list[dict] = []
        followers: list[dict] = []
        avoid: list[dict] = []
        secondary: list[dict] = []

        for raw_item in merged_items:
            item = {k: v for k, v in raw_item.items() if k != "_category"}
            role, role_note = _theme_role_label(item)
            item["theme_role"] = role
            item["role_note"] = role_note
            if role == "leader":
                leaders.append(item)
            elif role == "core":
                core.append(item)
                secondary.append(item)
            elif role == "follower":
                followers.append(item)
                secondary.append(item)
            else:
                avoid.append(item)

        if leaders and bucket["conviction"] == "low":
            bucket["conviction"] = "medium"
        collapsed.append(
            {
                "theme_name": bucket["theme_name"],
                "continuation_guess": bucket["continuation_guess"] or "event_follow_up",
                "conviction": bucket["conviction"],
                "priority_industries": list(bucket["priority_industries"][:5]),
                "trigger_labels": list(bucket["trigger_labels"][:5]),
                "leader_candidates": leaders[:3],
                "core_candidates": core[:4],
                "follower_candidates": followers[:5],
                "secondary_candidates": secondary[:5],
                "avoid_candidates": avoid[:4],
            }
        )

    collapsed.sort(
        key=lambda item: (
            -len(item.get("leader_candidates", [])),
            -len(item.get("secondary_candidates", [])),
            item.get("theme_name", ""),
        )
    )
    return collapsed[:4]


def _build_theme_board(
    *,
    candidate_cards: list[CandidateCard],
    trade_plans: list[TradePlanCard],
    theme_cards: list[ThemeCard],
    market_regime: MarketRegimeSnapshot,
) -> list[dict]:
    candidate_map = {card.stock_code: card for card in candidate_cards}
    plan_map = {plan.stock_code: plan for plan in trade_plans}
    board: list[dict] = []

    for theme in _focus_themes(theme_cards):
        related_codes = list(dict.fromkeys(theme.priority_stocks))
        if not related_codes:
            related_codes = [
                card.stock_code
                for card in candidate_cards
                if (card.theme_alignment_score or 0.0) >= 0.55 and "theme" in card.candidate_source
            ][:6]
        if not related_codes:
            continue

        leaders: list[dict] = []
        secondary: list[dict] = []
        avoid: list[dict] = []

        for stock_code in related_codes:
            card = candidate_map.get(stock_code)
            plan = plan_map.get(stock_code)
            if card is None:
                continue

            item = {
                "stock_code": stock_code,
                "plan_action": plan.action if plan else "none",
                "candidate_source": card.candidate_source,
                "candidate_score": card.candidate_score,
                "information_edge_score": card.information_edge_score,
                "tradeability_verdict": card.tradeability_verdict,
                "note": card.llm_diagnostic_summary or card.diagnostic_summary,
            }

            if plan and plan.action == "buy_pilot":
                leaders.append(item)
            elif card.tradeability_verdict in {"too_concentrated", "blocked_by_budget"} or any(
                flag in {"bearish_event_overhang", "text_watch_risk_overhang"} for flag in card.disqualify_flags
            ):
                avoid.append(item)
            else:
                secondary.append(item)

        if not leaders and not secondary and not avoid:
            continue

        board.append(
            {
                "theme_name": theme.theme_name,
                "continuation_guess": theme.continuation_guess,
                "conviction": _theme_conviction_label(theme, len(secondary) + len(leaders), len(leaders)),
                "priority_industries": list(theme.priority_industries[:5]),
                "leader_candidates": leaders[:3],
                "secondary_candidates": secondary[:5],
                "avoid_candidates": avoid[:4],
            }
        )

    if board:
        collapsed = _collapse_theme_board(board)
        for item in collapsed:
            strength_label, strength_note = _theme_strength_snapshot(item, market_regime)
            direct_beneficiaries, indirect_beneficiaries = _beneficiary_mapping(item)
            item["strength_label"] = strength_label
            item["strength_note"] = strength_note
            item["direct_beneficiaries"] = direct_beneficiaries
            item["indirect_beneficiaries"] = indirect_beneficiaries
        return collapsed

    support_groups: dict[str, dict] = {}
    for plan in trade_plans:
        for label in plan.supporting_cards:
            cleaned = str(label or "").strip()
            if not cleaned:
                continue
            family_key, family_name = _fallback_theme_family(cleaned)
            bucket = support_groups.setdefault(
                family_key,
                {
                    "theme_name": family_name,
                    "trigger_labels": [],
                    "items": [],
                },
            )
            if cleaned not in bucket["trigger_labels"]:
                bucket["trigger_labels"].append(cleaned)
            bucket["items"].append(
                {
                    "stock_code": plan.stock_code,
                    "plan_action": plan.action,
                    "candidate_score": candidate_map.get(plan.stock_code).candidate_score if plan.stock_code in candidate_map else None,
                    "information_edge_score": candidate_map.get(plan.stock_code).information_edge_score if plan.stock_code in candidate_map else None,
                    "candidate_source": candidate_map.get(plan.stock_code).candidate_source if plan.stock_code in candidate_map else "",
                    "tradeability_verdict": candidate_map.get(plan.stock_code).tradeability_verdict if plan.stock_code in candidate_map else "",
                    "note": candidate_map.get(plan.stock_code).llm_diagnostic_summary if plan.stock_code in candidate_map else "",
                }
            )

    fallback_board: list[dict] = []
    for _, bucket in sorted(support_groups.items(), key=lambda item: (-len(item[1]["items"]), item[1]["theme_name"])):
        items = list(bucket["items"])
        if len(items) < 2:
            continue
        items.sort(key=_leader_sort_key, reverse=True)
        leaders = [item for item in items if item["plan_action"] == "buy_pilot"][:3]
        secondary = [item for item in items if item["plan_action"] == "watch_only"][:5]
        avoid = [
            item
            for item in items
            if item["tradeability_verdict"] in {"too_concentrated", "blocked_by_budget"}
        ][:4]
        fallback_board.append(
            {
                "theme_name": bucket["theme_name"],
                "continuation_guess": "event_follow_up",
                "conviction": "medium" if leaders else "low",
                "priority_industries": [],
                "trigger_labels": list(bucket["trigger_labels"][:4]),
                "leader_candidates": leaders,
                "secondary_candidates": secondary,
                "avoid_candidates": avoid,
            }
        )
        if len(fallback_board) >= 4:
            break

    collapsed = _collapse_theme_board(fallback_board)
    for item in collapsed:
        strength_label, strength_note = _theme_strength_snapshot(item, market_regime)
        direct_beneficiaries, indirect_beneficiaries = _beneficiary_mapping(item)
        item["strength_label"] = strength_label
        item["strength_note"] = strength_note
        item["direct_beneficiaries"] = direct_beneficiaries
        item["indirect_beneficiaries"] = indirect_beneficiaries
    return collapsed


def build_preopen_summary_payload(
    *,
    trade_date: str,
    market_regime: MarketRegimeSnapshot,
    account: AccountConstraints,
    portfolio: PortfolioSnapshot,
    holding_assessments: list[HoldingAssessment],
    candidate_cards: list[CandidateCard],
    trade_plans: list[TradePlanCard],
    theme_cards: list[ThemeCard],
    macro_event_cards: list[MacroEventCard] | None = None,
    setup_performance: dict | None = None,
    execution_feedback: dict | None = None,
    execution_behavior: dict | None = None,
) -> dict:
    held_codes = {item.stock_code for item in holding_assessments}
    top_new_ideas = _top_new_ideas(trade_plans, held_codes)
    watchlist = _watchlist(trade_plans, held_codes)
    candidate_map = {card.stock_code: card for card in candidate_cards}
    stock_name_map = _load_stock_name_map(trade_date)
    theme_board = _build_theme_board(
        candidate_cards=candidate_cards,
        trade_plans=trade_plans,
        theme_cards=theme_cards,
        market_regime=market_regime,
    )
    theme_context = _theme_context_map(theme_board)
    action_summary = _action_summary(market_regime, account, theme_board, top_new_ideas, watchlist)

    payload = {
        "trade_date": trade_date,
        "data_basis": {
            "market_close_date": trade_date,
            "description": "This summary is based on the latest completed market session and overnight structured information.",
        },
        "market_view": asdict(market_regime),
        "account_view": {
            "profile_name": account.profile_name,
            "trading_style": account.trading_style,
            "target_return_mode": account.target_return_mode,
            "capital_total": account.capital_total,
            "single_position_max_pct": account.single_position_max_pct,
            "single_trade_capital_max": account.single_trade_capital_max,
            "max_holdings": account.max_holdings,
            "max_new_positions_per_day": account.max_new_positions_per_day,
            "execution_mode": account.execution_mode,
            "can_watch_intraday": account.can_watch_intraday,
        },
        "action_summary": action_summary,
        "portfolio": portfolio.to_dict(),
        "holding_assessments": [assessment.to_dict() for assessment in holding_assessments],
        "theme_board": theme_board,
        "top_new_ideas": [
            {
                "stock_code": plan.stock_code,
                "stock_name": stock_name_map.get(plan.stock_code, ""),
                "action": plan.action,
                "setup_type": plan.setup_type,
                "setup_policy_status": plan.setup_policy_status,
                "priority_rank": plan.priority_rank,
                "entry_condition": plan.entry_condition,
                "position_size_rule": plan.position_size_rule,
                "max_position_pct": plan.max_position_pct,
                "rationale": plan.llm_refined_plan or plan.rationale,
                "supporting_cards": list(plan.supporting_cards),
                "theme_context": theme_context.get(plan.stock_code, {}),
                "beneficiary_note": _beneficiary_note(theme_context.get(plan.stock_code, {})),
                "trade_instruction": _direct_trade_opinion(
                    plan=plan,
                    card=candidate_map.get(plan.stock_code),
                    account=account,
                    theme_context=theme_context.get(plan.stock_code, {}),
                ),
                "candidate_diagnosis": (
                    candidate_map[plan.stock_code].llm_diagnostic_summary
                    if plan.stock_code in candidate_map and candidate_map[plan.stock_code].llm_diagnostic_summary
                    else candidate_map[plan.stock_code].diagnostic_summary
                    if plan.stock_code in candidate_map
                    else ""
                ),
            }
            for plan in top_new_ideas
        ],
        "watchlist": [
            {
                "stock_code": plan.stock_code,
                "stock_name": stock_name_map.get(plan.stock_code, ""),
                "priority_rank": plan.priority_rank,
                "setup_type": plan.setup_type,
                "setup_policy_status": plan.setup_policy_status,
                "rationale": plan.llm_refined_plan or plan.rationale,
                "entry_condition": plan.entry_condition,
                "risk_notes": list(plan.risk_notes),
                "theme_context": theme_context.get(plan.stock_code, {}),
                "beneficiary_note": _beneficiary_note(theme_context.get(plan.stock_code, {})),
                "trade_instruction": _direct_trade_opinion(
                    plan=plan,
                    card=candidate_map.get(plan.stock_code),
                    account=account,
                    theme_context=theme_context.get(plan.stock_code, {}),
                ),
            }
            for plan in watchlist
        ],
        "focus_themes": [
            {
                "theme_name": card.theme_name,
                "continuation_guess": card.continuation_guess,
                "priority_industries": list(card.priority_industries),
                "priority_stocks": list(card.priority_stocks[:5]),
                "llm_tradeability_verdict": card.llm_tradeability_verdict,
            }
            for card in _focus_themes(theme_cards)
        ],
        "macro_event_board": [
            {
                "title": card.title,
                "event_type": card.event_type,
                "bias": card.bias,
                "impact_scope": card.impact_scope,
                "confidence": card.confidence,
                "beneficiary_industries": list(card.beneficiary_industries),
                "risk_industries": list(card.risk_industries),
                "confirmation_signals": list(card.confirmation_signals),
                "summary": card.summary,
            }
            for card in list(macro_event_cards or [])[:5]
        ],
        "setup_performance_board": list((setup_performance or {}).get("setup_summary", []))[:5],
        "execution_feedback_board": list((execution_feedback or {}).get("setup_summary", []))[:5],
        "execution_behavior_board": list((execution_behavior or {}).get("setup_summary", []))[:5],
    }
    return payload


def save_preopen_summary_payload(trade_date: str, payload: dict, path: Path | None = None) -> Path:
    output_path = path or (preopen_summary_output_dir() / f"preopen_summary_{trade_date}.json")
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def render_preopen_summary_markdown(payload: dict) -> str:
    market_view = dict(payload.get("market_view", {}))
    account_view = dict(payload.get("account_view", {}))
    action_summary = dict(payload.get("action_summary", {}))
    holdings = list(payload.get("holding_assessments", []))
    top_new_ideas = list(payload.get("top_new_ideas", []))
    watchlist = list(payload.get("watchlist", []))
    theme_board = list(payload.get("theme_board", []))
    macro_event_board = list(payload.get("macro_event_board", []))
    setup_performance_board = list(payload.get("setup_performance_board", []))
    execution_feedback_board = list(payload.get("execution_feedback_board", []))
    execution_behavior_board = list(payload.get("execution_behavior_board", []))
    focus_themes = list(payload.get("focus_themes", []))

    lines = [
        f"# 盘前摘要 - {payload.get('trade_date', '')}",
        "",
        "- 数据基础：基于最近一个完整交易日的收盘数据与隔夜结构化信息生成。",
        f"- 使用收盘日：`{payload.get('data_basis', {}).get('market_close_date', '')}`",
        "",
        "## 市场判断",
        f"- 风险模式：`{_cn_value(market_view.get('risk_mode', ''))}`",
        f"- 市场倾向：`{_cn_value(market_view.get('market_bias', ''))}`",
        f"- 风格主导：`{_cn_value(market_view.get('style_lead', ''))}`",
        f"- 宽度强弱：`{_cn_value(market_view.get('breadth_strength', ''))}`",
        f"- 主线集中度：`{_cn_value(market_view.get('theme_concentration', ''))}`",
        f"- 情绪阶段：`{_cn_value(market_view.get('sentiment_cycle', ''))}`",
        f"- 龙头稳定性：`{_cn_value(market_view.get('leader_stability', ''))}`",
        f"- 事件驱动偏向：`{_cn_value(market_view.get('event_driven_bias', ''))}`",
        f"- 指数趋势状态：`{_cn_value(market_view.get('index_trend_state', ''))}`",
        f"- 指数一致性：`{_cn_value(market_view.get('index_alignment', ''))}`",
        f"- 趋势强度分：`{_safe_score(market_view.get('trend_strength_score'))}`",
        f"- 投机热度分：`{_safe_score(market_view.get('speculative_heat_score'))}`",
        f"- 情绪压力分：`{_safe_score(market_view.get('sentiment_pressure_score'))}`",
        f"- 炸板失败率：`{_safe_pct(market_view.get('breakout_failure_rate'))}`",
        f"- 开盘提示：{_cn_display_text(market_view.get('opening_risk_note', '') or '无')}",
        "",
        "## 账户约束",
        f"- 交易风格：`{account_view.get('trading_style', '') or 'n/a'}`",
        f"- 收益模式：`{account_view.get('target_return_mode', '') or 'n/a'}`",
        f"- 总资金：`{account_view.get('capital_total')}`",
        f"- 单次最大可用资金：`{account_view.get('single_trade_capital_max')}`",
        f"- 当日最多新开仓：`{account_view.get('max_new_positions_per_day')}`",
        f"- 最多持仓数：`{account_view.get('max_holdings')}`",
        "",
        "## 今日结论",
        f"- 建议姿态：`{_cn_value(action_summary.get('preferred_posture', ''))}`",
        f"- 操作说明：{action_summary.get('posture_note', '') or '无'}",
        f"- 核心主线：`{action_summary.get('focus_theme', '') or '无'}`",
        f"- 主线强度：`{_cn_value(action_summary.get('focus_theme_strength', '')) or '无'}`",
        f"- 可交易主线数量：`{action_summary.get('tradable_theme_count', 0)}`",
        f"- 主线集中提示：{action_summary.get('concentration_note', '') or '无'}",
        f"- 可试仓想法数：`{action_summary.get('new_idea_count', 0)}`",
        f"- 观察名单数：`{action_summary.get('watchlist_count', 0)}`",
        f"- 回避样本数：`{action_summary.get('avoid_count', 0)}`",
        "",
        "## 当前持仓",
    ]

    if not holdings:
        lines.append("- 暂无持仓")
    else:
        for item in holdings:
            lines.extend(
                [
                    f"### {item.get('stock_code', '')} {item.get('stock_name', '')}".rstrip(),
                    f"- 持仓建议：`{item.get('summary_action', '')}`",
                    f"- 持股数量：`{item.get('shares', 0)}`",
                    f"- 成本价：`{item.get('cost_basis')}`",
                    f"- 最新收盘价：`{item.get('last_close_price')}`",
                    f"- 市值：`{item.get('market_value')}`",
                    f"- 浮动收益：`{_safe_pct(item.get('unrealized_return_pct'))}`",
                    f"- 组合占比：`{_safe_pct(item.get('portfolio_weight_pct'))}`",
                    f"- 直接建议：{_cn_display_text(item.get('recommendation', '') or '无')}",
                    f"- 理由：{_cn_display_text(item.get('rationale', '') or '无')}",
                    f"- 风险提示：`{_cn_display_text(', '.join(item.get('risk_notes', [])) if item.get('risk_notes') else '无')}`",
                    "",
                ]
            )

    lines.append("## 可交易主线板")
    if not theme_board:
        lines.append("- 暂无清晰可交易主线")
    else:
        for item in theme_board:
            lines.extend(
                [
                    f"### {item.get('theme_name', '')}",
                    f"- 置信度：`{_cn_value(item.get('conviction', ''))}`",
                    f"- 主线强度：`{_cn_value(item.get('strength_label', ''))}`",
                    f"- 强度说明：{_cn_display_text(item.get('strength_note', '') or '无')}",
                    f"- 持续性判断：`{_cn_value(item.get('continuation_guess', '') or '无')}`",
                    f"- 优先行业：`{', '.join(item.get('priority_industries', [])) if item.get('priority_industries') else '无'}`",
                    f"- 触发事件：`{', '.join(item.get('trigger_labels', [])) if item.get('trigger_labels') else '无'}`",
                    f"- 直接受益：`{', '.join(item.get('direct_beneficiaries', [])) if item.get('direct_beneficiaries') else '无'}`",
                    f"- 间接受益：`{', '.join(item.get('indirect_beneficiaries', [])) if item.get('indirect_beneficiaries') else '无'}`",
                ]
            )
            leaders = list(item.get("leader_candidates", []))
            core = list(item.get("core_candidates", []))
            followers = list(item.get("follower_candidates", []))
            avoid = list(item.get("avoid_candidates", []))
            if leaders:
                lines.append("- 前排：")
                for leader in leaders:
                    lines.append(
                        f"  - {leader.get('stock_code', '')} / action={_cn_value(leader.get('plan_action', ''))} / score={leader.get('candidate_score')} / note={_cn_display_text(leader.get('role_note', ''))}"
                    )
            if core:
                lines.append("- 中军/次前排：")
                for stock in core:
                    lines.append(
                        f"  - {stock.get('stock_code', '')} / action={_cn_value(stock.get('plan_action', ''))} / score={stock.get('candidate_score')} / note={_cn_display_text(stock.get('role_note', ''))}"
                    )
            if followers:
                lines.append("- 跟风观察：")
                for stock in followers:
                    lines.append(
                        f"  - {stock.get('stock_code', '')} / action={_cn_value(stock.get('plan_action', ''))} / score={stock.get('candidate_score')} / note={_cn_display_text(stock.get('role_note', ''))}"
                    )
            if avoid:
                lines.append("- 回避：")
                for stock in avoid:
                    lines.append(
                        f"  - {stock.get('stock_code', '')} / tradeability={stock.get('tradeability_verdict', '')} / note={_cn_display_text(stock.get('role_note', ''))}"
                    )
            lines.append("")

    lines.append("## 今日可试仓")
    if not top_new_ideas:
        lines.append("- 暂无可直接试仓标的")
    else:
        for item in top_new_ideas:
            instruction = dict(item.get("trade_instruction", {}))
            lines.extend(
                [
                    f"### {item.get('priority_rank', '')}. {item.get('stock_code', '')} {item.get('stock_name', '')}".rstrip(),
                    f"- 动作：`{_cn_value(item.get('action', ''))}`",
                    f"- 所属主线：`{item.get('theme_context', {}).get('theme_name', '') or '无'}`",
                    f"- 主线身份：`{_cn_value(item.get('theme_context', {}).get('theme_role', '')) or '无'}`",
                    f"- 主线强度：`{_cn_value(item.get('theme_context', {}).get('strength_label', '')) or '无'}`",
                    f"- 受益判断：{_cn_display_text(item.get('beneficiary_note', '') or '无')}",
                    f"- 直接执行意见：{_cn_display_text(instruction.get('instruction', '无'))}",
                    f"- 参考买入区间：`{instruction.get('buy_zone', '暂无')}`",
                    f"- 参考止损价：`{instruction.get('stop_loss', '暂无')}`",
                    f"- 参考止盈区间：`{instruction.get('take_profit', '暂无')}`",
                    f"- 建议试仓股数：`{instruction.get('pilot_shares') if instruction.get('pilot_shares') is not None else '暂无'}`",
                    f"- 建议最大股数：`{instruction.get('max_shares') if instruction.get('max_shares') is not None else '暂无'}`",
                    f"- 专业诊断：{_cn_display_text(item.get('candidate_diagnosis', '') or '无')}",
                    f"- 最大仓位比例：`{item.get('max_position_pct')}`",
                    f"- 支撑信息：`{', '.join(item.get('supporting_cards', [])) if item.get('supporting_cards') else '无'}`",
                    "",
                ]
            )

    lines.append("## 观察名单")
    if not watchlist:
        lines.append("- 暂无观察标的")
    else:
        for item in watchlist:
            instruction = dict(item.get("trade_instruction", {}))
            lines.extend(
                [
                    f"### {item.get('priority_rank', '')}. {item.get('stock_code', '')} {item.get('stock_name', '')}".rstrip(),
                    f"- 所属主线：`{item.get('theme_context', {}).get('theme_name', '') or '无'}`",
                    f"- 主线身份：`{_cn_value(item.get('theme_context', {}).get('theme_role', '')) or '无'}`",
                    f"- 主线强度：`{_cn_value(item.get('theme_context', {}).get('strength_label', '')) or '无'}`",
                    f"- 受益判断：{_cn_display_text(item.get('beneficiary_note', '') or '无')}",
                    f"- 直接执行意见：{_cn_display_text(instruction.get('instruction', '无'))}",
                    f"- 参考买入区间：`{instruction.get('buy_zone', '暂无')}`",
                    f"- 参考止损价：`{instruction.get('stop_loss', '暂无')}`",
                    f"- 参考止盈区间：`{instruction.get('take_profit', '暂无')}`",
                    f"- 风险提示：`{_cn_display_text(', '.join(item.get('risk_notes', [])) if item.get('risk_notes') else '无')}`",
                    "",
                ]
            )

    lines.append("## 宏观事件")
    if not macro_event_board:
        lines.append("- 暂无需要额外强调的宏观事件")
    else:
        for item in macro_event_board:
            lines.extend(
                [
                    f"### {item.get('title', '')}",
                    f"- 事件类型：`{_cn_value(item.get('event_type', '') or 'none')}`",
                    f"- 方向判断：`{_cn_value(item.get('bias', '')) or item.get('bias', 'none')}`",
                    f"- 影响范围：`{_cn_value(item.get('impact_scope', '') or 'none')}`",
                    f"- 置信度：`{_safe_score(item.get('confidence'))}`",
                    f"- 受益行业：`{', '.join(item.get('beneficiary_industries', [])) if item.get('beneficiary_industries') else 'none'}`",
                    f"- 受压行业：`{', '.join(item.get('risk_industries', [])) if item.get('risk_industries') else 'none'}`",
                    f"- 需要确认：`{', '.join(item.get('confirmation_signals', [])) if item.get('confirmation_signals') else 'none'}`",
                    f"- 摘要：{_cn_display_text(item.get('summary', '') or '无')}",
                    "",
                ]
            )

    lines.append("## Setup 复盘")
    if not setup_performance_board:
        lines.append("- 暂无 setup 历史评估")
    else:
        for item in setup_performance_board:
            buy_pilot_3d = dict(item.get("buy_pilot_horizons", {})).get("3d", {})
            lines.extend(
                [
                    f"### {item.get('setup_type', '')}",
                    f"- 样本数：`{item.get('sample_count', 0)}`",
                    f"- buy_pilot 数：`{item.get('buy_pilot_count', 0)}`",
                    f"- 平均 setup 置信度：`{_safe_score(item.get('avg_setup_confidence'))}`",
                    f"- 5日平均最大有利波动：`{_safe_pct(item.get('avg_mfe_5d'))}`",
                    f"- 5日平均最大不利波动：`{_safe_pct(item.get('avg_mae_5d'))}`",
                    f"- buy_pilot 3日平均收益：`{_safe_pct(buy_pilot_3d.get('avg_return'))}` / 胜率：`{_safe_pct(buy_pilot_3d.get('win_rate'))}` / 3%命中率：`{_safe_pct(buy_pilot_3d.get('hit_rate_3pct'))}`",
                    "",
                ]
            )

    lines.append("## 实盘反馈")
    if not execution_feedback_board and not execution_behavior_board:
        lines.append("- 暂无实盘反馈样本")
    else:
        for item in execution_feedback_board:
            matching_behavior = next(
                (entry for entry in execution_behavior_board if entry.get("setup_type") == item.get("setup_type")),
                {},
            )
            lines.extend(
                [
                    f"### {item.get('setup_type', '')}",
                    f"- 实盘平均收益：`{_safe_pct(item.get('avg_realized_return'))}` / 胜率：`{_safe_pct(item.get('win_rate'))}` / 样本数：`{item.get('closed_trade_count', 0)}`",
                    f"- 执行成交率：`{_safe_pct(matching_behavior.get('fill_rate'))}` / 取消或跳过率：`{_safe_pct(matching_behavior.get('skip_rate'))}` / 部分成交率：`{_safe_pct(matching_behavior.get('partial_rate'))}`",
                    f"- 买入滑点：`{_safe_pct(matching_behavior.get('avg_buy_slippage_pct'))}` / 执行备注：`{', '.join(matching_behavior.get('notes', [])) or '无'}`",
                    "",
                ]
            )

    lines.append("## 观察主题")
    if not focus_themes:
        lines.append("- 暂无额外观察主题")
    else:
        for item in focus_themes:
            lines.extend(
                [
                    f"### {item.get('theme_name', '')}",
                    f"- 持续性判断：`{_cn_value(item.get('continuation_guess', '') or '无')}`",
                    f"- 优先行业：`{', '.join(item.get('priority_industries', [])) if item.get('priority_industries') else '无'}`",
                    f"- 优先股票：`{', '.join(item.get('priority_stocks', [])) if item.get('priority_stocks') else '无'}`",
                    f"- LLM 交易性判断：`{_cn_value(item.get('llm_tradeability_verdict', '') or '无')}`",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"
