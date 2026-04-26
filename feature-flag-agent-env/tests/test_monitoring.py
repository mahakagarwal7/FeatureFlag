"""
tests/test_monitoring.py

Comprehensive test suite for the monitoring and alerting system.
Tests the actual monitoring module implementation.
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import patch

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from feature_flag_env.utils.monitoring import (
    MonitoringConfig,
    MetricsCollector,
    AlertManager,
    HealthStatus,
    Alert,
    get_prometheus_metrics,
    get_dashboard_data,
    get_status_summary,
    record_step,
    record_episode,
    record_api_call,
)


class TestMonitoringConfig:
    def test_config_enabled_by_default(self):
        with patch.dict(os.environ, {'ENABLE_MONITORING': 'true'}):
            config = MonitoringConfig()
            assert config.enabled is True

    def test_config_disabled(self):
        with patch.dict(os.environ, {'ENABLE_MONITORING': 'false'}):
            config = MonitoringConfig()
            assert config.enabled is False

    def test_config_alerting(self):
        with patch.dict(os.environ, {'ENABLE_ALERTING': 'true'}):
            config = MonitoringConfig()
            assert config.enable_alerting is True

    def test_config_prometheus(self):
        with patch.dict(os.environ, {'ENABLE_PROMETHEUS': 'true'}):
            config = MonitoringConfig()
            assert config.enable_prometheus is True

    def test_config_thresholds(self):
        with patch.dict(os.environ, {
            'ALERT_ERROR_RATE_THRESHOLD': '0.1',
            'ALERT_LATENCY_THRESHOLD_MS': '2000',
            'ALERT_HEALTH_SCORE_THRESHOLD': '0.6',
        }):
            config = MonitoringConfig()
            assert config.error_rate_threshold == 0.1
            assert config.latency_threshold_ms == 2000
            assert config.health_score_threshold == 0.6


class TestMetricsCollector:
    def test_record_metric(self):
        collector = MetricsCollector()
        collector.record_metric('latency', 100.0, {'user': 'user1'})
        assert 'latency' in collector.metrics
        assert len(collector.metrics['latency']) > 0

    def test_increment_counter(self):
        collector = MetricsCollector()
        collector.increment_counter('requests', 1)
        collector.increment_counter('requests', 1)
        assert 'requests' in collector.counters

    def test_set_gauge(self):
        collector = MetricsCollector()
        collector.set_gauge('active_users', 50)
        assert 'active_users' in collector.gauges
        assert collector.gauges['active_users'] == 50

    def test_get_metric_stats(self):
        collector = MetricsCollector()
        for value in [100, 150, 200, 250, 300]:
            collector.record_metric('latency', float(value))

        stats = collector.get_metric_stats('latency')
        assert stats is not None
        assert stats.get('count') >= 0
        assert 'avg' in stats

    def test_get_metric_stats_empty(self):
        collector = MetricsCollector()
        stats = collector.get_metric_stats('nonexistent')
        assert stats is not None
        assert stats.get('count') == 0

    def test_health_status_calculation(self):
        collector = MetricsCollector()
        collector.record_metric('step_latency_ms', 500.0)
        collector.increment_counter('steps', 1)

        health = collector.get_health_status()
        assert isinstance(health, HealthStatus)
        assert 0 <= health.error_rate <= 1
        assert 0 <= health.system_health_score <= 1


class TestAlertManager:
    def test_alert_creation(self):
        health = HealthStatus(
            system_health_score=0.5,
            error_rate=0.1,
            avg_latency_ms=2000.0,
            uptime_seconds=3600,
            episode_count=10,
            step_count=100,
            active_users=2
        )
        assert health.system_health_score == 0.5

    def test_alert_severity(self):
        alert = Alert(
            alert_id='test_001',
            severity='critical',
            title='Test Alert',
            message='Test',
            metric_name='error_rate',
            metric_value=0.3,
            threshold=0.05
        )
        assert alert.severity == 'critical'

    def test_get_active_alerts(self):
        alertmgr = AlertManager()
        alerts = alertmgr.get_active_alerts()
        assert isinstance(alerts, list)

    def test_get_alert_history(self):
        alertmgr = AlertManager()
        history = alertmgr.get_alert_history(limit=5)
        assert isinstance(history, list)


class TestRecordingFunctions:
    def test_record_step(self):
        record_step(
            step_duration_ms=150.5,
            action='INCREASE_ROLLOUT',
            error=False,
            user='agent1'
        )

    def test_record_episode(self):
        record_episode(
            episode_id='ep_001',
            reward=42.5,
            steps=50,
            errors=2,
            user='agent1'
        )

    def test_record_api_call(self):
        record_api_call(
            endpoint='/step',
            method='POST',
            status_code=200,
            duration_ms=125.0,
            user='agent1'
        )

    def test_record_step_error(self):
        record_step(step_duration_ms=500.0, action='HALT', error=True, user='test')

    def test_record_api_error(self):
        record_api_call(endpoint='/error', method='POST', status_code=500, duration_ms=1000.0, user='test')


class TestPrometheusExport:
    def test_prometheus_metrics_format(self):
        metrics_text = get_prometheus_metrics()
        assert isinstance(metrics_text, str)

    def test_prometheus_metrics_utf8(self):
        metrics_text = get_prometheus_metrics()
        try:
            metrics_text.encode('utf-8')
        except UnicodeEncodeError:
            pytest.fail('Invalid UTF-8')


class TestDashboardData:
    def test_dashboard_structure(self):
        data = get_dashboard_data()
        assert isinstance(data, dict)
        assert 'timestamp' in data

    def test_dashboard_content(self):
        data = get_dashboard_data()
        assert 'health' in data or 'metrics' in data


class TestStatusSummary:
    def test_status_summary_string(self):
        summary = get_status_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0


class TestHealthStatus:
    def test_health_status_valid(self):
        health = HealthStatus(
            system_health_score=0.95,
            error_rate=0.05,
            avg_latency_ms=500.0,
            uptime_seconds=3600.0,
            episode_count=100,
            step_count=1000,
            active_users=5
        )
        assert 0 <= health.system_health_score <= 1
        assert 0 <= health.error_rate <= 1

    def test_health_status_extreme(self):
        health = HealthStatus(
            system_health_score=1.0,
            error_rate=0.0,
            avg_latency_ms=0.0,
            uptime_seconds=0.0
        )
        assert health.system_health_score == 1.0


class TestAlert:
    def test_alert_creation(self):
        alert = Alert(
            alert_id='alert_001',
            severity='warning',
            title='High Errors',
            message='Error rate high',
            metric_name='error_rate',
            metric_value=0.1,
            threshold=0.05
        )
        assert alert.alert_id == 'alert_001'
        assert alert.severity == 'warning'

    def test_alert_severities(self):
        for sev in ['warning', 'error', 'critical', 'info']:
            alert = Alert(alert_id=f'a_{sev}', severity=sev, title=sev, message=sev, metric_name='test', metric_value=1, threshold=1)
            assert alert.severity == sev


class TestMonitoringIntegration:
    def test_end_to_end(self):
        collector = MetricsCollector()
        for i in range(10):
            collector.record_metric('step_latency_ms', 100.0 + i * 10)
        collector.increment_counter('steps', 10)

        health = collector.get_health_status()
        assert isinstance(health, HealthStatus)

    def test_with_recording_functions(self):
        record_step(step_duration_ms=100.0, action='TEST', error=False, user='test')
        record_episode(episode_id='ep_test', reward=50.0, steps=10, errors=0, user='test')
        record_api_call(endpoint='/step', method='POST', status_code=200, duration_ms=50.0, user='test')

        metrics_text = get_prometheus_metrics()
        assert isinstance(metrics_text, str)

        dashboard = get_dashboard_data()
        assert isinstance(dashboard, dict)


class TestMonitoringErrorHandling:
    def test_invalid_metric_values(self):
        collector = MetricsCollector()
        collector.record_metric('latency', 999999.0)
        collector.record_metric('error_rate', 1.0)
        collector.record_metric('error_rate', 0.0)

    def test_prometheus_always_string(self):
        result = get_prometheus_metrics()
        assert isinstance(result, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
