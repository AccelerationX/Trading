from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from trading_system.config.paths import CONFIGS_DIR
from trading_system.context.cards import MarketRegimeSnapshot


@dataclass(frozen=True)
class TechnicalModule:
    module_id: str
    family: str
    role: str
    priority: str
    legacy_refs: tuple[str, ...]
    market_regimes: tuple[str, ...]
    style_bias: tuple[str, ...]
    needs_intraday: bool
    description: str


def load_technical_modules(path: Path | None = None) -> list[TechnicalModule]:
    config_path = path or (CONFIGS_DIR / "technical_module_registry.json")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return [
        TechnicalModule(
            module_id=item["module_id"],
            family=item["family"],
            role=item["role"],
            priority=item["priority"],
            legacy_refs=tuple(item.get("legacy_refs", [])),
            market_regimes=tuple(item.get("market_regimes", [])),
            style_bias=tuple(item.get("style_bias", [])),
            needs_intraday=bool(item.get("needs_intraday", False)),
            description=item.get("description", ""),
        )
        for item in payload["modules"]
    ]


def recommend_modules_for_regime(
    snapshot: MarketRegimeSnapshot,
    *,
    can_watch_intraday: bool = True,
) -> list[TechnicalModule]:
    modules = load_technical_modules()
    recommended: list[tuple[int, TechnicalModule]] = []
    for module in modules:
        if snapshot.risk_mode not in module.market_regimes:
            continue
        if module.needs_intraday and not can_watch_intraday:
            continue

        score = 0
        if module.priority == "core":
            score += 30
        elif module.priority == "high":
            score += 20
        else:
            score += 10

        if snapshot.style_lead == "small_cap_lead" and any(
            tag in module.style_bias for tag in ("hot_theme", "sector_rotation", "repair_names", "emerging_theme")
        ):
            score += 8
        if snapshot.style_lead == "large_cap_lead" and any(
            tag in module.style_bias for tag in ("main_board", "large_mid_cap", "defensive")
        ):
            score += 8
        if snapshot.risk_mode == "risk_on" and any(
            tag in module.style_bias for tag in ("event_driven", "hot_theme", "repair_names", "sector_rotation")
        ):
            score += 6
        if snapshot.risk_mode == "risk_off" and any(
            tag in module.style_bias for tag in ("defensive", "all")
        ):
            score += 6
        if snapshot.theme_concentration == "high" and any(
            tag in module.style_bias for tag in ("hot_theme", "sector_rotation", "policy_theme")
        ):
            score += 5

        recommended.append((score, module))

    recommended.sort(key=lambda item: (-item[0], item[1].module_id))
    return [module for _, module in recommended]
