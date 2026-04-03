"""
feature_flag_env/utils/monitoring.py

Real-Time Monitoring & Alerting System

Provides:
- Performance metrics collection (Prometheus-compatible)
- Health status tracking
- SLA compliance monitoring
- Alert thresholds
- Real-time visibility into system health

All features are optional and can be disabled
"""

import time
import os
from datetime import datetime
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


# =========================
# MONITORING CONFIGURATION
# =========================
class MonitoringConfig:
    """Monitoring configuration loaded from environment variables"""
    
    def __init__(self):
        # Feature flags
        self.enabled = os.getenv("ENABLE_MONITORING", "true").lower() == "true"
        self.enable_alerting = os.getenv("ENABLE_ALERTING", "true").lower() == "true"
        self.enable_prometheus = os.getenv("ENABLE_PROMETHEUS", "true").lower() == "true"
        
        # Alert thresholds
        self.error_rate_threshold = float(os.getenv("ALERT_ERROR_RATE_THRESHOLD", "0.05"))  # 5%
        self.latency_threshold_ms = float(os.getenv("ALERT_LATENCY_THRESHOLD_MS", "1000"))  # 1 second
        self.health_score_threshold = float(os.getenv("ALERT_HEALTH_SCORE_THRESHOLD", "0.7"))  # 70%
        
        # Collection intervals
        self.metrics_collection_interval = int(os.getenv("METRICS_COLLECTION_INTERVAL", "60"))  # seconds
        self.alert_check_interval = int(os.getenv("ALERT_CHECK_INTERVAL", "30"))  # seconds


config = MonitoringConfig()


# =========================
# METRICS DATA CLASSES
# =========================
@dataclass
class Metric:
    """Single metric data point"""
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class HealthStatus:
    """System health status"""
    timestamp: float = field(default_factory=time.time)
    system_health_score: float = 1.0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    uptime_seconds: float = 0.0
    episode_count: int = 0
    step_count: int = 0
    active_users: int = 0


@dataclass
class Alert:
    """Alert notification"""
    alert_id: str
    timestamp: float = field(default_factory=time.time)
    severity: str = "warning"  # info, warning, critical
    title: str = ""
    message: str = ""
    metric_name: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    user: str = "system"
    resolved: bool = False


# =========================
# METRICS COLLECTOR
# =========================
class MetricsCollector:
    """Collects and aggregates system metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, List[Metric]] = defaultdict(list)
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = defaultdict(float)
        self.start_time = time.time()
        self._max_metrics_per_name = 10000  # Prevent unbounded growth
    
    def record_metric(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a metric value"""
        if not config.enabled:
            return
        
        metric = Metric(name=name, value=value, labels=labels or {})
        self.metrics[name].append(metric)
        
        # Trim old metrics if too many
        if len(self.metrics[name]) > self._max_metrics_per_name:
            self.metrics[name] = self.metrics[name][-self._max_metrics_per_name:]
    
    def increment_counter(self, name: str, amount: int = 1, labels: Optional[Dict[str, str]] = None):
        """Increment a counter"""
        if not config.enabled:
            return
        
        counter_key = f"{name}_{str(labels)}" if labels else name
        self.counters[counter_key] += amount
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge value"""
        if not config.enabled:
            return
        
        gauge_key = f"{name}_{str(labels)}" if labels else name
        self.gauges[gauge_key] = value
    
    def get_metric_stats(self, name: str, time_window_seconds: int = 60) -> Dict:
        """Get statistics for a metric over a time window"""
        if name not in self.metrics or len(self.metrics[name]) == 0:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "avg": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0
            }
        
        cutoff_time = time.time() - time_window_seconds
        values = [m.value for m in self.metrics[name] if m.timestamp > cutoff_time]
        
        if not values:
            return {
                "count": 0,
                "min": 0,
                "max": 0,
                "avg": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0
            }
        
        values_sorted = sorted(values)
        count = len(values_sorted)
        
        return {
            "count": count,
            "min": min(values_sorted),
            "max": max(values_sorted),
            "avg": sum(values_sorted) / count,
            "p50": values_sorted[int(count * 0.50)],
            "p95": values_sorted[int(count * 0.95)],
            "p99": values_sorted[int(count * 0.99)]
        }
    
    def get_health_status(self) -> HealthStatus:
        """Get current system health status"""
        uptime = time.time() - self.start_time
        
        # Calculate error rate from last 100 episodes
        error_count = self.counters.get("errors", 0)
        step_count = self.counters.get("steps", 0)
        error_rate = error_count / step_count if step_count > 0 else 0.0
        error_rate = min(error_rate, 1.0)  # Cap at 100%
        
        # Get average latency
        latency_stats = self.get_metric_stats("step_latency_ms", time_window_seconds=300)
        avg_latency = latency_stats.get("avg", 0.0)
        
        # Calculate health score (0-1)
        health_score = 1.0
        health_score -= min(error_rate, 1.0) * 0.5  # Error rate affects 50%
        health_score -= min(avg_latency / config.latency_threshold_ms, 1.0) * 0.3  # Latency affects 30%
        health_score -= (1.0 - (1.0 if step_count > 100 else step_count / 100)) * 0.2  # Activity affects 20%
        health_score = max(0.0, min(health_score, 1.0))  # Clamp to 0-1
        
        return HealthStatus(
            system_health_score=health_score,
            error_rate=error_rate,
            avg_latency_ms=avg_latency,
            uptime_seconds=uptime,
            episode_count=self.counters.get("episodes", 0),
            step_count=step_count,
            active_users=len(set([
                m.labels.get("user", "unknown")
                for metrics in self.metrics.values()
                for m in metrics[-100:] if m.labels
            ]))
        )


# Global collector instance
metrics = MetricsCollector()


# =========================
# ALERT MANAGER
# =========================
class AlertManager:
    """Manages alerts based on metric thresholds"""
    
    def __init__(self):
        self.alerts: List[Alert] = []
        self.alert_history: List[Alert] = []
        self._max_alerts = 1000
        self._alert_cooldown: Dict[str, float] = defaultdict(lambda: 0)
        self._alert_cooldown_seconds = 300  # Don't alert same issue more than once per 5 min
    
    def check_alerts(self, health: HealthStatus, metrics_obj: MetricsCollector) -> List[Alert]:
        """Check thresholds and generate alerts"""
        if not config.enable_alerting:
            return []
        
        new_alerts = []
        now = time.time()
        
        # Check error rate
        if health.error_rate > config.error_rate_threshold:
            alert = self._create_alert_if_needed(
                name="high_error_rate",
                severity="critical" if health.error_rate > 0.1 else "warning",
                title="High Error Rate Detected",
                message=f"Error rate is {health.error_rate:.1%}, threshold is {config.error_rate_threshold:.1%}",
                metric_name="error_rate",
                metric_value=health.error_rate,
                threshold=config.error_rate_threshold
            )
            if alert:
                new_alerts.append(alert)
        
        # Check latency
        if health.avg_latency_ms > config.latency_threshold_ms:
            alert = self._create_alert_if_needed(
                name="high_latency",
                severity="warning",
                title="High Latency Detected",
                message=f"Average latency is {health.avg_latency_ms:.0f}ms, threshold is {config.latency_threshold_ms:.0f}ms",
                metric_name="avg_latency_ms",
                metric_value=health.avg_latency_ms,
                threshold=config.latency_threshold_ms
            )
            if alert:
                new_alerts.append(alert)
        
        # Check health score
        if health.system_health_score < config.health_score_threshold:
            alert = self._create_alert_if_needed(
                name="low_health_score",
                severity="warning",
                title="System Health Degraded",
                message=f"Health score is {health.system_health_score:.1%}, threshold is {config.health_score_threshold:.1%}",
                metric_name="health_score",
                metric_value=health.system_health_score,
                threshold=config.health_score_threshold
            )
            if alert:
                new_alerts.append(alert)
        
        # Add alerts
        self.alerts.extend(new_alerts)
        self.alert_history.extend(new_alerts)
        
        # Trim if too many
        if len(self.alerts) > self._max_alerts:
            self.alerts = self.alerts[-self._max_alerts:]
        
        return new_alerts
    
    def _create_alert_if_needed(
        self,
        name: str,
        severity: str,
        title: str,
        message: str,
        metric_name: str,
        metric_value: float,
        threshold: float
    ) -> Optional[Alert]:
        """Create alert only if cooldown elapsed"""
        now = time.time()
        
        if now - self._alert_cooldown[name] < self._alert_cooldown_seconds:
            return None  # Still in cooldown
        
        alert = Alert(
            alert_id=f"{name}_{int(now)}",
            severity=severity,
            title=title,
            message=message,
            metric_name=metric_name,
            metric_value=metric_value,
            threshold=threshold
        )
        
        self._alert_cooldown[name] = now
        return alert
    
    def get_active_alerts(self) -> List[Alert]:
        """Get unresolved alerts"""
        return [a for a in self.alerts if not a.resolved]
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Get recent alert history"""
        return self.alert_history[-limit:]


# Global alert manager instance
alert_manager = AlertManager()


# =========================
# PROMETHEUS EXPORTER
# =========================
def get_prometheus_metrics() -> str:
    """
    Export metrics in Prometheus format
    
    Returns:
        String in Prometheus text format
    """
    if not config.enable_prometheus:
        return ""
    
    lines = []
    health = metrics.get_health_status()
    
    # HELP and TYPE metadata
    lines.append("# HELP ff_health_score System health score (0-1)")
    lines.append("# TYPE ff_health_score gauge")
    lines.append(f"ff_health_score {health.system_health_score}")
    
    lines.append("# HELP ff_error_rate Current error rate")
    lines.append("# TYPE ff_error_rate gauge")
    lines.append(f"ff_error_rate {health.error_rate}")
    
    lines.append("# HELP ff_latency_ms Average latency in milliseconds")
    lines.append("# TYPE ff_latency_ms gauge")
    lines.append(f"ff_latency_ms {health.avg_latency_ms}")
    
    lines.append("# HELP ff_uptime_seconds System uptime in seconds")
    lines.append("# TYPE ff_uptime_seconds gauge")
    lines.append(f"ff_uptime_seconds {health.uptime_seconds}")
    
    lines.append("# HELP ff_episodes_total Total episodes completed")
    lines.append("# TYPE ff_episodes_total counter")
    lines.append(f"ff_episodes_total {health.episode_count}")
    
    lines.append("# HELP ff_steps_total Total steps completed")
    lines.append("# TYPE ff_steps_total counter")
    lines.append(f"ff_steps_total {health.step_count}")
    
    lines.append("# HELP ff_active_users Current active users")
    lines.append("# TYPE ff_active_users gauge")
    lines.append(f"ff_active_users {health.active_users}")
    
    lines.append("# HELP ff_alerts_active Currently active alerts")
    lines.append("# TYPE ff_alerts_active gauge")
    lines.append(f"ff_alerts_active {len(alert_manager.get_active_alerts())}")
    
    return "\n".join(lines) + "\n"


# =========================
# DASHBOARD DATA
# =========================
def get_dashboard_data() -> Dict:
    """Get all data for monitoring dashboard"""
    health = metrics.get_health_status()
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "health": {
            "score": health.system_health_score,
            "status": "healthy" if health.system_health_score > 0.8 else "degraded" if health.system_health_score > 0.5 else "critical"
        },
        "metrics": {
            "error_rate": health.error_rate,
            "avg_latency_ms": health.avg_latency_ms,
            "uptime_seconds": health.uptime_seconds,
            "episodes": health.episode_count,
            "steps": health.step_count,
            "active_users": health.active_users
        },
        "alerts": {
            "active_count": len(alert_manager.get_active_alerts()),
            "recent": [
                {
                    "id": a.alert_id,
                    "severity": a.severity,
                    "title": a.title,
                    "timestamp": a.timestamp,
                    "resolved": a.resolved
                }
                for a in alert_manager.get_alert_history(limit=10)
            ]
        },
        "thresholds": {
            "error_rate": config.error_rate_threshold,
            "latency_ms": config.latency_threshold_ms,
            "health_score": config.health_score_threshold
        }
    }


# =========================
# MONITORING UTILITIES
# =========================
def record_episode(episode_id: str, reward: float, steps: int, errors: int, user: str = "anonymous"):
    """Record episode completion"""
    metrics.record_metric("episode_reward", reward, labels={"episode": episode_id, "user": user})
    metrics.record_metric("episode_steps", steps, labels={"episode": episode_id})
    metrics.increment_counter("episodes")
    metrics.increment_counter("steps", steps)
    if errors > 0:
        metrics.increment_counter("errors", errors)


def record_step(step_duration_ms: float, action: str, error: bool = False, user: str = "anonymous"):
    """Record step execution"""
    metrics.record_metric("step_latency_ms", step_duration_ms, labels={"action": action, "user": user})
    if error:
        metrics.increment_counter("errors")


def record_api_call(endpoint: str, method: str, status_code: int, duration_ms: float, user: str = "anonymous"):
    """Record API call"""
    metrics.record_metric(
        "api_latency_ms",
        duration_ms,
        labels={"endpoint": endpoint, "method": method, "status": str(status_code), "user": user}
    )
    if status_code >= 400:
        metrics.increment_counter("errors")


def get_status_summary() -> str:
    """Get human-readable status summary"""
    health = metrics.get_health_status()
    alerts = alert_manager.get_active_alerts()
    
    lines = [
        "╔════════════════════════════════════════════╗",
        "║     SYSTEM MONITORING STATUS REPORT        ║",
        "╠════════════════════════════════════════════╣",
        f"║ Health Score:     {health.system_health_score:>6.1%}                  ║",
        f"║ Error Rate:       {health.error_rate:>6.1%}                  ║",
        f"║ Avg Latency:      {health.avg_latency_ms:>6.0f}ms                ║",
        f"║ Uptime:           {int(health.uptime_seconds):>6}s                 ║",
        f"║ Episodes:         {health.episode_count:>6}                  ║",
        f"║ Steps:            {health.step_count:>6}                  ║",
        f"║ Active Alerts:    {len(alerts):>6}                  ║",
        "╚════════════════════════════════════════════╝",
    ]
    
    if alerts:
        lines.append("\n⚠️  Active Alerts:")
        for alert in alerts[:5]:
            lines.append(f"  • [{alert.severity.upper()}] {alert.title}")
        if len(alerts) > 5:
            lines.append(f"  ... and {len(alerts) - 5} more")
    
    return "\n".join(lines)
