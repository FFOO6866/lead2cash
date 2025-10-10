#!/bin/bash
# Automated Session Launcher - Token: a6936f32-17d4-424f-9740-e903e4c0642b
# DO NOT MODIFY THIS FILE

SESSION_TOKEN="a6936f32-17d4-424f-9740-e903e4c0642b"
SESSION_START=$(date +%s)
RESULTS_FILE="testing/legitimate_ab_test_sessions/results/session_a6936f32-17d4-424f-9740-e903e4c0642b.json"

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

Challenge: Content Scheduler with Parallel Processing
Description: Create a complex workflow system for automated processing and analysis. Optimize for concurrent processing of multiple data streams.

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

Constraints:
- Use LocalRuntime for execution
- Maximum 12 nodes in the workflow
- Include at least one cycle or parallel branch

Please create a complete workflow that meets these requirements.
EOF

echo ""
echo "Press ENTER when ready to start..."
read

# Record session start
echo '{"session_token": "a6936f32-17d4-424f-9740-e903e4c0642b", "start_time": "'$(date -Iseconds)'", "challenge_id": "WF302"}' > "$RESULTS_FILE.tmp"

# Launch appropriate Claude Code environment

# MCP-ENHANCED CONDITION - Claude Code with MCP Tools
echo "Launching Claude Code (enhanced environment)..."
# Command to launch Claude Code with MCP tools
# This would include the MCP configuration
echo "Please use Claude Code WITH the MCP Parameter Validation Tool enabled"
echo "MCP Config: ~/Library/Application Support/Claude/claude_desktop_config.json"


echo ""
echo "When you have completed the challenge:"
echo "1. Save your final workflow code to: final_code_a6936f32-17d4-424f-9740-e903e4c0642b.py"
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
  "session_token": "a6936f32-17d4-424f-9740-e903e4c0642b",
  "challenge_id": "WF302",
  "start_time": "$(date -Iseconds -d @$SESSION_START)",
  "end_time": "$(date -Iseconds -d @$SESSION_END)",
  "duration_seconds": $DURATION,
  "debug_iterations": "$DEBUG_ITERATIONS",
  "successful": "$SUCCESS",
  "difficulty_rating": "$DIFFICULTY",
  "final_code_file": "final_code_a6936f32-17d4-424f-9740-e903e4c0642b.py"
}
EOF

echo ""
echo "📊 Results saved to: $RESULTS_FILE"
echo "Thank you for completing this session!"
