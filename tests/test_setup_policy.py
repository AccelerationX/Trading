from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trading_system.evaluation.setup_policy import derive_setup_policy


class SetupPolicyTest(unittest.TestCase):
    def test_execution_feedback_can_disable_setup(self) -> None:
        setup_performance = {
            "setup_summary": [
                {
                    "setup_type": "leader_acceleration",
                    "sample_count": 8,
                    "buy_pilot_count": 4,
                    "buy_pilot_horizons": {
                        "3d": {"avg_return": 0.05, "win_rate": 0.75, "hit_rate_3pct": 0.50}
                    },
                }
            ]
        }
        execution_feedback = {
            "setup_summary": [
                {
                    "setup_type": "leader_acceleration",
                    "closed_trade_count": 3,
                    "avg_realized_return": -0.05,
                    "win_rate": 0.0,
                }
            ]
        }

        policy = derive_setup_policy(setup_performance, execution_feedback=execution_feedback)

        self.assertEqual(policy["leader_acceleration"].status, "disabled")
        self.assertEqual(policy["leader_acceleration"].position_cap_multiplier, 0.0)
        self.assertIn("execution_feedback_underperformance", policy["leader_acceleration"].notes)

    def test_execution_feedback_can_favor_setup(self) -> None:
        setup_performance = {
            "setup_summary": [
                {
                    "setup_type": "event_ignition",
                    "sample_count": 5,
                    "buy_pilot_count": 3,
                    "buy_pilot_horizons": {
                        "3d": {"avg_return": 0.02, "win_rate": 0.5, "hit_rate_3pct": 0.3}
                    },
                }
            ]
        }
        execution_feedback = {
            "setup_summary": [
                {
                    "setup_type": "event_ignition",
                    "closed_trade_count": 3,
                    "avg_realized_return": 0.06,
                    "win_rate": 0.67,
                }
            ]
        }

        policy = derive_setup_policy(setup_performance, execution_feedback=execution_feedback)

        self.assertEqual(policy["event_ignition"].status, "favored")
        self.assertGreaterEqual(policy["event_ignition"].score_multiplier, 1.10)
        self.assertLessEqual(policy["event_ignition"].action_score_floor, 0.54)
        self.assertIn("execution_feedback_positive", policy["event_ignition"].notes)

    def test_execution_behavior_can_make_setup_cautious(self) -> None:
        setup_performance = {
            "setup_summary": [
                {
                    "setup_type": "trend_follow_thrust",
                    "sample_count": 8,
                    "buy_pilot_count": 4,
                    "buy_pilot_horizons": {
                        "3d": {"avg_return": 0.03, "win_rate": 0.55, "hit_rate_3pct": 0.30}
                    },
                }
            ]
        }
        execution_behavior = {
            "setup_summary": [
                {
                    "setup_type": "trend_follow_thrust",
                    "finalized_count": 3,
                    "fill_rate": 0.33,
                    "skip_rate": 0.67,
                    "partial_rate": 0.0,
                    "avg_buy_slippage_pct": 0.03,
                }
            ]
        }

        policy = derive_setup_policy(setup_performance, execution_behavior=execution_behavior)

        self.assertEqual(policy["trend_follow_thrust"].status, "cautious")
        self.assertGreaterEqual(policy["trend_follow_thrust"].action_score_floor, 0.66)
        self.assertIn("execution_followthrough_weak", policy["trend_follow_thrust"].notes)
        self.assertIn("execution_buy_slippage_high", policy["trend_follow_thrust"].notes)


if __name__ == "__main__":
    unittest.main()
