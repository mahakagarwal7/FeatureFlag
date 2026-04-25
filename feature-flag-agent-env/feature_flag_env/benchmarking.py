"""
feature_flag_env/benchmarking.py

Competitive benchmarking system for comparing deployment performance against industry standards.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class IndustryBenchmark:
    industry: str
    company_size: str  # startup, mid-market, enterprise
    error_rate_p50: float
    error_rate_p90: float
    latency_p99_p50: float  # median of p99s
    latency_p99_p90: float  # 90th percentile of p99s
    rollout_speed_score: float  # 0-1 (1 = very fast)


# Realistic industry data (approximations)
BENCHMARK_DATA = [
    IndustryBenchmark("fintech",    "enterprise", 0.001, 0.005, 100.0, 180.0, 0.3),
    IndustryBenchmark("fintech",    "startup",    0.005, 0.02,  150.0, 250.0, 0.7),
    IndustryBenchmark("ecommerce",  "enterprise", 0.01,  0.03,  120.0, 200.0, 0.5),
    IndustryBenchmark("ecommerce",  "startup",    0.02,  0.05,  200.0, 400.0, 0.8),
    IndustryBenchmark("saas",       "enterprise", 0.005, 0.02,  150.0, 300.0, 0.6),
    IndustryBenchmark("saas",       "startup",    0.015, 0.06,  250.0, 500.0, 0.9),
]


class BenchmarkEngine:
    """
    Analyzes current deployment performance against industry peers.
    Supports filtering by industry and company size.
    """

    def __init__(self, industry: str = "saas", company_size: str = "mid-market"):
        self.industry = industry.lower()
        self.company_size = company_size.lower()
        self.active_benchmark = self._find_benchmark()

    def _find_benchmark(self) -> IndustryBenchmark:
        """Find the closest matching benchmark, with fallback."""
        for b in BENCHMARK_DATA:
            if b.industry == self.industry and b.company_size == self.company_size:
                return b
        # Fallback: match industry only
        for b in BENCHMARK_DATA:
            if b.industry == self.industry:
                return b
        # Ultimate fallback
        return BENCHMARK_DATA[2]  # ecommerce enterprise

    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare current metrics against the active benchmark.
        Returns percentile, comparison string, and recommendations.
        """
        b = self.active_benchmark
        err = float(metrics.get("error_rate", 0.0))
        lat = float(metrics.get("latency_p99_ms", 0.0))

        # --- Error Percentile (lower is better) ---
        if b.error_rate_p90 == b.error_rate_p50:
            err_percentile = 0.5
        elif err <= b.error_rate_p50:
            err_percentile = 0.9 + (1.0 - err / max(b.error_rate_p50, 1e-9)) * 0.1
        elif err <= b.error_rate_p90:
            span = b.error_rate_p90 - b.error_rate_p50
            err_percentile = 0.5 + (1.0 - (err - b.error_rate_p50) / span) * 0.4
        else:
            err_percentile = max(0.05, 0.5 - (err / max(b.error_rate_p90, 1e-9)) * 0.4)

        # --- Latency Percentile (lower is better) ---
        if b.latency_p99_p90 == b.latency_p99_p50:
            lat_percentile = 0.5
        elif lat <= b.latency_p99_p50:
            lat_percentile = 0.9 + (1.0 - lat / max(b.latency_p99_p50, 1e-9)) * 0.1
        elif lat <= b.latency_p99_p90:
            span = b.latency_p99_p90 - b.latency_p99_p50
            lat_percentile = 0.5 + (1.0 - (lat - b.latency_p99_p50) / span) * 0.4
        else:
            lat_percentile = max(0.05, 0.5 - (lat / max(b.latency_p99_p90, 1e-9)) * 0.4)

        overall_percentile = round((err_percentile + lat_percentile) / 2.0, 3)

        comparison = (
            f"Your deployment is performing better than {overall_percentile:.1%} "
            f"of {self.company_size} {self.industry} peers."
        )

        recommendations: List[str] = []
        if err_percentile < 0.7:
            recommendations.append(
                "Error rate is above industry average. Check downstream service health."
            )
        if lat_percentile < 0.7:
            recommendations.append(
                "P99 latency is lagging. Consider optimizing payload sizes or using edge caching."
            )
        if not recommendations:
            recommendations.append("Performance is elite. Continue with planned rollout.")

        return {
            "percentile": overall_percentile,
            "comparison": comparison,
            "recommendations": recommendations,
            "benchmark_used": f"{self.industry} ({self.company_size})",
        }
