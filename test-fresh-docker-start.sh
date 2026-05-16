#!/bin/bash
# Test script for fresh Docker deployment
# This simulates what a new user would experience

set -e

echo "🧪 Testing fresh AVI deployment with automatic API key generation"
echo "================================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Stop and clean everything
echo -e "${YELLOW}Step 1: Cleaning up existing containers and volumes...${NC}"
docker compose down -v
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Step 2: Rebuild images with new changes
echo -e "${YELLOW}Step 2: Rebuilding Docker images with new changes...${NC}"
docker compose build api
echo -e "${GREEN}✓ Build complete${NC}"
echo ""

# Step 3: Start services
echo -e "${YELLOW}Step 3: Starting services...${NC}"
# Start minimal services for testing (including jaeger to avoid connection errors)
docker compose up -d redis qdrant jaeger mlflow
echo "Waiting for dependencies to be ready..."
sleep 5
docker compose up -d api
echo ""

# Wait for API to be ready
echo -e "${YELLOW}Step 4: Waiting for API to start...${NC}"
sleep 10

# Step 5: Check logs for API key creation
echo -e "${YELLOW}Step 5: Checking logs for default API key creation...${NC}"
echo "================================================================="
docker compose logs api | grep -A 20 "DEFAULT ADMIN API KEY" || echo -e "${YELLOW}Key not found in current logs, may have been created earlier${NC}"
echo "================================================================="
echo ""

# Step 6: Retrieve the API key
echo -e "${YELLOW}Step 6: Retrieving the default API key...${NC}"
API_KEY=$(docker compose exec -T api cat /app/data/.default_api_key 2>/dev/null || echo "")

if [ -z "$API_KEY" ]; then
    echo -e "${RED}✗ API key file not found!${NC}"
    echo "This might mean:"
    echo "  1. The initialization script didn't run"
    echo "  2. An admin key already existed"
    echo "  3. The container hasn't fully started yet"
    echo ""
    echo "Check the container logs:"
    echo "  docker compose logs api"
    exit 1
else
    echo -e "${GREEN}✓ API key retrieved: ${API_KEY}${NC}"
    echo ""
fi

# Step 7: Test health (always public, no auth required)
echo -e "${YELLOW}Step 7: Testing health endpoint (no auth)...${NC}"
HEALTH_RESPONSE=$(curl -s http://localhost:8000/api/v1/health || echo "ERROR")
if echo "$HEALTH_RESPONSE" | grep -q "healthy\|ok"; then
    echo -e "${GREEN}✓ Health check passed${NC}"
    echo "Response: $HEALTH_RESPONSE"
else
    echo -e "${RED}✗ Health check failed${NC}"
    echo "Response: $HEALTH_RESPONSE"
fi
echo ""

# Step 8: Test authenticated endpoint (like /query) with API key
echo -e "${YELLOW}Step 8: Testing authenticated endpoint with API key...${NC}"
AUTH_RESPONSE=$(curl -s -H "X-API-Key: $API_KEY" http://localhost:8000/api/v1/health || echo "ERROR")
if echo "$AUTH_RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Authenticated request successful!${NC}"
    echo "Response: $AUTH_RESPONSE"
else
    echo -e "${RED}✗ Authenticated request failed${NC}"
    echo "Response: $AUTH_RESPONSE"
fi
echo ""

# Step 9: Test Swagger UI access
echo -e "${YELLOW}Step 9: Check Swagger UI availability...${NC}"
SWAGGER_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)
if [ "$SWAGGER_RESPONSE" = "200" ]; then
    echo -e "${GREEN}✓ Swagger UI is accessible at http://localhost:8000/docs${NC}"
else
    echo -e "${RED}✗ Swagger UI returned HTTP $SWAGGER_RESPONSE${NC}"
fi
echo ""

# Summary
echo "================================================================="
echo -e "${GREEN}🎉 Test Summary${NC}"
echo "================================================================="
echo "Default API Key: $API_KEY"
echo ""
echo "Next steps:"
echo "  1. Open Swagger UI: http://localhost:8000/docs"
echo "  2. Click 'Authorize' and enter the API key above"
echo "  3. Try making API calls!"
echo ""
echo "To see all logs:"
echo "  docker compose logs -f api"
echo ""
echo "To stop services:"
echo "  docker compose down"
echo ""
echo "To completely clean up:"
echo "  docker compose down -v"
echo "================================================================="
