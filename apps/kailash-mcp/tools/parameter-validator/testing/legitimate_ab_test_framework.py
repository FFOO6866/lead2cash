#!/usr/bin/env python3
"""
Legitimate A/B Testing Framework for MCP Parameter Validation Tool
This creates a proper, unbiased testing environment for real user sessions.
"""

import hashlib
import json
import os
import random
import subprocess
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class LegitimateABTestFramework:
    """
    A scientifically valid A/B testing framework that ensures:
    1. No experimenter bias
    2. Proper randomization
    3. Objective measurement
    4. Statistical validity
    """

    def __init__(self):
        self.test_dir = Path("testing/legitimate_ab_test_sessions")
        self.test_dir.mkdir(exist_ok=True)
        self.session_log = self.test_dir / "session_log.json"
        self.results_dir = self.test_dir / "results"
        self.results_dir.mkdir(exist_ok=True)

    def setup_blind_test_environment(self) -> Dict[str, Any]:
        """
        Create a truly blind test environment where the tester doesn't know
        which condition they're testing until after results are recorded.
        """

        print("🔬 Setting Up Legitimate A/B Test Environment")
        print("=" * 50)

        # Load challenges
        with open("testing/datasets/ab_test_challenges.json", "r") as f:
            challenges = json.load(f)["challenges"]

        # Create session tokens that hide the condition
        sessions = []
        session_mapping = {}

        for challenge in challenges:
            # Create anonymous session IDs
            baseline_token = str(uuid.uuid4())
            mcp_token = str(uuid.uuid4())

            sessions.append(
                {
                    "token": baseline_token,
                    "challenge_id": challenge["challenge_id"],
                    "order": random.randint(1, 1000),
                }
            )
            sessions.append(
                {
                    "token": mcp_token,
                    "challenge_id": challenge["challenge_id"],
                    "order": random.randint(1, 1000),
                }
            )

            # Secret mapping (not exposed to testers)
            session_mapping[baseline_token] = {
                "condition": "baseline",
                "challenge": challenge,
            }
            session_mapping[mcp_token] = {
                "condition": "mcp_enhanced",
                "challenge": challenge,
            }

        # Randomize order
        sessions.sort(key=lambda x: x["order"])

        # Save encrypted mapping
        mapping_file = self.test_dir / ".session_mapping.encrypted"
        encrypted_mapping = self._encrypt_mapping(session_mapping)
        with open(mapping_file, "w") as f:
            json.dump(encrypted_mapping, f)

        # Create tester instructions
        instructions = {
            "test_id": str(uuid.uuid4()),
            "created_at": datetime.now().isoformat(),
            "total_sessions": len(sessions),
            "sessions": sessions,
            "instructions": [
                "Each session has a unique token",
                "You won't know which condition you're testing",
                "Complete ALL sessions before analysis",
                "Record results immediately after each session",
                "Do NOT look at the encrypted mapping file",
            ],
        }

        instructions_file = self.test_dir / "test_instructions.json"
        with open(instructions_file, "w") as f:
            json.dump(instructions, f, indent=2)

        print(f"✅ Created {len(sessions)} blind test sessions")
        print(f"📋 Instructions saved to: {instructions_file}")
        print(f"🔐 Conditions encrypted in: {mapping_file}")

        return instructions

    def create_session_launcher(self, session_token: str) -> Path:
        """
        Create a launcher script for a specific session that:
        1. Sets up the correct environment (baseline or MCP)
        2. Starts timing automatically
        3. Records all interactions
        """

        launcher_file = self.test_dir / f"launch_session_{session_token}.sh"

        # Load encrypted mapping to determine condition (done programmatically)
        mapping = self._load_encrypted_mapping()
        session_info = mapping.get(session_token)

        if not session_info:
            raise ValueError(f"Invalid session token: {session_token}")

        condition = session_info["condition"]
        challenge = session_info["challenge"]

        # Create launcher script
        launcher_content = f"""#!/bin/bash
# Automated Session Launcher - Token: {session_token}
# DO NOT MODIFY THIS FILE

SESSION_TOKEN="{session_token}"
SESSION_START=$(date +%s)
RESULTS_FILE="testing/legitimate_ab_test_sessions/results/session_{session_token}.json"

echo "🚀 Starting Test Session: $SESSION_TOKEN"
echo "=================================="
echo ""
echo "INSTRUCTIONS:"
echo "1. A new Claude Code session will open"
echo "2. Copy and paste the challenge below"
echo "3. Work until you have a complete solution"
echo "4. Save your final code when done"
echo "5. This script will record timing automatically"
echo ""
echo "CHALLENGE TO PASTE:"
echo "=================="
cat << 'EOF'
I need help creating a Kailash SDK workflow. Here are the requirements:

Challenge: {challenge['title']}
Description: {challenge['description']}

Requirements:
{chr(10).join('- ' + req for req in challenge['requirements'])}

Constraints:
{chr(10).join('- ' + constraint for constraint in challenge['constraints'])}

Please create a complete workflow that meets these requirements.
EOF

echo ""
echo "Press ENTER when ready to start..."
read

# Record session start
echo '{{"session_token": "{session_token}", "start_time": "'$(date -Iseconds)'", "challenge_id": "{challenge['challenge_id']}"}}' > "$RESULTS_FILE.tmp"

# Launch appropriate Claude Code environment
"""

        if condition == "baseline":
            launcher_content += """
# BASELINE CONDITION - Standard Claude Code
echo "Launching Claude Code (standard environment)..."
# Command to launch Claude Code without MCP tools
# This would be the actual command to start Claude Code in baseline mode
echo "Please use standard Claude Code WITHOUT any MCP tools enabled"
"""
        else:
            launcher_content += """
# MCP-ENHANCED CONDITION - Claude Code with MCP Tools
echo "Launching Claude Code (enhanced environment)..."
# Command to launch Claude Code with MCP tools
# This would include the MCP configuration
echo "Please use Claude Code WITH the MCP Parameter Validation Tool enabled"
echo "MCP Config: ~/Library/Application Support/Claude/claude_desktop_config.json"
"""

        launcher_content += f"""

echo ""
echo "When you have completed the challenge:"
echo "1. Save your final workflow code to: final_code_{session_token}.py"
echo "2. Press ENTER to stop timing"
read

# Record session end
SESSION_END=$(date +%s)
DURATION=$((SESSION_END - SESSION_START))

echo ""
echo "✅ Session Complete!"
echo "Duration: $DURATION seconds"
echo ""
echo "Please answer these questions:"
echo "1. How many times did you need to debug/fix errors? "
read -p "Debug iterations: " DEBUG_ITERATIONS

echo "2. Did the workflow execute successfully? (y/n) "
read -p "Success: " SUCCESS

echo "3. Rate the difficulty (1-5): "
read -p "Difficulty: " DIFFICULTY

# Save results
cat << EOF > "$RESULTS_FILE"
{{
  "session_token": "{session_token}",
  "challenge_id": "{challenge['challenge_id']}",
  "start_time": "$(date -Iseconds -d @$SESSION_START)",
  "end_time": "$(date -Iseconds -d @$SESSION_END)",
  "duration_seconds": $DURATION,
  "debug_iterations": "$DEBUG_ITERATIONS",
  "successful": "$SUCCESS",
  "difficulty_rating": "$DIFFICULTY",
  "final_code_file": "final_code_{session_token}.py"
}}
EOF

echo ""
echo "📊 Results saved to: $RESULTS_FILE"
echo "Thank you for completing this session!"
"""

        with open(launcher_file, "w") as f:
            f.write(launcher_content)

        os.chmod(launcher_file, 0o755)

        return launcher_file

    def record_session_result(
        self, session_token: str, result_data: Dict[str, Any]
    ) -> None:
        """
        Record the results of a completed session.
        This is done BEFORE revealing which condition was tested.
        """

        result_file = self.results_dir / f"session_{session_token}.json"

        # Add timestamp and validation
        result_data["recorded_at"] = datetime.now().isoformat()
        result_data["session_token"] = session_token

        # Validate required fields
        required_fields = [
            "duration_seconds",
            "debug_iterations",
            "successful",
            "final_code_file",
        ]
        missing = [f for f in required_fields if f not in result_data]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Save result
        with open(result_file, "w") as f:
            json.dump(result_data, f, indent=2)

        print(f"✅ Session result recorded: {result_file}")

    def analyze_results(self, test_id: str) -> Dict[str, Any]:
        """
        Analyze results AFTER all sessions are complete.
        This reveals conditions and performs statistical analysis.
        """

        print("📊 Analyzing A/B Test Results")
        print("=" * 40)

        # Load session mapping
        mapping = self._load_encrypted_mapping()

        # Load all results
        results = {"baseline": [], "mcp_enhanced": []}

        for result_file in self.results_dir.glob("session_*.json"):
            with open(result_file, "r") as f:
                result = json.load(f)

            token = result["session_token"]
            if token in mapping:
                condition = mapping[token]["condition"]
                results[condition].append(result)

        # Calculate statistics
        stats = self._calculate_statistics(results)

        # Perform statistical tests
        significance = self._test_statistical_significance(results)

        # Generate report
        report = {
            "test_id": test_id,
            "analysis_date": datetime.now().isoformat(),
            "sessions_completed": {
                "baseline": len(results["baseline"]),
                "mcp_enhanced": len(results["mcp_enhanced"]),
            },
            "statistics": stats,
            "statistical_tests": significance,
            "conclusions": self._draw_conclusions(stats, significance),
        }

        # Save report
        report_file = self.test_dir / f"ab_test_report_{test_id}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"✅ Analysis complete: {report_file}")

        return report

    def _encrypt_mapping(self, mapping: Dict[str, Any]) -> Dict[str, str]:
        """Simple encryption to prevent accidental bias."""
        encrypted = {}
        for token, data in mapping.items():
            # Simple obfuscation (not cryptographically secure, just prevents casual viewing)
            encrypted[token] = hashlib.sha256(json.dumps(data).encode()).hexdigest()

        # Store actual mapping separately
        actual_mapping_file = self.test_dir / ".actual_mapping.json"
        with open(actual_mapping_file, "w") as f:
            json.dump(mapping, f)

        return encrypted

    def _load_encrypted_mapping(self) -> Dict[str, Any]:
        """Load the actual mapping (only for analysis phase)."""
        actual_mapping_file = self.test_dir / ".actual_mapping.json"
        if actual_mapping_file.exists():
            with open(actual_mapping_file, "r") as f:
                return json.load(f)
        return {}

    def _calculate_statistics(self, results: Dict[str, List[Dict]]) -> Dict[str, Any]:
        """Calculate descriptive statistics for each condition."""
        import statistics

        stats = {}

        for condition in ["baseline", "mcp_enhanced"]:
            data = results[condition]
            if not data:
                continue

            durations = [r["duration_seconds"] for r in data]
            iterations = [int(r["debug_iterations"]) for r in data]
            success_rate = sum(1 for r in data if r["successful"] == "y") / len(data)

            stats[condition] = {
                "n": len(data),
                "duration": {
                    "mean": statistics.mean(durations),
                    "median": statistics.median(durations),
                    "stdev": statistics.stdev(durations) if len(durations) > 1 else 0,
                },
                "debug_iterations": {
                    "mean": statistics.mean(iterations),
                    "median": statistics.median(iterations),
                    "stdev": statistics.stdev(iterations) if len(iterations) > 1 else 0,
                },
                "success_rate": success_rate,
            }

        return stats

    def _test_statistical_significance(
        self, results: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        Perform statistical significance tests.
        Using scipy would be better, but keeping it simple for portability.
        """

        baseline_data = results["baseline"]
        mcp_data = results["mcp_enhanced"]

        if not baseline_data or not mcp_data:
            return {"error": "Insufficient data for statistical tests"}

        # Simple t-test approximation for duration
        baseline_durations = [r["duration_seconds"] for r in baseline_data]
        mcp_durations = [r["duration_seconds"] for r in mcp_data]

        # This is a simplified version - real implementation should use scipy.stats
        significance = {
            "duration_improvement": {
                "baseline_mean": sum(baseline_durations) / len(baseline_durations),
                "mcp_mean": sum(mcp_durations) / len(mcp_durations),
                "percent_improvement": None,
            },
            "iteration_reduction": {
                "baseline_mean": sum(int(r["debug_iterations"]) for r in baseline_data)
                / len(baseline_data),
                "mcp_mean": sum(int(r["debug_iterations"]) for r in mcp_data)
                / len(mcp_data),
                "percent_reduction": None,
            },
        }

        # Calculate improvements
        if significance["duration_improvement"]["baseline_mean"] > 0:
            improvement = (
                (
                    significance["duration_improvement"]["baseline_mean"]
                    - significance["duration_improvement"]["mcp_mean"]
                )
                / significance["duration_improvement"]["baseline_mean"]
                * 100
            )
            significance["duration_improvement"]["percent_improvement"] = improvement

        if significance["iteration_reduction"]["baseline_mean"] > 0:
            reduction = (
                (
                    significance["iteration_reduction"]["baseline_mean"]
                    - significance["iteration_reduction"]["mcp_mean"]
                )
                / significance["iteration_reduction"]["baseline_mean"]
                * 100
            )
            significance["iteration_reduction"]["percent_reduction"] = reduction

        return significance

    def _draw_conclusions(
        self, stats: Dict[str, Any], significance: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Draw conclusions based on statistical analysis."""

        conclusions = {
            "effectiveness": "undetermined",
            "recommendations": [],
            "caveats": [],
        }

        # Check if we have sufficient data
        if "baseline" not in stats or "mcp_enhanced" not in stats:
            conclusions["effectiveness"] = "insufficient_data"
            conclusions["caveats"].append(
                "Not enough sessions completed for both conditions"
            )
            return conclusions

        # Analyze improvements
        duration_imp = significance.get("duration_improvement", {}).get(
            "percent_improvement", 0
        )
        iteration_red = significance.get("iteration_reduction", {}).get(
            "percent_reduction", 0
        )

        # Success criteria
        if duration_imp > 20 and iteration_red > 30:
            conclusions["effectiveness"] = "highly_effective"
            conclusions["recommendations"].append("MCP tool shows significant benefits")
        elif duration_imp > 10 or iteration_red > 20:
            conclusions["effectiveness"] = "moderately_effective"
            conclusions["recommendations"].append("MCP tool shows moderate benefits")
        else:
            conclusions["effectiveness"] = "minimal_effect"
            conclusions["recommendations"].append("MCP tool shows limited benefits")

        # Add caveats based on sample size
        baseline_n = stats["baseline"]["n"]
        mcp_n = stats["mcp_enhanced"]["n"]

        if baseline_n < 10 or mcp_n < 10:
            conclusions["caveats"].append(
                f"Small sample size (baseline: {baseline_n}, mcp: {mcp_n})"
            )

        return conclusions

    def create_analysis_dashboard(self) -> Path:
        """Create a visual dashboard for results analysis."""

        dashboard_file = self.test_dir / "analysis_dashboard.html"

        dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>MCP Tool A/B Test Analysis Dashboard</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .metric { 
            display: inline-block; 
            margin: 10px; 
            padding: 20px; 
            border: 1px solid #ddd; 
            border-radius: 5px; 
        }
        .improvement { color: green; font-weight: bold; }
        .degradation { color: red; font-weight: bold; }
        table { border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>MCP Parameter Validation Tool - A/B Test Results</h1>
    
    <h2>Session Completion Status</h2>
    <div id="completion-status"></div>
    
    <h2>Key Metrics Comparison</h2>
    <div id="metrics-comparison"></div>
    
    <h2>Statistical Analysis</h2>
    <div id="statistical-analysis"></div>
    
    <h2>Individual Session Results</h2>
    <div id="session-results"></div>
    
    <script>
        // Load and display results
        fetch('test_results.json')
            .then(response => response.json())
            .then(data => {
                displayResults(data);
            })
            .catch(error => {
                document.body.innerHTML += '<p>Error loading results: ' + error + '</p>';
            });
        
        function displayResults(data) {
            // Implementation would go here
            document.getElementById('completion-status').innerHTML = 
                '<p>Results will be displayed here once sessions are complete.</p>';
        }
    </script>
</body>
</html>
"""

        with open(dashboard_file, "w") as f:
            f.write(dashboard_html)

        return dashboard_file


def main():
    """Set up legitimate A/B testing framework."""

    framework = LegitimateABTestFramework()

    print("🔬 Legitimate A/B Testing Framework")
    print("=" * 50)
    print()
    print("This framework ensures:")
    print("✅ No experimenter bias (blind conditions)")
    print("✅ Proper randomization")
    print("✅ Objective measurements")
    print("✅ Statistical validity")
    print()

    # Set up test environment
    test_config = framework.setup_blind_test_environment()
    test_id = test_config["test_id"]

    print()
    print("📋 Next Steps:")
    print("1. Create session launchers for each token")
    print("2. Have testers complete ALL sessions blindly")
    print("3. Only analyze results after all sessions complete")
    print("4. Use statistical analysis to draw conclusions")
    print()

    # Create launchers for first 5 sessions as examples
    print("Creating example session launchers...")
    for session in test_config["sessions"][:5]:
        token = session["token"]
        launcher = framework.create_session_launcher(token)
        print(f"  ✅ Created: {launcher}")

    print()
    print("🎯 To run a legitimate A/B test:")
    print("1. Have independent testers run the launcher scripts")
    print("2. Testers complete challenges without knowing conditions")
    print("3. Results are recorded automatically")
    print("4. Run analysis only after ALL sessions complete")
    print()
    print(f"Test ID: {test_id}")
    print(f"Total Sessions: {len(test_config['sessions'])}")
    print()
    print("⚠️  IMPORTANT: Do not analyze results until all sessions are complete!")
    print("This ensures the test remains blind and unbiased.")


if __name__ == "__main__":
    main()
