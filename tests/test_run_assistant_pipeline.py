from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import trading_system.cli.run_assistant_pipeline as pipeline_cli


class RunAssistantPipelineTest(unittest.TestCase):
    def test_resolve_effective_trade_date_falls_back_to_latest_local_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir) / "inbox"
            market_dir = inbox / "market_equity_daily"
            market_dir.mkdir(parents=True, exist_ok=True)
            (market_dir / "market_equity_daily_20260506.csv").write_text("stock_code,close\n", encoding="utf-8")

            with patch.object(pipeline_cli, "INBOX_DIR", inbox):
                effective, warning = pipeline_cli._resolve_effective_trade_date("2026-05-08")

        self.assertEqual(effective, "2026-05-06")
        self.assertIsNotNone(warning)
        self.assertIn("requested 2026-05-08", warning or "")
        self.assertIn("using 2026-05-06", warning or "")

    def test_run_source_fetch_best_effort_returns_skipped_when_all_sources_fail(self) -> None:
        with patch.object(pipeline_cli, "fetch_tushare_supported_sources", side_effect=RuntimeError("tushare blocked")), patch.object(
            pipeline_cli,
            "fetch_official_text_sources",
            side_effect=RuntimeError("official blocked"),
        ):
            status, artifacts, warnings = pipeline_cli._run_source_fetch_best_effort("2026-05-08")

        self.assertEqual(status, "skipped")
        self.assertEqual(artifacts, [])
        self.assertEqual(len(warnings), 2)
        self.assertIn("source_fetch_tushare_failed", warnings[0])
        self.assertIn("source_fetch_official_failed", warnings[1])

    def test_run_pipeline_continues_with_local_cache_when_source_fetch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir) / "inbox"
            market_dir = inbox / "market_equity_daily"
            market_dir.mkdir(parents=True, exist_ok=True)
            (market_dir / "market_equity_daily_20260506.csv").write_text("stock_code,close\n", encoding="utf-8")

            report_dir = Path(tmp_dir) / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)

            def _fake_artifact(name: str) -> Path:
                path = Path(tmp_dir) / f"{name}.json"
                path.write_text("{}", encoding="utf-8")
                return path

            fake_runtime_json = _fake_artifact("llm_runtime")
            fake_runtime_md = Path(tmp_dir) / "llm_runtime.md"
            fake_runtime_md.write_text("# runtime\n", encoding="utf-8")

            with ExitStack() as stack:
                stack.enter_context(patch.object(pipeline_cli, "INBOX_DIR", inbox))
                stack.enter_context(patch.object(pipeline_cli, "_daily_report_dir", return_value=report_dir))
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "_run_source_fetch_best_effort",
                        return_value=("skipped", [], ["source_fetch_tushare_failed: blocked"]),
                    )
                )
                stack.enter_context(patch.object(pipeline_cli, "_run_account_refresh", return_value=_fake_artifact("account")))
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_market_regime",
                        return_value=(_fake_artifact("market"), Path(tmp_dir) / "market.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_event_and_theme_cards",
                        return_value=(
                            _fake_artifact("event"),
                            _fake_artifact("theme"),
                            Path(tmp_dir) / "event.md",
                            Path(tmp_dir) / "theme.md",
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_text_signal_watch_cli",
                        return_value=(_fake_artifact("text_watch"), Path(tmp_dir) / "text_watch.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_capital_behavior_cards_cli",
                        return_value=(_fake_artifact("capital"), Path(tmp_dir) / "capital.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_analysis_bundle",
                        return_value=(_fake_artifact("bundle"), Path(tmp_dir) / "bundle.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "sync_stock_history_from_market_daily",
                        return_value=(_fake_artifact("sync"), Path(tmp_dir) / "sync.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_candidate_cards_from_bundle",
                        return_value=(
                            _fake_artifact("candidate"),
                            Path(tmp_dir) / "candidate.md",
                            _fake_artifact("module_signals"),
                            Path(tmp_dir) / "module_signals.md",
                            [],
                        ),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_trade_plan_cards_cli",
                        return_value=(_fake_artifact("trade_plan"), Path(tmp_dir) / "trade_plan.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_module_evaluation_cli",
                        return_value=(_fake_artifact("module_eval"), Path(tmp_dir) / "module_eval.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_review_memory_cli",
                        return_value=(_fake_artifact("memory"), Path(tmp_dir) / "memory.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_llm_workpacks_cli",
                        return_value=(_fake_artifact("workpacks"), Path(tmp_dir) / "workpacks.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "plan_llm_execution",
                        return_value=(_fake_artifact("llm_exec"), Path(tmp_dir) / "llm_exec.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "execute_llm_runtime",
                        return_value=(fake_runtime_json, fake_runtime_md, []),
                    )
                )
                stack.enter_context(patch.object(pipeline_cli, "refresh_holdings_snapshot", return_value=_fake_artifact("holdings")))
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_preopen_summary",
                        return_value=(_fake_artifact("preopen"), Path(tmp_dir) / "preopen.md"),
                    )
                )
                stack.enter_context(patch.object(pipeline_cli, "_has_enabled_remote_llm_provider", return_value=False))

                report_path, stage_outputs, warnings = pipeline_cli.run_assistant_pipeline(
                    "2026-05-08",
                    include_source_fetch=True,
                    include_live_llm=False,
                    live_llm_limit=1,
                )

            self.assertEqual(report_path.name, "assistant_pipeline_run_2026-05-06.md")
            self.assertEqual(stage_outputs[0][0], "source_fetch")
            self.assertEqual(stage_outputs[0][1], "skipped")
            self.assertTrue(any("trade_date_fallback" in warning for warning in warnings))
            self.assertTrue(report_path.exists())


if __name__ == "__main__":
    unittest.main()
