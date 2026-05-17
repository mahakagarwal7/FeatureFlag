"""
tests/test_benchmarking.py

Unit tests for the BenchmarkEngine.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from feature_flag_env.benchmarking import BenchmarkEngine


class TestBenchmarkEngine(unittest.TestCase):
    def test_benchmark_lookup_exact(self):
        engine = BenchmarkEngine(industry="fintech", company_size="enterprise")
        self.assertEqual(engine.active_benchmark.industry, "fintech")
        self.assertEqual(engine.active_benchmark.company_size, "enterprise")

    def test_benchmark_lookup_fallback(self):
        engine = BenchmarkEngine(industry="non_existent", company_size="tiny")
        # Should fallback to ecommerce enterprise
        self.assertEqual(engine.active_benchmark.industry, "ecommerce")

    def test_percentile_elite(self):
        engine = BenchmarkEngine(industry="saas", company_size="startup")
        result = engine.analyze({"error_rate": 0.0, "latency_p99_ms": 10.0})
        self.assertGreaterEqual(result["percentile"], 0.95)
        self.assertIn("elite", result["recommendations"][0].lower())

    def test_percentile_poor(self):
        engine = BenchmarkEngine(industry="fintech", company_size="enterprise")
        result = engine.analyze({"error_rate": 0.1, "latency_p99_ms": 500.0})
        self.assertLessEqual(result["percentile"], 0.2)
        self.assertTrue(len(result["recommendations"]) >= 2)

    def test_different_industries_give_different_results(self):
        fintech = BenchmarkEngine(industry="fintech", company_size="enterprise")
        saas = BenchmarkEngine(industry="saas", company_size="startup")
        metrics = {"error_rate": 0.01, "latency_p99_ms": 200.0}
        r1 = fintech.analyze(metrics)
        r2 = saas.analyze(metrics)
        self.assertNotEqual(r1["percentile"], r2["percentile"])

    def test_output_format(self):
        engine = BenchmarkEngine()
        result = engine.analyze({"error_rate": 0.02, "latency_p99_ms": 180.0})
        self.assertIn("percentile", result)
        self.assertIn("comparison", result)
        self.assertIn("recommendations", result)
        self.assertIn("benchmark_used", result)
        self.assertIsInstance(result["percentile"], float)
        self.assertIsInstance(result["recommendations"], list)


if __name__ == "__main__":
    unittest.main()
