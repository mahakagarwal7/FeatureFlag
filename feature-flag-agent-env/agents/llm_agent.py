import os
import json
import ast
import time
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Keep agent usable even if dotenv isn't installed.
    load_dotenv = None

from feature_flag_env.models import FeatureFlagAction, FeatureFlagObservation


if load_dotenv is not None:
    # Load environment variables from common .env locations.
    load_dotenv()
    env_candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
        Path(__file__).resolve().parents[3] / ".env",
    ]
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)


class LLMAgent:
    def __init__(self, model: str = ""):
        self.model = model or os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.api_base_url = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
        self.api_key = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
        self.timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
        self.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
        self.retry_backoff_seconds = float(os.getenv("OPENAI_RETRY_BACKOFF_SECONDS", "1.5"))
        self.debug = os.getenv("FF_DEBUG_API", "0") == "1"
        self.api_calls = 0
        self.api_failures = 0
        self.last_error = None

        if not self.api_key:
            print("WARNING: HF_TOKEN/OPENAI_API_KEY not set. Using fallback.", file=sys.stderr)
            self.use_baseline = True
        else:
            self.use_baseline = False
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.api_base_url,
                    timeout=self.timeout_seconds,
                )
            except ImportError:
                print("WARNING: openai package not installed. Using fallback.", file=sys.stderr)
                self.use_baseline = True
            except Exception as exc:
                print(f"WARNING: Failed to initialize OpenAI client: {exc}. Using fallback.", file=sys.stderr)
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
            "SCALE_DOWN": "DECREASE_ROLLOUT",
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

    def _resolve_target_percentage(self, raw_target, action_type: str, current_rollout: float) -> float:
        try:
            target = float(raw_target)
        except (TypeError, ValueError):
            target = current_rollout

        if action_type in {"MAINTAIN", "HALT_ROLLOUT"}:
            target = current_rollout
        elif action_type == "FULL_ROLLOUT":
            target = 100.0
        elif action_type == "ROLLBACK":
            target = 0.0
        elif action_type == "INCREASE_ROLLOUT" and target <= current_rollout:
            target = min(100.0, current_rollout + 10.0)
        elif action_type == "DECREASE_ROLLOUT" and target >= current_rollout:
            target = max(0.0, current_rollout - 10.0)

        return max(0.0, min(100.0, target))

    def _fallback(self, observation, history):
        from agents.baseline_agent import BaselineAgent
        return BaselineAgent().decide(observation, history)

    def _should_retry(self, exc: Exception) -> bool:
        """Retry on transient/rate-limit API errors."""
        status_code = getattr(exc, "status_code", None)
        if status_code in {408, 409, 429, 500, 502, 503, 504}:
            return True
        text = str(exc).lower()
        return (
            "429" in text
            or "rate limit" in text
            or "too many requests" in text
            or "timeout" in text
            or "temporar" in text
        )

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

For task2, aim for a final rollout around 65-70% and avoid overshooting above 70% unless you have a strong reason.

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
 "target_percentage": number,
 "reason": "..."
}}
"""

            response = None
            last_exc: Exception | None = None
            for attempt in range(self.max_retries + 1):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a rollout controller. Return strict JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.7,
                        response_format={"type": "json_object"},
                    )
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt >= self.max_retries or not self._should_retry(exc):
                        raise
                    sleep_for = self.retry_backoff_seconds * (2 ** attempt)
                    if self.debug:
                        print(
                            f"[LLM DEBUG] transient API error, retrying in {sleep_for:.1f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                    time.sleep(sleep_for)

            if response is None and last_exc is not None:
                raise last_exc

            content = response.choices[0].message.content
            data = self._parse_llm_json(content)
            normalized_action = self._normalize_action_type(data.get("action_type"))
            target_percentage = self._resolve_target_percentage(
                data.get("target_percentage"),
                normalized_action,
                observation.current_rollout_percentage,
            )
            reason = (data.get("reason") or "").strip() or "LLM decision"

            # Anti-stall nudge: at rollout 0 with healthy metrics, avoid repeated hold/halt loops.
            if (
                observation.current_rollout_percentage <= 0.0
                and observation.error_rate < 0.05
                and normalized_action in {"MAINTAIN", "HALT_ROLLOUT", "ROLLBACK"}
            ):
                normalized_action = "INCREASE_ROLLOUT"
                target_percentage = 10.0
                reason = f"{reason} | startup nudge to avoid zero-rollout stall"

            return FeatureFlagAction(
                action_type=normalized_action,
                target_percentage=target_percentage,
                reason=reason,
            )

        except Exception as exc:
            self.api_failures += 1
            self.last_error = str(exc)
            # Avoid hammering API after repeated hard failures.
            if self._should_retry(exc):
                self.use_baseline = True
            if self.debug:
                print(f"[LLM DEBUG] API failure #{self.api_failures}: {exc}")
            return self._fallback(observation, history)