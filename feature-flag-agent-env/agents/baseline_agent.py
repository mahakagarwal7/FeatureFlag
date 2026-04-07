import os
import sys

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation


class BaselineAgent:
    """
    Simple rule-based agent.

    Rules:
    - If errors < 3%: Increase rollout by 15%
    - If errors 3-7%: Maintain
    - If errors > 7%: Decrease rollout by 20%
    - If errors > 15%: Rollback
    """

    def decide(self, observation: FeatureFlagObservation, history):
        error_rate = observation.error_rate * 100
        current_rollout = observation.current_rollout_percentage
        active_task = os.getenv("FF_ACTIVE_TASK", "").strip().lower()
        debug = os.getenv("FF_DEBUG_DECISIONS", "0") == "1"

        if active_task == "task2":
            # Task2 prefers a safer plateau around 65% and must never exceed 70%.
            if error_rate > 12:
                action = FeatureFlagAction(
                    action_type="ROLLBACK",
                    target_percentage=max(0.0, current_rollout - 40),
                    reason=f"Task2 severe incident ({error_rate:.1f}%)"
                )
            elif error_rate > 6:
                action = FeatureFlagAction(
                    action_type="DECREASE_ROLLOUT",
                    target_percentage=max(0.0, current_rollout - 20),
                    reason=f"Task2 high error ({error_rate:.1f}%)"
                )
            elif error_rate > 2.5:
                action = FeatureFlagAction(
                    action_type="MAINTAIN",
                    target_percentage=current_rollout,
                    reason=f"Task2 caution zone ({error_rate:.1f}%)"
                )
            else:
                if current_rollout >= 65.0:
                    action = FeatureFlagAction(
                        action_type="MAINTAIN",
                        target_percentage=current_rollout,
                        reason="Task2 safe plateau reached (>=65%)"
                    )
                else:
                    action = FeatureFlagAction(
                        action_type="INCREASE_ROLLOUT",
                        target_percentage=min(65.0, current_rollout + 10),
                        reason=f"Task2 low error ({error_rate:.1f}%)"
                    )

            action.target_percentage = min(action.target_percentage, 70.0)

            if debug:
                print(f"[BASELINE DEBUG] err={error_rate:.2f}% rollout={current_rollout:.1f}% -> {action.action_type} {action.target_percentage:.1f}%", file=sys.stderr)
            return action

        if error_rate > 15:
            action = FeatureFlagAction(
                action_type="ROLLBACK",
                target_percentage=0.0,
                reason=f"Critical error rate ({error_rate:.1f}%)"
            )

        elif error_rate > 7:
            action = FeatureFlagAction(
                action_type="DECREASE_ROLLOUT",
                target_percentage=max(0.0, current_rollout - 20),
                reason=f"High error rate ({error_rate:.1f}%)"
            )

        elif error_rate > 3:
            action = FeatureFlagAction(
                action_type="MAINTAIN",
                target_percentage=current_rollout,
                reason=f"Moderate error rate ({error_rate:.1f}%)"
            )

        else:
            if active_task == "task1":
                # Task1 favors conservative stable rollout around 25%.
                if current_rollout >= 25.0:
                    action = FeatureFlagAction(
                        action_type="MAINTAIN",
                        target_percentage=current_rollout,
                        reason="Task1 safe plateau reached (>=25%)"
                    )
                else:
                    action = FeatureFlagAction(
                        action_type="INCREASE_ROLLOUT",
                        target_percentage=min(25.0, current_rollout + 10),
                        reason=f"Task1 low error ({error_rate:.1f}%)"
                    )
            else:
                action = FeatureFlagAction(
                    action_type="INCREASE_ROLLOUT",
                    target_percentage=min(100.0, current_rollout + 10),
                    reason=f"Low error rate ({error_rate:.1f}%)"
                )

        if debug:
            print(f"[BASELINE DEBUG] err={error_rate:.2f}% rollout={current_rollout:.1f}% -> {action.action_type} {action.target_percentage:.1f}%", file=sys.stderr)
        return action