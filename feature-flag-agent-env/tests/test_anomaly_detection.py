import pytest
from feature_flag_env.anomaly_detection import AnomalyDetector

def test_anomaly_detector_baseline_maintenance():
    detector = AnomalyDetector(window_size=5)
    
    # Fill baseline
    for _ in range(5):
        detector.update_baselines({"error_rate": 0.01})
    
    assert len(detector.metrics_history["error_rate"]) == 5
    assert sum(detector.metrics_history["error_rate"]) / 5 == 0.01

def test_anomaly_detection_logic():
    detector = AnomalyDetector(window_size=10, threshold=2.0)
    
    # Establish stable baseline (0.01 error rate)
    for _ in range(10):
        detector.update_baselines({"error_rate": 0.01})
    
    # Normal reading (no anomaly)
    res = detector.detect({"error_rate": 0.012})
    assert res["anomaly_score"] == 0.0
    assert not res["anomalies"]
    
    # Anomaly (spike to 0.10)
    res = detector.detect({"error_rate": 0.10})
    assert res["anomaly_score"] > 0.0
    assert "error_rate" in res["anomalies"]
    assert res["is_significant"] is True

def test_multi_metric_anomaly():
    detector = AnomalyDetector(window_size=10)
    for _ in range(10):
        detector.update_baselines({
            "error_rate": 0.01,
            "latency_p99_ms": 50.0
        })
        
    # Spike both
    res = detector.detect({
        "error_rate": 0.50,
        "latency_p99_ms": 500.0
    })
    
    assert "error_rate" in res["anomalies"]
    assert "latency_p99_ms" in res["anomalies"]
    assert res["anomaly_score"] > 0.8

def test_reset():
    detector = AnomalyDetector(window_size=5)
    detector.update_baselines({"error_rate": 0.01})
    detector.reset()
    assert len(detector.metrics_history["error_rate"]) == 0
