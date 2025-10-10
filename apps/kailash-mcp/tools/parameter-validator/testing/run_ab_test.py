"""
Practical A/B testing script for MCP Parameter Validation Tool effectiveness.
Provides instructions and framework for conducting bias-free testing.
"""

import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List

from challenge_generator import WorkflowChallengeGenerator
from evaluation_system import ABTestRunner, WorkflowEvaluator


class MCPToolABTest:
    """Coordinate A/B testing of MCP Parameter Validation Tool."""

    def __init__(self):
        """Initialize testing framework."""
        self.generator = WorkflowChallengeGenerator()
        self.evaluator = WorkflowEvaluator()
        self.test_results = []

    def setup_test_environment(self, num_challenges: int = 20) -> Dict[str, Any]:
        """
        Set up the A/B testing environment.

        Args:
            num_challenges: Number of challenges to use for testing (default 20 for quick test)

        Returns:
            Test configuration and instructions
        """
        print("🚀 Setting up MCP Parameter Validation Tool A/B Test")
        print("=" * 60)

        # Generate challenges
        print(f"📋 Generating {num_challenges} workflow challenges...")
        challenges = self.generator.generate_challenge_dataset(num_challenges)

        # Save challenges for reference
        challenges_file = Path("testing/datasets/ab_test_challenges.json")
        self.generator.save_challenge_dataset(challenges, str(challenges_file))

        # Create randomized test order
        test_sessions = []
        for challenge in challenges:
            # Each challenge tested in both conditions
            test_sessions.append(
                {
                    "session_id": f"{challenge['challenge_id']}_baseline",
                    "challenge_id": challenge["challenge_id"],
                    "condition": "baseline",
                    "order": random.randint(1, 1000),
                }
            )
            test_sessions.append(
                {
                    "session_id": f"{challenge['challenge_id']}_mcp",
                    "challenge_id": challenge["challenge_id"],
                    "condition": "mcp_enhanced",
                    "order": random.randint(1, 1000),
                }
            )

        # Randomize order to prevent learning effects
        random.shuffle(test_sessions)

        # Save test plan
        test_plan = {
            "metadata": {
                "test_type": "A/B Testing - MCP Parameter Validation Tool",
                "total_challenges": num_challenges,
                "total_sessions": len(test_sessions),
                "conditions": {
                    "baseline": "Claude Code without MCP Parameter Validation Tool",
                    "mcp_enhanced": "Claude Code with MCP Parameter Validation Tool enabled",
                },
                "bias_prevention": [
                    "External challenge dataset (no lookahead bias)",
                    "Randomized session order",
                    "Fresh Claude Code session for each test",
                    "Automated evaluation criteria",
                ],
            },
            "challenges": challenges,
            "test_sessions": test_sessions,
        }

        test_plan_file = Path("testing/datasets/ab_test_plan.json")
        test_plan_file.parent.mkdir(parents=True, exist_ok=True)
        with open(test_plan_file, "w", encoding="utf-8") as f:
            json.dump(test_plan, f, indent=2)

        print(f"✅ Test plan saved: {test_plan_file}")
        print(f"📊 Total test sessions: {len(test_sessions)}")
        print(
            f"🔄 Conditions: baseline ({len([s for s in test_sessions if s['condition'] == 'baseline'])}), "
            f"mcp_enhanced ({len([s for s in test_sessions if s['condition'] == 'mcp_enhanced'])})"
        )

        return test_plan

    def get_test_instructions(self) -> str:
        """Get detailed instructions for conducting the A/B test."""
        instructions = """
🎯 MCP Parameter Validation Tool A/B Testing Instructions

OBJECTIVE: Compare Claude Code performance with and without MCP Parameter Validation Tool

⚠️  CRITICAL: NO LOOKAHEAD BIAS
- Each test uses a fresh Claude Code session (no prior context)
- Challenges are external (not created in Claude's context)
- Identical prompts for both conditions
- No hints about errors or solutions

📋 TESTING PROCEDURE:

1. SETUP PHASE:
   - Load the test plan: ab_test_plan.json
   - Prepare two Claude Code environments:
     * Baseline: Standard Claude Code (no MCP tools)
     * Enhanced: Claude Code with MCP Parameter Validation Tool enabled

2. FOR EACH TEST SESSION:
   
   a) START FRESH SESSION
      - Open new Claude Code session
      - Clear all context and memory
      - Ensure correct condition (baseline vs mcp_enhanced)
   
   b) PRESENT CHALLENGE
      - Use EXACTLY this prompt format:
      
      "I need help creating a Kailash SDK workflow. Here are the requirements:
      
      Challenge: [CHALLENGE_TITLE]
      Description: [CHALLENGE_DESCRIPTION]
      
      Requirements:
      [LIST_ALL_REQUIREMENTS]
      
      Constraints:
      [LIST_ALL_CONSTRAINTS]
      
      Please create a complete workflow that meets these requirements."
   
   c) TRACK TIMING
      - Start timer when challenge is presented
      - Stop timer when working solution is achieved
      - Record all debug iterations and fixes
   
   d) CAPTURE RESULTS
      - Final workflow code
      - Total development time
      - Number of iterations/fixes needed
      - Any errors encountered

3. EVALUATION:
   - Use evaluation_system.py to score each submission
   - Record results in standardized format
   - No manual scoring - use automated evaluation only

📊 WHAT TO MEASURE:

Primary Metrics:
✓ Functional Success Rate (does workflow execute?)
✓ Code Quality Score (imports, patterns, validation)
✓ Error Detection Rate (caught before execution?)
✓ Time to Working Solution

Secondary Metrics:
✓ Debug Iterations Needed
✓ Import Statement Correctness
✓ Parameter Validation Completeness
✓ Connection Syntax Accuracy

🚫 WHAT NOT TO DO:

❌ Don't give hints about common errors
❌ Don't mention MCP tool capabilities in baseline condition
❌ Don't reuse sessions across different challenges
❌ Don't manually evaluate - use automated scoring only
❌ Don't look at solutions before testing

✅ VALIDITY CHECKLIST:

Before starting:
□ Challenge dataset is external (not created in Claude's context)
□ Two identical environments prepared (only MCP tool differs)
□ Randomized session order prepared
□ Automated evaluation system tested
□ No prior knowledge of challenges or solutions

During testing:
□ Fresh session for each test
□ Identical prompts used
□ Timing accurately recorded
□ All results captured
□ No manual intervention in scoring

After testing:
□ All sessions completed
□ Results evaluated automatically
□ Statistical analysis performed
□ Bias sources eliminated

📈 EXPECTED OUTCOMES:

If MCP Tool is Effective:
- Higher functional success rates
- Fewer debug iterations
- Better code quality scores
- Faster time to working solution

If Tool Shows No Benefit:
- Similar performance across conditions
- No significant differences in metrics
- Need to analyze why tool didn't help

🔬 STATISTICAL ANALYSIS:

Use these tests:
- Paired t-test for continuous metrics (scores, times)
- Chi-square test for categorical outcomes (success/failure)
- Effect size calculation (Cohen's d)
- 95% confidence intervals for all estimates

Significance threshold: p < 0.05
Minimum effect size for practical significance: d > 0.5

📝 REPORTING:

Create report with:
1. Executive summary of findings
2. Statistical test results
3. Effect sizes and confidence intervals
4. Detailed analysis by challenge difficulty
5. Recommendations for tool improvement
6. Methodology validation and bias checks

🎯 SUCCESS CRITERIA FOR MCP TOOL:

Tool considered effective if:
✓ ≥20% improvement in functional success rate
✓ ≥30% reduction in debug iterations  
✓ ≥50% improvement in code quality scores
✓ Statistical significance (p < 0.05) across metrics
✓ Effect size > 0.5 (medium effect)

Remember: The goal is unbiased evaluation. If the tool doesn't show clear benefits, 
that's valuable information for improvement, not a failure of the testing process.
"""
        return instructions

    def evaluate_test_session(
        self,
        session_id: str,
        workflow_code: str,
        development_time: float,
        debug_iterations: int = 0,
    ) -> Dict[str, Any]:
        """
        Evaluate a single test session result.

        Args:
            session_id: Unique identifier for the test session
            workflow_code: The submitted workflow code
            development_time: Time taken to develop solution (seconds)
            debug_iterations: Number of fix attempts needed

        Returns:
            Evaluation results
        """
        # Load test plan to get challenge details
        test_plan_file = Path("testing/datasets/ab_test_plan.json")
        if not test_plan_file.exists():
            raise FileNotFoundError(
                "Test plan not found. Run setup_test_environment() first."
            )

        with open(test_plan_file, "r", encoding="utf-8") as f:
            test_plan = json.load(f)

        # Find session details
        session = next(
            (s for s in test_plan["test_sessions"] if s["session_id"] == session_id),
            None,
        )
        if not session:
            raise ValueError(f"Session {session_id} not found in test plan")

        # Find challenge details
        challenge = next(
            (
                c
                for c in test_plan["challenges"]
                if c["challenge_id"] == session["challenge_id"]
            ),
            None,
        )
        if not challenge:
            raise ValueError(f"Challenge {session['challenge_id']} not found")

        # Evaluate using automated system
        result = self.evaluator.evaluate_submission(
            workflow_code=workflow_code,
            challenge=challenge,
            execution_time=development_time,
        )

        # Add session-specific information
        result.update(
            {
                "session_id": session_id,
                "test_condition": session["condition"],
                "debug_iterations": debug_iterations,
                "timestamp": time.time(),
            }
        )

        # Save individual result
        results_dir = Path("testing/results")
        results_dir.mkdir(parents=True, exist_ok=True)

        result_file = results_dir / f"{session_id}_result.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

        print(f"📊 Session {session_id} evaluated:")
        print(f"   Overall Score: {result['overall_score']:.3f}")
        print(f"   Condition: {session['condition']}")
        print(f"   Development Time: {development_time:.1f}s")
        print(f"   Debug Iterations: {debug_iterations}")
        print(f"   Result saved: {result_file}")

        return result

    def analyze_results(self) -> Dict[str, Any]:
        """Analyze all test results and compare conditions."""
        results_dir = Path("testing/results")
        if not results_dir.exists():
            raise FileNotFoundError("No results found. Complete test sessions first.")

        # Load all results
        all_results = []
        for result_file in results_dir.glob("*_result.json"):
            with open(result_file, "r", encoding="utf-8") as f:
                all_results.append(json.load(f))

        if not all_results:
            raise ValueError("No test results found")

        # Separate by condition
        baseline_results = [r for r in all_results if r["test_condition"] == "baseline"]
        mcp_results = [r for r in all_results if r["test_condition"] == "mcp_enhanced"]

        print(f"📈 Analyzing {len(all_results)} test results:")
        print(f"   Baseline: {len(baseline_results)} sessions")
        print(f"   MCP Enhanced: {len(mcp_results)} sessions")

        # Calculate comparative metrics
        analysis = {
            "summary": {
                "total_sessions": len(all_results),
                "baseline_sessions": len(baseline_results),
                "mcp_sessions": len(mcp_results),
                "analysis_timestamp": time.time(),
            },
            "baseline_metrics": self._calculate_condition_metrics(baseline_results),
            "mcp_metrics": self._calculate_condition_metrics(mcp_results),
        }

        # Calculate improvements
        if baseline_results and mcp_results:
            analysis["improvements"] = self._calculate_improvements(
                analysis["baseline_metrics"], analysis["mcp_metrics"]
            )

        # Save analysis
        analysis_file = Path("testing/results/ab_test_analysis.json")
        with open(analysis_file, "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2)

        print(f"📊 Analysis complete: {analysis_file}")
        return analysis

    def _calculate_condition_metrics(
        self, results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate metrics for a single condition."""
        if not results:
            return {}

        # Extract metrics
        overall_scores = [r["overall_score"] for r in results]
        functional_scores = [r["component_scores"]["functional"] for r in results]
        quality_scores = [r["component_scores"]["code_quality"] for r in results]
        performance_scores = [r["component_scores"]["performance"] for r in results]

        development_times = [
            r["metrics"]["development_time_seconds"]
            for r in results
            if r["metrics"]["development_time_seconds"]
        ]
        debug_iterations = [r["debug_iterations"] for r in results]

        success_rate = sum(
            1 for r in results if r["success_criteria_met"]["overall_success"]
        ) / len(results)

        return {
            "count": len(results),
            "overall_score": {
                "mean": sum(overall_scores) / len(overall_scores),
                "min": min(overall_scores),
                "max": max(overall_scores),
            },
            "functional_score": {
                "mean": sum(functional_scores) / len(functional_scores),
                "success_rate": success_rate,
            },
            "code_quality_score": {"mean": sum(quality_scores) / len(quality_scores)},
            "performance_score": {
                "mean": sum(performance_scores) / len(performance_scores)
            },
            "development_time": {
                "mean": (
                    sum(development_times) / len(development_times)
                    if development_times
                    else 0
                ),
                "count": len(development_times),
            },
            "debug_iterations": {
                "mean": sum(debug_iterations) / len(debug_iterations),
                "total": sum(debug_iterations),
            },
        }

    def _calculate_improvements(
        self, baseline: Dict[str, Any], mcp: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate percentage improvements from baseline to MCP condition."""
        improvements = {}

        # Overall score improvement
        if baseline["overall_score"]["mean"] > 0:
            improvements["overall_score_improvement"] = (
                (mcp["overall_score"]["mean"] - baseline["overall_score"]["mean"])
                / baseline["overall_score"]["mean"]
                * 100
            )

        # Success rate improvement
        improvements["success_rate_improvement"] = (
            mcp["functional_score"]["success_rate"]
            - baseline["functional_score"]["success_rate"]
        ) * 100

        # Code quality improvement
        if baseline["code_quality_score"]["mean"] > 0:
            improvements["code_quality_improvement"] = (
                (
                    mcp["code_quality_score"]["mean"]
                    - baseline["code_quality_score"]["mean"]
                )
                / baseline["code_quality_score"]["mean"]
                * 100
            )

        # Debug iterations reduction
        if baseline["debug_iterations"]["mean"] > 0:
            improvements["debug_iterations_reduction"] = (
                (baseline["debug_iterations"]["mean"] - mcp["debug_iterations"]["mean"])
                / baseline["debug_iterations"]["mean"]
                * 100
            )

        # Development time improvement (negative = faster)
        if (
            baseline["development_time"]["mean"] > 0
            and mcp["development_time"]["mean"] > 0
        ):
            improvements["development_time_improvement"] = (
                (baseline["development_time"]["mean"] - mcp["development_time"]["mean"])
                / baseline["development_time"]["mean"]
                * 100
            )

        return improvements


def main():
    """Main entry point for A/B testing."""
    tester = MCPToolABTest()

    print("🔬 MCP Parameter Validation Tool - A/B Testing Framework")
    print("=" * 60)

    # Setup test
    test_plan = tester.setup_test_environment(num_challenges=10)  # Small test for demo

    # Print instructions
    print("\n📋 NEXT STEPS:")
    print(
        "1. Review the generated challenges in: testing/datasets/ab_test_challenges.json"
    )
    print("2. Follow the detailed instructions below")
    print("3. Complete test sessions for both conditions")
    print("4. Use evaluate_test_session() to score each submission")
    print("5. Run analyze_results() for final comparison")

    print("\n" + "=" * 60)
    print(tester.get_test_instructions())

    # Example evaluation (for demonstration)
    print("\n🎯 EXAMPLE: How to evaluate a test session")
    print("-" * 40)

    sample_code = """
from kailash.workflow.builder import WorkflowBuilder
from kailash.runtime.local import LocalRuntime

workflow = WorkflowBuilder()
workflow.add_node("LLMAgentNode", "agent", {"model": "gpt-4"})
runtime = LocalRuntime()
results, run_id = runtime.execute(workflow.build())
"""

    # This would be done after actual testing
    # result = tester.evaluate_test_session(
    #     session_id="WF101_baseline",
    #     workflow_code=sample_code,
    #     development_time=180.5,
    #     debug_iterations=2
    # )

    print("Use tester.evaluate_test_session() after completing each session")
    print("Use tester.analyze_results() after all sessions are complete")


if __name__ == "__main__":
    main()
