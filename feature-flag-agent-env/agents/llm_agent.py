import os
import json
import ast
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Keep agent usable even if dotenv isn't installed.
    load_dotenv = None

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation


if load_dotenv is not None:
    # Load from current working directory first.
    load_dotenv()
    # Also load repository-level .env when invoked from nested folders.
    project_env = Path(__file__).resolve().parents[1] / ".env"
    if project_env.exists():
        load_dotenv(dotenv_path=project_env)


class LLMAgent:
    def __init__(self, model: str = "llama-3.1-8b-instant"):
        self.model = model
        self.api_key = os.getenv("GROQ_API_KEY")
        self.timeout_seconds = float(os.getenv("GROQ_TIMEOUT_SECONDS", "20"))
        self.debug = os.getenv("FF_DEBUG_API", "0") == "1"
        self.api_calls = 0
        self.api_failures = 0
        self.last_error = None

        if not self.api_key:
            print("⚠️  GROQ_API_KEY not set. Using fallback.")
            self.use_baseline = True
        else:
            self.use_baseline = False
            try:
                from groq import Groq
                self.client = Groq(api_key=self.api_key, timeout=self.timeout_seconds)
            except ImportError:
                print("⚠️ groq not installed. Using fallback.")
                self.use_baseline = True
            except Exception as exc:
                print(f"⚠️ Failed to initialize Groq client: {exc}. Using fallback.")
                self.use_baseline = True

        if self.debug:
            status = "enabled" if not self.use_baseline else "fallback"
            print(f"[LLM DEBUG] startup status={status}, timeout={self.timeout_seconds}s")

    def _parse_llm_json(self, content: str):
        text = (content or "").strip()

        # Handle fenced code blocks like ```json ... ```
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start = text.find("{")
        if start != -1:
            depth = 0
            end = -1
            for idx in range(start, len(text)):
                if text[idx] == "{":
                    depth += 1
                elif text[idx] == "}":
                    depth -= 1
                    if depth == 0:
                        end = idx
                        break
            if end != -1:
                text = text[start:end + 1]

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Some models return Python dict-style single quotes.
            return ast.literal_eval(text)

    def _normalize_action_type(self, raw_action: str) -> str:
        action = (raw_action or "").strip().upper().replace("-", "_").replace(" ", "_")
        alias_map = {
            "INCREASE": "INCREASE_ROLLOUT",
            "CONTINUE": "INCREASE_ROLLOUT",
            "CONTINUE_ROLLOUT": "INCREASE_ROLLOUT",
            "SCALE_UP": "INCREASE_ROLLOUT",
            "SCALE_BACK": "DECREASE_ROLLOUT",
            "DECREASE": "DECREASE_ROLLOUT",
            "PAUSE": "HALT_ROLLOUT",
            "PAUSE_ROLLOUT": "HALT_ROLLOUT",
            "HOLD": "MAINTAIN",
            "KEEP": "MAINTAIN",
            "FULL": "FULL_ROLLOUT",
            "ROLL_OUT_ALL": "FULL_ROLLOUT",
            "ROLLBACK_ALL": "ROLLBACK",
        }
        if action in alias_map:
            return alias_map[action]

        valid_actions = {
            "INCREASE_ROLLOUT",
            "DECREASE_ROLLOUT",
            "MAINTAIN",
            "HALT_ROLLOUT",
            "FULL_ROLLOUT",
            "ROLLBACK",
        }
        if action in valid_actions:
            return action

        return "MAINTAIN"

    def _fallback(self, observation, history):
        from agents.baseline_agent import BaselineAgent
        return BaselineAgent().decide(observation, history)

    def decide(self, observation: FeatureFlagObservation, history):
        if self.use_baseline:
            if self.debug:
                print("[LLM DEBUG] baseline fallback active (no API call)")
            return self._fallback(observation, history)

        try:
            self.api_calls += 1
            if self.debug:
                print(
                    f"[LLM DEBUG] API call #{self.api_calls} "
                    f"rollout={observation.current_rollout_percentage:.1f}% "
                    f"error={observation.error_rate * 100:.2f}%"
                )

            prompt = f"""
Feature rollout decision:

Rollout: {observation.current_rollout_percentage}%
Error: {observation.error_rate*100:.2f}%
Latency: {observation.latency_p99_ms}
Adoption: {observation.user_adoption_rate}
Revenue: {observation.revenue_impact}
Health: {observation.system_health_score}

Allowed action_type values only:
- INCREASE_ROLLOUT
- DECREASE_ROLLOUT
- MAINTAIN
- HALT_ROLLOUT
- FULL_ROLLOUT
- ROLLBACK

Respond with JSON only (no markdown, no prose):
{{
 "action_type": "...",
 "target_percentage": number
}}
"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a rollout controller. Return strict JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            data = self._parse_llm_json(content)
            normalized_action = self._normalize_action_type(data.get("action_type"))
            target_percentage = float(data.get("target_percentage", observation.current_rollout_percentage))

            if normalized_action in {"MAINTAIN", "HALT_ROLLOUT"}:
                target_percentage = observation.current_rollout_percentage
            elif normalized_action == "FULL_ROLLOUT":
                target_percentage = 100.0
            elif normalized_action == "ROLLBACK":
                target_percentage = 0.0

            return FeatureFlagAction(
                action_type=normalized_action,
                target_percentage=max(0.0, min(100.0, target_percentage)),
                reason="LLM decision"
            )

        except Exception as exc:
            self.api_failures += 1
            self.last_error = str(exc)
            if self.debug:
                print(f"[LLM DEBUG] API failure #{self.api_failures}: {exc}")
            return self._fallback(observation, history)