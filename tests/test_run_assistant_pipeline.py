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

    def test_market_data_precheck_prefers_fetched_market_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir) / "inbox"
            market_dir = inbox / "market_equity_daily"
            market_dir.mkdir(parents=True, exist_ok=True)
            (market_dir / "market_equity_daily_20260506.csv").write_text("stock_code,close\n", encoding="utf-8")
            fetched_market_path = market_dir / "market_equity_daily_20260507.csv"
            fetched_market_path.write_text("stock_code,close\n", encoding="utf-8")

            with patch.object(pipeline_cli, "INBOX_DIR", inbox):
                precheck = pipeline_cli._build_market_data_precheck(
                    "2026-05-08",
                    source_fetch_status="completed",
                    source_artifacts=[fetched_market_path],
                    strict_market_date=False,
                )

        self.assertEqual(precheck.effective_trade_date, "2026-05-07")
        self.assertEqual(precheck.fetched_market_date, "2026-05-07")
        self.assertTrue(precheck.used_source_fetch_market_date)
        self.assertTrue(any("trade_date_source_fetch_adjusted" in warning for warning in precheck.warnings))

    def test_market_data_precheck_reads_market_date_from_fetch_report_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            report_path = Path(tmp_dir) / "tushare_source_fetch_20260517.json"
            report_path.write_text(
                """
{
  "trade_date": "20260517",
  "artifacts": [
    {
      "source_id": "market_equity_daily",
      "path": "D:/TradingSystem/data/inbox/market_equity_daily/market_equity_daily_20260515.csv"
    }
  ],
  "warnings": []
}
                """.strip(),
                encoding="utf-8",
            )
            precheck = pipeline_cli._build_market_data_precheck(
                "2026-05-17",
                source_fetch_status="completed",
                source_artifacts=[report_path],
                strict_market_date=False,
            )

        self.assertEqual(precheck.fetched_market_date, "2026-05-15")
        self.assertEqual(precheck.effective_trade_date, "2026-05-15")
        self.assertTrue(precheck.used_source_fetch_market_date)

    def test_market_data_precheck_strict_mode_fails_without_fresh_market_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            inbox = Path(tmp_dir) / "inbox"
            market_dir = inbox / "market_equity_daily"
            market_dir.mkdir(parents=True, exist_ok=True)
            (market_dir / "market_equity_daily_20260506.csv").write_text("stock_code,close\n", encoding="utf-8")

            with patch.object(pipeline_cli, "INBOX_DIR", inbox):
                with self.assertRaises(RuntimeError):
                    pipeline_cli._build_market_data_precheck(
                        "2026-05-08",
                        source_fetch_status="skipped",
                        source_artifacts=[],
                        strict_market_date=True,
                    )

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
                            _fake_artifact("macro"),
                            Path(tmp_dir) / "event.md",
                            Path(tmp_dir) / "theme.md",
                            Path(tmp_dir) / "macro.md",
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
                        "build_setup_performance_cli",
                        return_value=(_fake_artifact("setup_eval"), Path(tmp_dir) / "setup_eval.md"),
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
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_trade_execution_sheet",
                        return_value=(_fake_artifact("trade_execution"), Path(tmp_dir) / "trade_execution.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "sync_trade_execution_to_live_state",
                        return_value=(_fake_artifact("auto_holdings"), _fake_artifact("trade_log"), _fake_artifact("holdings_snapshot")),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_execution_feedback_cli",
                        return_value=(_fake_artifact("execution_feedback"), Path(tmp_dir) / "execution_feedback.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_execution_behavior_cli",
                        return_value=(_fake_artifact("execution_behavior"), Path(tmp_dir) / "execution_behavior.md"),
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
            self.assertTrue(any(stage[0] == "market_data_precheck" for stage in stage_outputs))
            self.assertTrue(any("trade_date_fallback" in warning for warning in warnings))
            self.assertTrue(report_path.exists())

    def test_run_pipeline_skips_llm_runtime_when_mode_is_off(self) -> None:
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

            with ExitStack() as stack:
                stack.enter_context(patch.object(pipeline_cli, "INBOX_DIR", inbox))
                stack.enter_context(patch.object(pipeline_cli, "_daily_report_dir", return_value=report_dir))
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
                            _fake_artifact("macro"),
                            Path(tmp_dir) / "event.md",
                            Path(tmp_dir) / "theme.md",
                            Path(tmp_dir) / "macro.md",
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
                        "build_setup_performance_cli",
                        return_value=(_fake_artifact("setup_eval"), Path(tmp_dir) / "setup_eval.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_review_memory_cli",
                        return_value=(_fake_artifact("memory"), Path(tmp_dir) / "memory.md"),
                    )
                )
                build_workpacks = stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_llm_workpacks_cli",
                        return_value=(_fake_artifact("workpacks"), Path(tmp_dir) / "workpacks.md"),
                    )
                )
                plan_execution = stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "plan_llm_execution",
                        return_value=(_fake_artifact("llm_exec"), Path(tmp_dir) / "llm_exec.md"),
                    )
                )
                execute_runtime = stack.enter_context(patch.object(pipeline_cli, "execute_llm_runtime"))
                apply_enrichments = stack.enter_context(patch.object(pipeline_cli, "apply_llm_enrichments"))
                stack.enter_context(patch.object(pipeline_cli, "refresh_holdings_snapshot", return_value=_fake_artifact("holdings")))
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_preopen_summary",
                        return_value=(_fake_artifact("preopen"), Path(tmp_dir) / "preopen.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_trade_execution_sheet",
                        return_value=(_fake_artifact("trade_execution"), Path(tmp_dir) / "trade_execution.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "sync_trade_execution_to_live_state",
                        return_value=(_fake_artifact("auto_holdings"), _fake_artifact("trade_log"), _fake_artifact("holdings_snapshot")),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_execution_feedback_cli",
                        return_value=(_fake_artifact("execution_feedback"), Path(tmp_dir) / "execution_feedback.md"),
                    )
                )
                stack.enter_context(
                    patch.object(
                        pipeline_cli,
                        "build_execution_behavior_cli",
                        return_value=(_fake_artifact("execution_behavior"), Path(tmp_dir) / "execution_behavior.md"),
                    )
                )

                report_path, stage_outputs, warnings = pipeline_cli.run_assistant_pipeline(
                    "2026-05-08",
                    llm_mode="off",
                )

            self.assertTrue(report_path.exists())
            build_workpacks.assert_called_once_with("2026-05-06", mode="off")
            plan_execution.assert_called_once_with("2026-05-06", mode="off")
            execute_runtime.assert_not_called()
            apply_enrichments.assert_not_called()
            self.assertTrue(any(stage[0] == "llm_runtime" and stage[1] == "skipped" for stage in stage_outputs))
            self.assertTrue(any("llm_mode=off" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
