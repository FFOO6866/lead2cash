"""
Automated evaluation system for A/B testing MCP Parameter Validation Tool.
Provides objective scoring of workflow submissions against challenge criteria.
"""

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add the parameter validator to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from suggestions import FixSuggestionEngine
from validator import ParameterValidator


class WorkflowEvaluator:
    """Automated evaluation system for workflow submissions."""

    def __init__(self):
        """Initialize with validation components."""
        self.validator = ParameterValidator()
        self.suggestion_engine = FixSuggestionEngine()

        # Error severity weights for scoring
        self.error_weights = {"error": 1.0, "warning": 0.5, "info": 0.1}

        # Success criteria weights
        self.criteria_weights = {
            "functional": 0.4,
            "code_quality": 0.4,
            "performance": 0.2,
        }

    def evaluate_submission(
        self,
        workflow_code: str,
        challenge: Dict[str, Any],
        execution_time: float = None,
    ) -> Dict[str, Any]:
        """
        Evaluate a workflow submission against challenge criteria.

        Args:
            workflow_code: The submitted workflow code
            challenge: Challenge specification
            execution_time: Time taken to develop the solution (seconds)

        Returns:
            Comprehensive evaluation results
        """
        evaluation_start = time.time()

        # Core evaluations
        validation_result = self._validate_code_quality(workflow_code)
        execution_result = self._test_execution_safety(workflow_code)
        error_detection = self._check_planted_errors(workflow_code, challenge)
        import_analysis = self._analyze_imports(workflow_code)
        pattern_analysis = self._analyze_patterns(workflow_code)
        complexity_analysis = self._analyze_complexity(workflow_code)

        # Calculate component scores
        functional_score = self._calculate_functional_score(
            execution_result, validation_result, challenge
        )
        code_quality_score = self._calculate_code_quality_score(
            validation_result, import_analysis, pattern_analysis
        )
        performance_score = self._calculate_performance_score(
            complexity_analysis, execution_time, challenge
        )

        # Overall weighted score
        overall_score = (
            functional_score * self.criteria_weights["functional"]
            + code_quality_score * self.criteria_weights["code_quality"]
            + performance_score * self.criteria_weights["performance"]
        )

        evaluation_time = time.time() - evaluation_start

        return {
            "challenge_id": challenge["challenge_id"],
            "overall_score": round(overall_score, 3),
            "component_scores": {
                "functional": round(functional_score, 3),
                "code_quality": round(code_quality_score, 3),
                "performance": round(performance_score, 3),
            },
            "detailed_analysis": {
                "validation_result": validation_result,
                "execution_result": execution_result,
                "error_detection": error_detection,
                "import_analysis": import_analysis,
                "pattern_analysis": pattern_analysis,
                "complexity_analysis": complexity_analysis,
            },
            "metrics": {
                "total_errors": len(validation_result.get("errors", [])),
                "total_warnings": len(validation_result.get("warnings", [])),
                "errors_caught": error_detection["errors_detected"],
                "errors_missed": error_detection["errors_missed"],
                "development_time_seconds": execution_time,
                "evaluation_time_seconds": round(evaluation_time, 3),
            },
            "success_criteria_met": self._check_success_criteria(
                challenge, functional_score, code_quality_score, performance_score
            ),
        }

    def _validate_code_quality(self, workflow_code: str) -> Dict[str, Any]:
        """Validate code quality using the parameter validator."""
        try:
            return self.validator.validate_workflow(workflow_code)
        except Exception as e:
            return {
                "has_errors": True,
                "errors": [
                    {
                        "code": "EVAL001",
                        "message": f"Validation error: {str(e)}",
                        "severity": "error",
                    }
                ],
                "warnings": [],
            }

    def _test_execution_safety(self, workflow_code: str) -> Dict[str, Any]:
        """Test if code can be safely parsed and analyzed (not executed)."""
        try:
            # Parse AST to check syntax
            tree = ast.parse(workflow_code)

            # Check for basic workflow construction
            has_workflow_builder = "WorkflowBuilder" in workflow_code
            has_runtime = any(
                runtime in workflow_code
                for runtime in ["LocalRuntime", "ParallelRuntime", "DockerRuntime"]
            )
            has_nodes = "add_node" in workflow_code
            has_connections = (
                "add_connection" in workflow_code or "connect" in workflow_code
            )

            # Count nodes and connections through AST analysis
            node_count = workflow_code.count("add_node")
            connection_count = workflow_code.count(
                "add_connection"
            ) + workflow_code.count(".connect(")

            syntax_valid = True
            structural_issues = []

            if not has_workflow_builder:
                structural_issues.append("Missing WorkflowBuilder instantiation")
            if not has_runtime:
                structural_issues.append("Missing runtime instantiation")
            if not has_nodes:
                structural_issues.append("No nodes added to workflow")
            if node_count > 1 and not has_connections:
                structural_issues.append("Multiple nodes but no connections")

            return {
                "syntax_valid": syntax_valid,
                "structural_complete": len(structural_issues) == 0,
                "structural_issues": structural_issues,
                "node_count": node_count,
                "connection_count": connection_count,
                "has_workflow_builder": has_workflow_builder,
                "has_runtime": has_runtime,
            }

        except SyntaxError as e:
            return {
                "syntax_valid": False,
                "syntax_error": str(e),
                "structural_complete": False,
                "structural_issues": ["Syntax error prevents analysis"],
                "node_count": 0,
                "connection_count": 0,
                "has_workflow_builder": False,
                "has_runtime": False,
            }
        except Exception as e:
            return {
                "syntax_valid": False,
                "analysis_error": str(e),
                "structural_complete": False,
                "structural_issues": ["Analysis error"],
                "node_count": 0,
                "connection_count": 0,
                "has_workflow_builder": False,
                "has_runtime": False,
            }

    def _check_planted_errors(
        self, workflow_code: str, challenge: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Check how many planted errors were detected/avoided."""
        planted_errors = challenge.get("planted_errors", [])
        validation_result = self.validator.validate_workflow(workflow_code)

        detected_error_types = set()
        all_errors = validation_result.get("errors", []) + validation_result.get(
            "warnings", []
        )

        # Map validation error codes to planted error types
        error_type_mapping = {
            "IMP001": "missing_imports",
            "CON002": "wrong_connection_syntax",
            "PAR004": "missing_parameters",
            "PAR003": "incorrect_parameter_types",
            "CYC001": "deprecated_patterns",
            "IMP004": "relative_imports",
            "IMP002": "unused_imports",
            "IMP006": "import_order_issues",
        }

        for error in all_errors:
            error_code = error.get("code", "")
            if error_code in error_type_mapping:
                detected_error_types.add(error_type_mapping[error_code])

        # Check which planted errors were caught
        planted_error_types = {error["type"] for error in planted_errors}
        errors_detected = len(planted_error_types.intersection(detected_error_types))
        errors_missed = len(planted_error_types - detected_error_types)

        return {
            "total_planted_errors": len(planted_errors),
            "errors_detected": errors_detected,
            "errors_missed": errors_missed,
            "detection_rate": (
                errors_detected / len(planted_errors) if planted_errors else 1.0
            ),
            "detected_types": list(detected_error_types),
            "missed_types": list(planted_error_types - detected_error_types),
        }

    def _analyze_imports(self, workflow_code: str) -> Dict[str, Any]:
        """Analyze import statements."""
        import_result = self.validator.validate_imports(workflow_code)

        import_errors = [
            e
            for e in import_result.get("errors", [])
            if e.get("code", "").startswith("IMP")
        ]
        import_warnings = [
            w
            for w in import_result.get("warnings", [])
            if w.get("code", "").startswith("IMP")
        ]

        return {
            "import_errors": len(import_errors),
            "import_warnings": len(import_warnings),
            "has_suggested_imports": len(import_result.get("suggested_imports", []))
            > 0,
            "import_error_details": import_errors,
            "import_correctness_score": max(
                0, 1.0 - (len(import_errors) * 0.2) - (len(import_warnings) * 0.1)
            ),
        }

    def _analyze_patterns(self, workflow_code: str) -> Dict[str, Any]:
        """Analyze code patterns and best practices."""
        # Check for common patterns
        has_error_handling = any(
            pattern in workflow_code.lower()
            for pattern in ["try:", "except:", "timeout", "retry", "error"]
        )

        has_proper_execution = "runtime.execute(workflow.build())" in workflow_code
        uses_deprecated_execution = "workflow.execute(runtime)" in workflow_code

        uses_snake_case = "add_node" in workflow_code
        uses_camel_case = "addNode" in workflow_code

        pattern_score = 1.0
        pattern_issues = []

        if not has_proper_execution and not uses_deprecated_execution:
            pattern_issues.append("No workflow execution found")
            pattern_score -= 0.3
        elif uses_deprecated_execution:
            pattern_issues.append("Uses deprecated execution pattern")
            pattern_score -= 0.2

        if uses_camel_case:
            pattern_issues.append("Uses camelCase instead of snake_case")
            pattern_score -= 0.1

        if not has_error_handling:
            pattern_issues.append("No error handling patterns detected")
            pattern_score -= 0.2

        return {
            "pattern_score": max(0, pattern_score),
            "pattern_issues": pattern_issues,
            "has_error_handling": has_error_handling,
            "uses_proper_execution": has_proper_execution,
            "uses_snake_case": uses_snake_case,
        }

    def _analyze_complexity(self, workflow_code: str) -> Dict[str, Any]:
        """Analyze workflow complexity."""
        try:
            complexity_result = self.validator.analyze_complexity(workflow_code)
            if complexity_result.get("has_analysis", False):
                return complexity_result
        except Exception:
            pass

        # Fallback simple analysis
        node_count = workflow_code.count("add_node")
        connection_count = workflow_code.count("add_connection")
        has_cycles = "create_cycle" in workflow_code or "cycle=" in workflow_code

        return {
            "has_analysis": False,
            "fallback_metrics": {
                "node_count": node_count,
                "connection_count": connection_count,
                "has_cycles": has_cycles,
                "complexity_score": node_count * 2
                + connection_count * 1.5
                + (10 if has_cycles else 0),
            },
        }

    def _calculate_functional_score(
        self,
        execution_result: Dict[str, Any],
        validation_result: Dict[str, Any],
        challenge: Dict[str, Any],
    ) -> float:
        """Calculate functional completeness score."""
        score = 1.0

        # Syntax and structure (40% of functional score)
        if not execution_result.get("syntax_valid", False):
            score *= 0.0  # Cannot function with syntax errors
        elif not execution_result.get("structural_complete", False):
            score *= 0.6  # Major structural issues

        # Error severity impact (40% of functional score)
        errors = validation_result.get("errors", [])
        critical_errors = [e for e in errors if e.get("severity") == "error"]

        if critical_errors:
            # Reduce score based on number of critical errors
            error_penalty = min(0.5, len(critical_errors) * 0.1)
            score *= 1.0 - error_penalty

        # Requirements fulfillment (20% of functional score)
        requirements_met = self._check_requirements_fulfillment(
            execution_result, challenge
        )
        score *= 0.8 + 0.2 * requirements_met

        return max(0.0, min(1.0, score))

    def _calculate_code_quality_score(
        self,
        validation_result: Dict[str, Any],
        import_analysis: Dict[str, Any],
        pattern_analysis: Dict[str, Any],
    ) -> float:
        """Calculate code quality score."""
        base_score = 1.0

        # Validation errors impact (50% of quality score)
        errors = validation_result.get("errors", [])
        warnings = validation_result.get("warnings", [])

        error_penalty = sum(
            self.error_weights.get(e.get("severity", "error"), 1.0) for e in errors
        )
        warning_penalty = sum(
            self.error_weights.get(w.get("severity", "warning"), 0.5) for w in warnings
        )

        validation_score = max(
            0, 1.0 - (error_penalty * 0.1) - (warning_penalty * 0.05)
        )

        # Import correctness (25% of quality score)
        import_score = import_analysis.get("import_correctness_score", 1.0)

        # Pattern adherence (25% of quality score)
        pattern_score = pattern_analysis.get("pattern_score", 1.0)

        overall_quality = (
            validation_score * 0.5 + import_score * 0.25 + pattern_score * 0.25
        )

        return max(0.0, min(1.0, overall_quality))

    def _calculate_performance_score(
        self,
        complexity_analysis: Dict[str, Any],
        execution_time: Optional[float],
        challenge: Dict[str, Any],
    ) -> float:
        """Calculate performance and efficiency score."""
        score = 1.0

        # Development time efficiency (50% of performance score)
        if execution_time is not None:
            expected_time = (
                challenge.get("metadata", {}).get("expected_duration_minutes", 15) * 60
            )
            if execution_time > expected_time:
                time_penalty = min(
                    0.5, (execution_time - expected_time) / expected_time
                )
                score *= 1.0 - time_penalty

        # Complexity appropriateness (30% of performance score)
        if complexity_analysis.get("has_analysis", False):
            metrics = complexity_analysis.get("metrics", {})
            node_count = metrics.get("node_count", 0)
            complexity_score = metrics.get("complexity_score", 0)

            # Check if complexity is appropriate for challenge level
            level = challenge.get("level", 1)
            expected_nodes = [0, 4, 8, 12, 20][level]  # Expected max nodes per level

            if node_count > expected_nodes * 1.5:
                score *= 0.7  # Over-engineered solution
            elif node_count < expected_nodes * 0.3:
                score *= 0.8  # Potentially under-engineered

        # Optimization suggestions (20% of performance score)
        optimization_suggestions = complexity_analysis.get(
            "optimization_suggestions", []
        )
        if len(optimization_suggestions) > 3:  # Many optimization opportunities
            score *= 0.8

        return max(0.0, min(1.0, score))

    def _check_requirements_fulfillment(
        self, execution_result: Dict[str, Any], challenge: Dict[str, Any]
    ) -> float:
        """Check what percentage of requirements are fulfilled."""
        # This is a simplified check - in practice would need more sophisticated analysis
        requirements = challenge.get("requirements", [])
        if not requirements:
            return 1.0

        fulfilled = 0
        total = len(requirements)

        # Basic structural requirements
        if execution_result.get("has_workflow_builder", False):
            fulfilled += 1
        if execution_result.get("has_runtime", False):
            fulfilled += 1
        if execution_result.get("node_count", 0) > 0:
            fulfilled += 1
        if (
            execution_result.get("connection_count", 0) > 0
            or execution_result.get("node_count", 0) <= 1
        ):
            fulfilled += 1

        # Cap at actual requirements count
        fulfilled = min(fulfilled, total)

        return fulfilled / total if total > 0 else 1.0

    def _check_success_criteria(
        self,
        challenge: Dict[str, Any],
        functional_score: float,
        code_quality_score: float,
        performance_score: float,
    ) -> Dict[str, bool]:
        """Check if success criteria are met."""
        criteria = challenge.get("success_criteria", {})
        level = challenge.get("level", 1)

        # Define thresholds based on difficulty level
        thresholds = {
            1: {"functional": 0.8, "code_quality": 0.7, "performance": 0.6},
            2: {"functional": 0.75, "code_quality": 0.75, "performance": 0.7},
            3: {"functional": 0.7, "code_quality": 0.8, "performance": 0.75},
            4: {"functional": 0.7, "code_quality": 0.85, "performance": 0.8},
        }

        level_thresholds = thresholds.get(level, thresholds[1])

        return {
            "functional_criteria_met": functional_score
            >= level_thresholds["functional"],
            "code_quality_criteria_met": code_quality_score
            >= level_thresholds["code_quality"],
            "performance_criteria_met": performance_score
            >= level_thresholds["performance"],
            "overall_success": (
                functional_score >= level_thresholds["functional"]
                and code_quality_score >= level_thresholds["code_quality"]
                and performance_score >= level_thresholds["performance"]
            ),
        }


class ABTestRunner:
    """Orchestrates A/B testing between baseline and MCP-enhanced conditions."""

    def __init__(self, challenges_file: str):
        """Initialize with challenge dataset."""
        self.evaluator = WorkflowEvaluator()
        self.challenges = self._load_challenges(challenges_file)

    def _load_challenges(self, challenges_file: str) -> List[Dict[str, Any]]:
        """Load challenges from JSON file."""
        with open(challenges_file, "r", encoding="utf-8") as f:
            dataset = json.load(f)
        return dataset["challenges"]

    def run_ab_test(self, num_challenges: int = None) -> Dict[str, Any]:
        """
        Run A/B test comparing baseline vs MCP-enhanced conditions.

        This is a framework - actual testing requires human Claude Code sessions.
        """
        if num_challenges is None:
            num_challenges = len(self.challenges)

        test_challenges = self.challenges[:num_challenges]

        print("A/B Test Framework Ready")
        print(f"Total challenges: {len(test_challenges)}")
        print("Conditions: Baseline (no MCP) vs Enhanced (with MCP)")
        print("Each challenge should be tested in both conditions")
        print("Results will be compared using automated evaluation")

        # Return test configuration
        return {
            "test_config": {
                "total_challenges": len(test_challenges),
                "conditions": ["baseline", "mcp_enhanced"],
                "total_sessions_needed": len(test_challenges) * 2,
                "evaluation_ready": True,
            },
            "challenges": test_challenges,
            "instructions": {
                "baseline_condition": "Test workflow development without MCP Parameter Validation Tool",
                "enhanced_condition": "Test workflow development with MCP Parameter Validation Tool enabled",
                "evaluation_method": "Automated scoring using WorkflowEvaluator",
                "metrics_tracked": [
                    "functional_score",
                    "code_quality_score",
                    "performance_score",
                    "overall_score",
                ],
            },
        }

    def evaluate_session_result(
        self,
        workflow_code: str,
        challenge_id: str,
        condition: str,
        execution_time: float = None,
    ) -> Dict[str, Any]:
        """Evaluate a single test session result."""
        # Find the challenge
        challenge = next(
            (c for c in self.challenges if c["challenge_id"] == challenge_id), None
        )
        if not challenge:
            raise ValueError(f"Challenge {challenge_id} not found")

        # Evaluate the submission
        result = self.evaluator.evaluate_submission(
            workflow_code, challenge, execution_time
        )
        result["test_condition"] = condition
        result["timestamp"] = time.time()

        return result


def main():
    """Example usage of the evaluation system."""
    # Sample workflow code for testing
    sample_code = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4", "prompt": "Analyze the data"})
workflow.add_node("HTTPRequestNode", "api", {"url": "https://api.example.com", "method": "POST"})
workflow.add_connection("agent", "result", "api", "data")

runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""

    # Sample challenge
    sample_challenge = {
        "challenge_id": "WF001",
        "level": 2,
        "pattern": "linear",
        "domain": "api_integration",
        "title": "API Integration Pipeline",
        "description": "Create a workflow that processes data and sends to API",
        "requirements": ["Use proper imports", "Include error handling"],
        "planted_errors": [
            {"type": "missing_imports", "description": "Missing import statements"}
        ],
        "success_criteria": {
            "functional": ["workflow executes", "nodes connected"],
            "code_quality": ["proper imports", "no deprecated patterns"],
            "performance": ["reasonable complexity"],
        },
        "metadata": {"expected_duration_minutes": 10},
    }

    # Evaluate the sample
    evaluator = WorkflowEvaluator()
    result = evaluator.evaluate_submission(
        sample_code, sample_challenge, execution_time=300
    )

    print("=== Evaluation Result ===")
    print(f"Overall Score: {result['overall_score']}")
    print(f"Component Scores: {result['component_scores']}")
    print(f"Total Errors: {result['metrics']['total_errors']}")
    print(f"Errors Detected: {result['metrics']['errors_caught']}")
    print(f"Success Criteria Met: {result['success_criteria_met']['overall_success']}")


if __name__ == "__main__":
    main()
