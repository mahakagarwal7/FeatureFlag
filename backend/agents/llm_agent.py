import os
import json
import ast
import time
import sys
from pathlib import Path
import httpx

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
        requested_provider = os.getenv("LLM_PROVIDER", "auto").strip().lower()
        if requested_provider not in {"auto", "openai", "hf", "huggingface", "groq"}:
            requested_provider = "auto"

        openai_api_key = os.getenv("OPENAI_API_KEY")
        generic_api_key = os.getenv("API_KEY")
        hf_token = os.getenv("HF_TOKEN")

        if requested_provider in {"hf", "huggingface"}:
            self.provider = "hf"
        elif requested_provider == "openai":
            self.provider = "openai"
        elif requested_provider == "groq":
            self.provider = "groq"
        else:
            self.provider = "hf" if hf_token and not (openai_api_key or generic_api_key) else "openai"

        default_model = "Qwen/Qwen2.5-7B-Instruct" if self.provider == "hf" else "gpt-4o-mini"
        self.model = model or os.getenv("MODEL_NAME", default_model)
        self.api_base_url = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
        hf_api_base_url = os.getenv("HF_API_BASE_URL", "https://router.huggingface.co/v1")
        self.hf_chat_completions_url = os.getenv(
            "HF_CHAT_COMPLETIONS_URL",
            f"{hf_api_base_url.rstrip('/')}/chat/completions",
        )

        # Hackathon validator may inject API_KEY and API_BASE_URL for proxy metering.
        if self.provider == "hf":
            self.api_key = hf_token or generic_api_key or openai_api_key
        else:
            self.api_key = openai_api_key or generic_api_key or hf_token

        self.timeout_seconds = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
        self.max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
        self.retry_backoff_seconds = float(os.getenv("OPENAI_RETRY_BACKOFF_SECONDS", "1.5"))
        self.debug = os.getenv("FF_DEBUG_API", "0") == "1"
        self.api_calls = 0
        self.api_failures = 0
        self.last_error = None

        self.use_baseline = False
        self.client = None

        if self.provider == "groq":
            try:
                from groq import Groq  # Requires: pip install groq
                
                # Get API key from environment (with fallback)
                groq_api_key = (
                    os.getenv("GROQ_API_KEY")
                    or os.getenv("API_KEY")
                    or os.getenv("LLM_API_KEY")
                )
                
                if not groq_api_key:
                    print("WARNING: GROQ_API_KEY not set. Using fallback agent.", file=sys.stderr)
                    self.use_baseline = True
                    self.client = None
                else:
                    # Initialize Groq client with config
                    self.client = Groq(
                        api_key=groq_api_key,
                        timeout=int(os.getenv("GROQ_TIMEOUT_SECONDS", "20")),
                        max_retries=int(os.getenv("GROQ_MAX_RETRIES", "2")),
                    )
                    self.use_baseline = False
                    
                    # Optional: Log initialization for debugging
                    if os.getenv("FF_DEBUG_API", "0") == "1":
                        print(f"[LLM DEBUG] Groq client initialized (model={self.model})", file=sys.stderr)
                        
            except ImportError:
                print("WARNING: groq package not installed. Install with: pip install groq", file=sys.stderr)
                self.use_baseline = True
                self.client = None
            except Exception as exc:
                print(f"WARNING: Failed to initialize Groq client: {exc}", file=sys.stderr)
                self.use_baseline = True
                self.client = None
        else:
            if not self.api_key:
                print(
                    "WARNING: API_KEY/HF_TOKEN/OPENAI_API_KEY not set. Using fallback.",
                    file=sys.stderr,
                )
                self.use_baseline = True
            else:
                if self.provider == "openai":
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
            print(
                f"[LLM DEBUG] startup status={status}, provider={self.provider}, timeout={self.timeout_seconds}s",
                file=sys.stderr,
            )

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

    def _call_openai_completion(self, prompt: str):
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a rollout controller. Return strict JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content

    def _call_hf_completion(self, prompt: str):
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a rollout controller. Return strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }

        response = httpx.post(
            self.hf_chat_completions_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()

        choices = data.get("choices") if isinstance(data, dict) else None
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content")
            if content:
                return content

        if isinstance(data, list) and data and isinstance(data[0], dict):
            generated_text = data[0].get("generated_text")
            if generated_text:
                return generated_text

        if isinstance(data, dict) and data.get("generated_text"):
            return data["generated_text"]

        raise ValueError("Unexpected Hugging Face response format")

    def _call_llm(self, prompt: str) -> str:
        """ Unified LLM call supporting Groq, OpenAI, and HF providers."""
        
        if self.provider == "groq" and self.client is not None:
            # Groq uses OpenAI-compatible API
            response = self.client.chat.completions.create(
                model=self.model,  # e.g., "llama3-8b-8192"
                messages=[
                    {"role": "system", "content": "You are a feature flag rollout agent. Output JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.7")),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "500")),
                response_format={"type": "json_object"},  # Ensure JSON output
            )
            return response.choices[0].message.content
        
        elif self.provider == "openai":
            return self._call_openai_completion(prompt)
            
        elif self.provider == "hf":
            return self._call_hf_completion(prompt)
            
        raise RuntimeError(f"LLM provider '{self.provider}' not properly configured")

    def decide(self, observation: FeatureFlagObservation, history):
        if self.use_baseline:
            if self.debug:
                print("[LLM DEBUG] baseline fallback active (no API call)", file=sys.stderr)
            return self._fallback(observation, history)

        try:
            self.api_calls += 1
            if self.debug:
                print(
                    f"[LLM DEBUG] API call #{self.api_calls} "
                    f"rollout={observation.current_rollout_percentage:.1f}% "
                    f"error={observation.error_rate * 100:.2f}%",
                    file=sys.stderr,
                )

            prompt = f"""
{observation.to_prompt_string()}

Based on the MISSION & PHASE constraints above (if explicitly provided), strictly adhere to the `allowed_actions`.
Plan your progression step-by-step to fulfill the listed phase objectives without exceeding the target bounds or errors.
If no mission phase is specified, aim for a final stable rollout.

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
                    response = self._call_llm(prompt)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt >= self.max_retries or not self._should_retry(exc):
                        raise
                    sleep_for = self.retry_backoff_seconds * (2 ** attempt)
                    if self.debug:
                        print(
                            f"[LLM DEBUG] transient API error, retrying in {sleep_for:.1f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})",
                            file=sys.stderr,
                        )
                    time.sleep(sleep_for)

            if response is None and last_exc is not None:
                raise last_exc

            content = response
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
                print(f"[LLM DEBUG] API failure #{self.api_failures}: {exc}", file=sys.stderr)
            return self._fallback(observation, history)