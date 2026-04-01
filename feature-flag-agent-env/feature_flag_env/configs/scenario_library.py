"""
feature_flag_env/configs/scenario_library.py

Library of simulation scenarios for episode generation.
Each scenario defines different system characteristics.
"""

from typing import Dict, Any, List

SCENARIO_LIBRARY: Dict[str, Dict[str, Any]] = {
    # ========== EASY SCENARIOS ==========
    "stable_feature": {
        "name": "stable_feature",
        "difficulty": "easy",
        "base_error_rate": 0.01,
        "error_variance": 0.002,
        "latency_per_10pct_rollout": 3.0,
        "adoption_speed": 0.15,
        "revenue_per_user": 0.10,
        "total_users": 10000,
        "incident_zones": [],
        "description": "Stable feature with low risk and predictable behavior",
    },
    
    "simple_ui_change": {
        "name": "simple_ui_change",
        "difficulty": "easy",
        "base_error_rate": 0.005,
        "error_variance": 0.001,
        "latency_per_10pct_rollout": 2.0,
        "adoption_speed": 0.20,
        "revenue_per_user": 0.05,
        "total_users": 10000,
        "incident_zones": [],
        "description": "Simple UI change with minimal backend impact",
    },
    
    # ========== MEDIUM SCENARIOS ==========
    "moderate_risk_feature": {
        "name": "moderate_risk_feature",
        "difficulty": "medium",
        "base_error_rate": 0.03,
        "error_variance": 0.01,
        "latency_per_10pct_rollout": 8.0,
        "adoption_speed": 0.10,
        "revenue_per_user": 0.20,
        "total_users": 10000,
        "incident_zones": [
            {"min": 40, "max": 50, "probability": 0.25, "spike": 0.12}
        ],
        "description": "Moderate risk with one incident zone at 40-50% rollout",
    },
    
    "api_integration": {
        "name": "api_integration",
        "difficulty": "medium",
        "base_error_rate": 0.025,
        "error_variance": 0.008,
        "latency_per_10pct_rollout": 10.0,
        "adoption_speed": 0.12,
        "revenue_per_user": 0.25,
        "total_users": 10000,
        "incident_zones": [
            {"min": 30, "max": 40, "probability": 0.20, "spike": 0.10}
        ],
        "description": "API integration with moderate latency impact",
    },
    
    # ========== HARD SCENARIOS ==========
    "high_risk_feature": {
        "name": "high_risk_feature",
        "difficulty": "hard",
        "base_error_rate": 0.05,
        "error_variance": 0.02,
        "latency_per_10pct_rollout": 15.0,
        "adoption_speed": 0.08,
        "revenue_per_user": 0.30,
        "total_users": 10000,
        "incident_zones": [
            {"min": 25, "max": 35, "probability": 0.30, "spike": 0.15},
            {"min": 55, "max": 65, "probability": 0.25, "spike": 0.12},
        ],
        "description": "High-risk feature with multiple incident zones",
    },
    
    "database_migration": {
        "name": "database_migration",
        "difficulty": "hard",
        "base_error_rate": 0.04,
        "error_variance": 0.015,
        "latency_per_10pct_rollout": 20.0,
        "adoption_speed": 0.05,
        "revenue_per_user": 0.15,
        "total_users": 10000,
        "incident_zones": [
            {"min": 20, "max": 30, "probability": 0.35, "spike": 0.18},
            {"min": 50, "max": 60, "probability": 0.30, "spike": 0.15},
            {"min": 80, "max": 90, "probability": 0.20, "spike": 0.10},
        ],
        "description": "Database migration with high latency and multiple risk zones",
    },
    
    "ml_model_deployment": {
        "name": "ml_model_deployment",
        "difficulty": "hard",
        "base_error_rate": 0.035,
        "error_variance": 0.012,
        "latency_per_10pct_rollout": 12.0,
        "adoption_speed": 0.10,
        "revenue_per_user": 0.40,
        "total_users": 10000,
        "incident_zones": [
            {"min": 40, "max": 50, "probability": 0.25, "spike": 0.12},
        ],
        "description": "ML model deployment with moderate risk and high revenue",
    },
}


def get_scenario(scenario_name: str) -> Dict[str, Any]:
    """Get a specific scenario by name"""
    if scenario_name not in SCENARIO_LIBRARY:
        raise ValueError(f"Unknown scenario: {scenario_name}")
    return SCENARIO_LIBRARY[scenario_name].copy()


def get_scenarios_by_difficulty(difficulty: str) -> List[Dict[str, Any]]:
    """Get all scenarios of a specific difficulty"""
    return [
        config.copy() for config in SCENARIO_LIBRARY.values()
        if config.get("difficulty") == difficulty
    ]


def get_random_scenario(difficulty: str = None) -> Dict[str, Any]:
    """Get a random scenario from the library"""
    import random
    if difficulty:
        scenarios = get_scenarios_by_difficulty(difficulty)
        if not scenarios:
            raise ValueError(f"No scenarios found for difficulty: {difficulty}")
        return random.choice(scenarios).copy()
    scenario_name = random.choice(list(SCENARIO_LIBRARY.keys()))
    return SCENARIO_LIBRARY[scenario_name].copy()