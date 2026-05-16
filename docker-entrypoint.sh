#!/bin/bash
set -e

echo "🚀 Starting AVI Content Safety System..."

# Initialize default API key if needed
echo "🔑 Initializing API key..."
python /app/scripts/init_default_api_key.py || echo "⚠️  API key initialization failed, continuing..."

# Execute the main command
echo "✅ Starting application server..."
exec "$@"
