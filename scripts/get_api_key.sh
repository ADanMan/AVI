#!/bin/bash
# Quick script to get or create an API key for AVI

set -e

echo "🔑 AVI API Key Helper"
echo "===================="
echo ""

# Check if we're inside Docker or outside
if [ -f "/app/data/.default_api_key" ]; then
    # Inside Docker container
    KEY_FILE="/app/data/.default_api_key"
    PYTHON_CMD="python"
else
    # Outside Docker - use docker exec
    KEY_FILE="data/.default_api_key"
    PYTHON_CMD="docker compose exec -T api python"
fi

# Try to get saved key
if [ -f "$KEY_FILE" ]; then
    KEY=$(cat "$KEY_FILE")
    echo "✅ Found saved API key:"
    echo ""
    echo "    $KEY"
    echo ""
    echo "Usage:"
    echo "  export AVI_API_KEY=$KEY"
    echo "  curl -H 'X-API-Key: \$AVI_API_KEY' http://localhost:8000/api/v1/health"
    echo ""
    exit 0
fi

# No saved key - offer to create one
echo "❌ No saved API key found."
echo ""
echo "Options:"
echo "  1. Create a new admin key interactively"
echo "  2. List existing keys (hash only)"
echo ""
read -p "Choose option (1-2): " choice

case $choice in
    1)
        echo "Creating new admin key..."
        if [ -f "/app/scripts/bootstrap_admin_key.py" ]; then
            # Inside Docker
            python /app/scripts/bootstrap_admin_key.py --name "Manual Key"
        else
            # Outside Docker
            docker compose exec api python scripts/bootstrap_admin_key.py --name "Manual Key"
        fi
        ;;
    2)
        echo "Listing existing keys..."
        if [ -f "/app/scripts/manage_api_keys.py" ]; then
            python /app/scripts/manage_api_keys.py list
        else
            docker compose exec api python scripts/manage_api_keys.py list
        fi
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac
