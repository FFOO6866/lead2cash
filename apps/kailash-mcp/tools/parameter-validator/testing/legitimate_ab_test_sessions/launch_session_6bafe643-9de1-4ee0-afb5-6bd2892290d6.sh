#!/bin/bash
# Automated Session Launcher - Token: 6bafe643-9de1-4ee0-afb5-6bd2892290d6
# DO NOT MODIFY THIS FILE

SESSION_TOKEN="6bafe643-9de1-4ee0-afb5-6bd2892290d6"
SESSION_START=$(date +%s)
RESULTS_FILE="testing/legitimate_ab_test_sessions/results/session_6bafe643-9de1-4ee0-afb5-6bd2892290d6.json"

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

Challenge: Reorder Point Calculator with Parallel Processing
Description: Create a moderate workflow system for automated processing and analysis. Optimize for concurrent processing of multiple data streams.

Requirements:
- Use appropriate Kailash SDK nodes for the task
- Implement proper error handling for external dependencies
- Include logging and monitoring capabilities
- Ensure data validation at input and output stages
- Support configurable parameters for different environments
- Implement retry logic for unreliable operations

Constraints:
- Use LocalRuntime for execution
- Maximum 8 nodes in the workflow
- Use only standard Kailash SDK nodes

Please create a complete workflow that meets these requirements.
EOF

echo ""
echo "Press ENTER when ready to start..."
read

# Record session start
echo '{"session_token": "6bafe643-9de1-4ee0-afb5-6bd2892290d6", "start_time": "'$(date -Iseconds)'", "challenge_id": "WF202"}' > "$RESULTS_FILE.tmp"

# Launch appropriate Claude Code environment

# MCP-ENHANCED CONDITION - Claude Code with MCP Tools
echo "Launching Claude Code (enhanced environment)..."
# Command to launch Claude Code with MCP tools
# This would include the MCP configuration
echo "Please use Claude Code WITH the MCP Parameter Validation Tool enabled"
echo "MCP Config: ~/Library/Application Support/Claude/claude_desktop_config.json"


echo ""
echo "When you have completed the challenge:"
echo "1. Save your final workflow code to: final_code_6bafe643-9de1-4ee0-afb5-6bd2892290d6.py"
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
  "session_token": "6bafe643-9de1-4ee0-afb5-6bd2892290d6",
  "challenge_id": "WF202",
  "start_time": "$(date -Iseconds -d @$SESSION_START)",
  "end_time": "$(date -Iseconds -d @$SESSION_END)",
  "duration_seconds": $DURATION,
  "debug_iterations": "$DEBUG_ITERATIONS",
  "successful": "$SUCCESS",
  "difficulty_rating": "$DIFFICULTY",
  "final_code_file": "final_code_6bafe643-9de1-4ee0-afb5-6bd2892290d6.py"
}
EOF

echo ""
echo "📊 Results saved to: $RESULTS_FILE"
echo "Thank you for completing this session!"
