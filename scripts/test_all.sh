#!/bin/bash

# Trae Bridge - Run All Tests
# Verifies the entire system from unit to E2E

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "============================================================"
echo "RUNNING ALL TRAE BRIDGE TESTS"
echo "============================================================"

# Function to run a test and check result
run_test() {
    local test_name=$1
    local test_cmd=$2
    
    echo -e "\n[Testing] ${test_name}..."
    if eval $test_cmd; then
        echo -e "${GREEN}✓ ${test_name} PASSED${NC}"
        return 0
    else
        echo -e "${RED}✗ ${test_name} FAILED${NC}"
        return 1
    fi
}

# 1. Integration Tests (No Trae required)
run_test "Integration Tests" "python3 scripts/test_integration.py" || exit 1

# 2. System Tests (Server startup)
run_test "System Tests" "python3 scripts/test_system.py" || exit 1

# Check if Trae is running before continuing
if ! curl -s http://localhost:9230/json/version > /dev/null; then
    echo -e "\n${RED}WARNING: Trae is not running on CDP port 9230.${NC}"
    echo "Skipping Bridge and E2E tests."
    echo "To run full tests, start Trae with: ./scripts/start_trae.sh"
    exit 0
fi

# 3. Bridge Tests (Requires Trae)
run_test "Bridge Logic Tests" "python3 scripts/test_bridge.py" || exit 1

# 4. E2E Tests (Requires Trae)
run_test "End-to-End Tests" "python3 scripts/test_e2e.py" || exit 1

echo -e "\n============================================================"
echo -e "${GREEN}ALL TESTS PASSED SUCCESSFULLY!${NC}"
echo "============================================================"
