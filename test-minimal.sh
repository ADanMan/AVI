#!/bin/bash
# Minimal test script - disables monitoring for faster testing
set -e

echo "🧪 Minimal AVI deployment test (without monitoring)"
echo "===================================================="
echo ""

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Clean up
echo -e "${YELLOW}Step 1: Cleaning up...${NC}"
docker compose down -v
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Step 2: Rebuild
echo -e "${YELLOW}Step 2: Rebuilding images...${NC}"
docker compose build api
echo -e "${GREEN}✓ Build complete${NC}"
echo ""

# Step 3: Start with monitoring disabled
echo -e "${YELLOW}Step 3: Starting minimal services...${NC}"
docker compose up -d redis qdrant
sleep 3

# Start API (OTEL will fail gracefully if jaeger not available)
docker compose up -d api
echo ""

# Wait for API
echo -e "${YELLOW}Step 4: Waiting for API to start...${NC}"
sleep 10

# Check logs for API key
echo -e "${YELLOW}Step 5: Checking for API key creation...${NC}"
echo "================================================================="
docker compose logs api 2>&1 | grep -A 20 "DEFAULT ADMIN API KEY" || echo -e "${YELLOW}Key not visible in logs (may already exist)${NC}"
echo "================================================================="
echo ""

# Get API key
echo -e "${YELLOW}Step 6: Retrieving API key...${NC}"
API_KEY=$(docker compose exec -T api cat /app/data/.default_api_key 2>/dev/null || echo "")

if [ -z "$API_KEY" ]; then
    echo -e "${RED}✗ API key not found${NC}"
    echo "Check logs: docker compose logs api"
    exit 1
else
    echo -e "${GREEN}✓ API key: ${API_KEY}${NC}"
    echo ""
fi

# Test health (always public, no auth required)
echo -e "${YELLOW}Step 7: Testing health endpoint...${NC}"
HEALTH=$(curl -s http://localhost:8000/api/v1/health || echo "ERROR")
if echo "$HEALTH" | grep -q "healthy\|ok"; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed${NC}"
    echo "Response: $HEALTH"
fi
echo ""

# Test with auth
echo -e "${YELLOW}Step 8: Testing authenticated request...${NC}"
AUTH_TEST=$(curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/health || echo "ERROR")
if echo "$AUTH_TEST" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Authenticated request successful${NC}"
else
    echo -e "${RED}✗ Authenticated request failed${NC}"
fi
echo ""

# Summary
echo "================================================================="
echo -e "${GREEN}✅ Minimal test complete${NC}"
echo "================================================================="
echo "API Key: $API_KEY"
echo ""
echo "Swagger UI: http://localhost:8000/docs"
echo ""
echo "To stop:"
echo "  docker compose down"
echo ""
echo "To clean up completely:"
echo "  docker compose down -v"
echo "================================================================="
