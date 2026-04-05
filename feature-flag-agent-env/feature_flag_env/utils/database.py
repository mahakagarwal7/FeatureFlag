"""
feature_flag_env/utils/database.py

Optional SQLite persistence layer.

Design goals:
- Fully opt-in via ENABLE_DATABASE=false by default
- Zero impact on rollout/reward logic when disabled
- Best-effort writes (never break API/training pipeline)
"""

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any, Dict

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    enabled: bool = os.getenv("ENABLE_DATABASE", "false").lower() == "true"
    path: str = os.getenv("DATABASE_PATH", "logs/app.db")
    timeout_seconds: float = float(os.getenv("DATABASE_TIMEOUT_SECONDS", "5.0"))


class SQLiteStore:
    """Small SQLite helper with best-effort persistence semantics."""

    def __init__(self):
        self.config = DatabaseConfig()
        self._lock = Lock()
        self._last_error: str | None = None

        if self.config.enabled:
            self.initialize()

    @contextmanager
    def _connect(self):
        db_path = self.config.path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        conn = sqlite3.connect(db_path, timeout=self.config.timeout_seconds)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def initialize(self) -> None:
        if not self.config.enabled:
            return

        try:
            with self._lock:
                with self._connect() as conn:
                    cur = conn.cursor()
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS episode_events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            ts TEXT NOT NULL,
                            event_type TEXT NOT NULL,
                            episode_id TEXT,
                            scenario_name TEXT,
                            difficulty TEXT,
                            step_count INTEGER,
                            action_type TEXT,
                            target_percentage REAL,
                            reward REAL,
                            error_rate REAL,
                            latency_p99_ms REAL,
                            system_health_score REAL,
                            done INTEGER,
                            feature_name TEXT,
                            reason TEXT,
                            metadata_json TEXT
                        )
                        """
                    )
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS audit_events (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            ts TEXT NOT NULL,
                            user TEXT,
                            action TEXT,
                            endpoint TEXT,
                            method TEXT,
                            status_code INTEGER,
                            details_json TEXT
                        )
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_episode_events_episode
                        ON episode_events (episode_id)
                        """
                    )
                    cur.execute(
                        """
                        CREATE INDEX IF NOT EXISTS idx_audit_events_ts
                        ON audit_events (ts)
                        """
                    )
        except Exception as exc:
            self._last_error = str(exc)
            logger.error("SQLite initialization failed: %s", exc)

    def is_enabled(self) -> bool:
        return self.config.enabled

    def get_health(self) -> Dict[str, Any]:
        if not self.config.enabled:
            return {
                "enabled": False,
                "path": self.config.path,
                "connected": False,
                "last_error": None,
            }

        connected = False
        error = self._last_error
        try:
            with self._connect() as conn:
                conn.execute("SELECT 1")
            connected = True
        except Exception as exc:
            error = str(exc)
            self._last_error = error

        return {
            "enabled": True,
            "path": self.config.path,
            "connected": connected,
            "last_error": error,
        }

    def get_stats(self) -> Dict[str, Any]:
        if not self.config.enabled:
            return {
                "enabled": False,
                "episode_events": 0,
                "audit_events": 0,
            }

        try:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM episode_events")
                episode_count = int(cur.fetchone()[0])
                cur.execute("SELECT COUNT(*) FROM audit_events")
                audit_count = int(cur.fetchone()[0])
                return {
                    "enabled": True,
                    "episode_events": episode_count,
                    "audit_events": audit_count,
                    "path": self.config.path,
                }
        except Exception as exc:
            self._last_error = str(exc)
            return {
                "enabled": True,
                "episode_events": 0,
                "audit_events": 0,
                "path": self.config.path,
                "error": str(exc),
            }

    def record_episode_reset(
        self,
        episode_id: str,
        scenario_name: str,
        difficulty: str,
        feature_name: str,
        current_rollout_percentage: float,
        error_rate: float,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        if not self.config.enabled:
            return

        try:
            payload = json.dumps(metadata or {}, default=str)
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO episode_events (
                            ts, event_type, episode_id, scenario_name, difficulty,
                            step_count, feature_name, target_percentage, error_rate,
                            metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            datetime.utcnow().isoformat(),
                            "reset",
                            episode_id,
                            scenario_name,
                            difficulty,
                            0,
                            feature_name,
                            float(current_rollout_percentage),
                            float(error_rate),
                            payload,
                        ),
                    )
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("SQLite episode reset write failed: %s", exc)

    def record_step(
        self,
        episode_id: str,
        step_count: int,
        action_type: str,
        target_percentage: float,
        reward: float,
        error_rate: float,
        latency_p99_ms: float,
        system_health_score: float,
        done: bool,
        reason: str = "",
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        if not self.config.enabled:
            return

        try:
            payload = json.dumps(metadata or {}, default=str)
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO episode_events (
                            ts, event_type, episode_id, step_count, action_type,
                            target_percentage, reward, error_rate, latency_p99_ms,
                            system_health_score, done, reason, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            datetime.utcnow().isoformat(),
                            "step",
                            episode_id,
                            int(step_count),
                            action_type,
                            float(target_percentage),
                            float(reward),
                            float(error_rate),
                            float(latency_p99_ms),
                            float(system_health_score),
                            1 if done else 0,
                            reason,
                            payload,
                        ),
                    )
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("SQLite step write failed: %s", exc)

    def record_audit_event(
        self,
        ts: str,
        user: str,
        action: str,
        endpoint: str,
        method: str,
        status_code: int,
        details: Dict[str, Any] | None = None,
    ) -> None:
        if not self.config.enabled:
            return

        try:
            payload = json.dumps(details or {}, default=str)
            with self._lock:
                with self._connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO audit_events (
                            ts, user, action, endpoint, method, status_code, details_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ts,
                            user,
                            action,
                            endpoint,
                            method,
                            int(status_code),
                            payload,
                        ),
                    )
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("SQLite audit write failed: %s", exc)


database = SQLiteStore()
