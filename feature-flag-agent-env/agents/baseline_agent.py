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

        if error_rate > 15:
            return FeatureFlagAction(
                action_type="ROLLBACK",
                target_percentage=0.0,
                reason=f"Critical error rate ({error_rate:.1f}%)"
            )

        elif error_rate > 7:
            return FeatureFlagAction(
                action_type="DECREASE_ROLLOUT",
                target_percentage=max(0.0, current_rollout - 20),
                reason=f"High error rate ({error_rate:.1f}%)"
            )

        elif error_rate > 3:
            return FeatureFlagAction(
                action_type="MAINTAIN",
                target_percentage=current_rollout,
                reason=f"Moderate error rate ({error_rate:.1f}%)"
            )

        else:
            return FeatureFlagAction(
                action_type="INCREASE_ROLLOUT",
                target_percentage=min(100.0, current_rollout + 15),
                reason=f"Low error rate ({error_rate:.1f}%)"
            )