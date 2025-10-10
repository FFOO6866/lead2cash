#!/bin/bash
# Automated Session Launcher - Token: b85492a6-d134-4207-b40b-683885698360
# DO NOT MODIFY THIS FILE

SESSION_TOKEN="b85492a6-d134-4207-b40b-683885698360"
SESSION_START=$(date +%s)
RESULTS_FILE="testing/legitimate_ab_test_sessions/results/session_b85492a6-d134-4207-b40b-683885698360.json"

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

Challenge: Performance Tracker - Advanced Integration
Description: Create a monitoring workflow that collects system metrics, analyzes performance data, and triggers alerts when needed. Implement enterprise-grade monitoring capabilities. Combine multiple processing patterns for maximum efficiency.

Requirements:
- Use appropriate Kailash SDK nodes for the task
- Implement proper error handling for external dependencies
- Include logging and monitoring capabilities
- Ensure data validation at input and output stages
- Support configurable parameters for different environments
- Implement retry logic for unreliable operations
- Include performance optimization for large data volumes
- Implement circuit breaker pattern for external services
- Support parallel processing where applicable
- Implement comprehensive audit logging
- Support dynamic workflow reconfiguration
- Include metrics collection and reporting
- Ensure enterprise-grade reliability patterns

Constraints:
- Use LocalRuntime for execution
- Maximum 20 nodes in the workflow
- Demonstrate enterprise architecture patterns
- Include both cycles and parallel processing

Please create a complete workflow that meets these requirements.
EOF

echo ""
echo "Press ENTER when ready to start..."
read

# Record session start
echo '{"session_token": "b85492a6-d134-4207-b40b-683885698360", "start_time": "'$(date -Iseconds)'", "challenge_id": "WF402"}' > "$RESULTS_FILE.tmp"

# Launch appropriate Claude Code environment

# BASELINE CONDITION - Standard Claude Code
echo "Launching Claude Code (standard environment)..."
# Command to launch Claude Code without MCP tools
# This would be the actual command to start Claude Code in baseline mode
echo "Please use standard Claude Code WITHOUT any MCP tools enabled"


echo ""
echo "When you have completed the challenge:"
echo "1. Save your final workflow code to: final_code_b85492a6-d134-4207-b40b-683885698360.py"
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
{
  "session_token": "b85492a6-d134-4207-b40b-683885698360",
  "challenge_id": "WF402",
  "start_time": "$(date -Iseconds -d @$SESSION_START)",
  "end_time": "$(date -Iseconds -d @$SESSION_END)",
  "duration_seconds": $DURATION,
  "debug_iterations": "$DEBUG_ITERATIONS",
  "successful": "$SUCCESS",
  "difficulty_rating": "$DIFFICULTY",
  "final_code_file": "final_code_b85492a6-d134-4207-b40b-683885698360.py"
}
EOF

echo ""
echo "📊 Results saved to: $RESULTS_FILE"
echo "Thank you for completing this session!"
