from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import trading_system.cli.build_candidate_cards as candidate_cli


class _UnavailableScanner:
    def is_available(self, trade_date: str) -> bool:
        return False


class BuildCandidateCardsCliTest(unittest.TestCase):
    def test_refresh_bundle_and_collect_scanner_warnings(self) -> None:
        payload = {
            "market_regime": {
                "snapshot_id": "s1",
                "trade_date": "2026-05-06",
                "market_bias": "bullish",
                "risk_mode": "risk_on",
                "breadth_strength": "strong",
                "limit_up_temperature": "warm",
                "turnover_regime": "high",
                "style_lead": "large_cap_lead",
                "theme_concentration": "high",
                "opening_risk_note": "",
                "confidence": 0.8,
                "supporting_evidence": [],
            },
            "account_constraints": {
                "profile_name": "acct",
                "capital_total": 43000.0,
                "capital_liquid_ratio_min": 0.1,
                "single_position_max_pct": 1.0,
                "single_trade_capital_max": 43000.0,
                "max_holdings": 5,
                "max_new_positions_per_day": 2,
                "max_portfolio_turnover_per_day": 0.4,
                "daily_drawdown_alert_pct": 0.03,
                "portfolio_drawdown_alert_pct": 0.08,
                "preferred_holding_horizon_days": 3,
                "execution_mode": "manual",
                "can_watch_intraday": True,
                "preopen_available": True,
                "midday_available": True,
                "close_available": True,
                "avoid_chasing_limit_up": True,
                "avoid_low_liquidity": True,
                "main_board_only": True,
                "notes": "",
            },
            "technical_modules": [
                {
                    "module_id": "TM001_line_a_trend_continuation",
                    "family": "trend_continuation",
                    "role": "candidate_generator",
                    "priority": "core",
                    "legacy_refs": [],
                    "market_regimes": ["risk_on"],
                    "style_bias": ["main_board"],
                    "needs_intraday": False,
                    "description": "",
                }
            ],
            "event_cards": [],
            "theme_cards": [],
            "capital_behavior_cards": [],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            fake_json = Path(tmp_dir) / "candidate_cards.json"
            outputs_dir = Path(tmp_dir) / "outputs"
            processed_dir = Path(tmp_dir) / "processed"
            with patch.object(candidate_cli, "build_analysis_bundle") as build_bundle, patch.object(
                candidate_cli, "_load_assistant_bundle", return_value=payload
            ), patch.object(
                candidate_cli,
                "load_scanners_for_modules",
                return_value={"TM001_line_a_trend_continuation": _UnavailableScanner()},
            ), patch.object(
                candidate_cli, "load_text_signal_watch", return_value=[]
            ), patch.object(candidate_cli, "build_candidate_cards", return_value=[]), patch.object(
                candidate_cli, "save_candidate_cards", return_value=fake_json
            ), patch.object(candidate_cli, "render_candidate_cards_markdown", return_value="# test\n"), patch.object(
                candidate_cli, "OUTPUTS_DIR", outputs_dir
            ), patch.object(
                candidate_cli, "PROCESSED_DATA_DIR", processed_dir
            ):
                json_path, md_path, module_signal_json, module_signal_md, warnings = candidate_cli.build_candidate_cards_from_bundle(
                    "2026-05-06",
                    refresh_bundle=True,
                )

            build_bundle.assert_called_once_with("2026-05-06")
            self.assertEqual(json_path, fake_json)
            self.assertEqual(md_path, outputs_dir / "analysis" / "candidate_cards_2026-05-06.md")
            self.assertEqual(module_signal_json, processed_dir / "module_signals" / "module_signals_2026-05-06.json")
            self.assertEqual(module_signal_md, outputs_dir / "analysis" / "module_signals_2026-05-06.md")
            self.assertTrue(module_signal_json.exists())
            self.assertIn("scanner_unavailable: TM001_line_a_trend_continuation for 2026-05-06", warnings)

    def test_candidate_cli_loads_only_prior_setup_policy(self) -> None:
        payload = {
            "market_regime": {
                "snapshot_id": "s1",
                "trade_date": "2026-05-15",
                "market_bias": "bullish",
                "risk_mode": "risk_on",
                "breadth_strength": "strong",
                "limit_up_temperature": "warm",
                "turnover_regime": "high",
                "style_lead": "large_cap_lead",
                "theme_concentration": "high",
                "opening_risk_note": "",
                "confidence": 0.8,
                "supporting_evidence": [],
            },
            "account_constraints": {
                "profile_name": "acct",
                "capital_total": 43000.0,
                "capital_liquid_ratio_min": 0.1,
                "single_position_max_pct": 1.0,
                "single_trade_capital_max": 43000.0,
                "max_holdings": 5,
                "max_new_positions_per_day": 2,
                "max_portfolio_turnover_per_day": 0.4,
                "daily_drawdown_alert_pct": 0.03,
                "portfolio_drawdown_alert_pct": 0.08,
                "preferred_holding_horizon_days": 3,
                "execution_mode": "manual",
                "can_watch_intraday": True,
                "preopen_available": True,
                "midday_available": True,
                "close_available": True,
                "avoid_chasing_limit_up": True,
                "avoid_low_liquidity": True,
                "main_board_only": True,
                "notes": "",
            },
            "technical_modules": [],
            "event_cards": [],
            "theme_cards": [],
            "macro_event_cards": [],
            "capital_behavior_cards": [],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            processed_dir = root / "processed"
            outputs_dir = root / "outputs"
            evaluation_dir = processed_dir / "evaluation"
            evaluation_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir.mkdir(parents=True, exist_ok=True)
            (evaluation_dir / "setup_performance_2026-05-07.json").write_text(
                json.dumps(
                    {
                        "setup_summary": [
                            {
                                "setup_type": "leader_acceleration",
                                "sample_count": 5,
                                "buy_pilot_count": 3,
                                "buy_pilot_horizons": {
                                    "3d": {"avg_return": -0.03, "win_rate": 0.2, "hit_rate_3pct": 0.0}
                                },
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (evaluation_dir / "setup_performance_2026-05-15.json").write_text(
                json.dumps(
                    {
                        "setup_summary": [
                            {
                                "setup_type": "leader_acceleration",
                                "sample_count": 9,
                                "buy_pilot_count": 6,
                                "buy_pilot_horizons": {
                                    "3d": {"avg_return": 0.08, "win_rate": 0.8, "hit_rate_3pct": 0.6}
                                },
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            fake_json = root / "candidate_cards.json"
            with patch.object(candidate_cli, "_load_assistant_bundle", return_value=payload), patch.object(
                candidate_cli,
                "load_scanners_for_modules",
                return_value={},
            ), patch.object(candidate_cli, "load_text_signal_watch", return_value=[]), patch.object(
                candidate_cli, "save_candidate_cards", return_value=fake_json
            ), patch.object(candidate_cli, "render_candidate_cards_markdown", return_value="# test\n"), patch.object(
                candidate_cli, "OUTPUTS_DIR", outputs_dir
            ), patch.object(
                candidate_cli, "PROCESSED_DATA_DIR", processed_dir
            ), patch.object(candidate_cli, "build_candidate_cards", return_value=[]) as build_cards:
                candidate_cli.build_candidate_cards_from_bundle("2026-05-15", refresh_bundle=False)

            setup_policy = build_cards.call_args.kwargs["setup_policy"]
            self.assertEqual(setup_policy["leader_acceleration"].status, "disabled")

    def test_candidate_cli_blends_prior_execution_feedback_into_setup_policy(self) -> None:
        payload = {
            "market_regime": {
                "snapshot_id": "s1",
                "trade_date": "2026-05-15",
                "market_bias": "bullish",
                "risk_mode": "risk_on",
                "breadth_strength": "strong",
                "limit_up_temperature": "warm",
                "turnover_regime": "high",
                "style_lead": "large_cap_lead",
                "theme_concentration": "high",
                "opening_risk_note": "",
                "confidence": 0.8,
                "supporting_evidence": [],
            },
            "account_constraints": {
                "profile_name": "acct",
                "capital_total": 43000.0,
                "capital_liquid_ratio_min": 0.1,
                "single_position_max_pct": 1.0,
                "single_trade_capital_max": 43000.0,
                "max_holdings": 5,
                "max_new_positions_per_day": 2,
                "max_portfolio_turnover_per_day": 0.4,
                "daily_drawdown_alert_pct": 0.03,
                "portfolio_drawdown_alert_pct": 0.08,
                "preferred_holding_horizon_days": 3,
                "execution_mode": "manual",
                "can_watch_intraday": True,
                "preopen_available": True,
                "midday_available": True,
                "close_available": True,
                "avoid_chasing_limit_up": True,
                "avoid_low_liquidity": True,
                "main_board_only": True,
                "notes": "",
            },
            "technical_modules": [],
            "event_cards": [],
            "theme_cards": [],
            "macro_event_cards": [],
            "capital_behavior_cards": [],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            processed_dir = root / "processed"
            outputs_dir = root / "outputs"
            evaluation_dir = processed_dir / "evaluation"
            evaluation_dir.mkdir(parents=True, exist_ok=True)
            outputs_dir.mkdir(parents=True, exist_ok=True)
            (evaluation_dir / "setup_performance_2026-05-07.json").write_text(
                json.dumps(
                    {
                        "setup_summary": [
                            {
                                "setup_type": "leader_acceleration",
                                "sample_count": 5,
                                "buy_pilot_count": 3,
                                "buy_pilot_horizons": {
                                    "3d": {"avg_return": 0.04, "win_rate": 0.66, "hit_rate_3pct": 0.33}
                                },
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (evaluation_dir / "execution_feedback_2026-05-09.json").write_text(
                json.dumps(
                    {
                        "setup_summary": [
                            {
                                "setup_type": "leader_acceleration",
                                "closed_trade_count": 2,
                                "avg_realized_return": -0.04,
                                "win_rate": 0.0,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            fake_json = root / "candidate_cards.json"
            with patch.object(candidate_cli, "_load_assistant_bundle", return_value=payload), patch.object(
                candidate_cli,
                "load_scanners_for_modules",
                return_value={},
            ), patch.object(candidate_cli, "load_text_signal_watch", return_value=[]), patch.object(
                candidate_cli, "save_candidate_cards", return_value=fake_json
            ), patch.object(candidate_cli, "render_candidate_cards_markdown", return_value="# test\n"), patch.object(
                candidate_cli, "OUTPUTS_DIR", outputs_dir
            ), patch.object(
                candidate_cli, "PROCESSED_DATA_DIR", processed_dir
            ), patch.object(candidate_cli, "build_candidate_cards", return_value=[]) as build_cards:
                candidate_cli.build_candidate_cards_from_bundle("2026-05-15", refresh_bundle=False)

            setup_policy = build_cards.call_args.kwargs["setup_policy"]
            self.assertEqual(setup_policy["leader_acceleration"].status, "disabled")
            self.assertIn("execution_feedback_underperformance", setup_policy["leader_acceleration"].notes)


if __name__ == "__main__":
    unittest.main()
