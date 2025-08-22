#!/bin/bash

# Development startup script for Jenkins AI Agent Service

set -e

echo "🚀 Starting Jenkins AI Agent Service in Development Mode"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "📋 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please configure .env file with your actual values before running again"
    exit 1
fi

# Source environment variables
source .env

# Check required environment variables
required_vars=("CLAUDE_API_KEY" "DATABASE_URL" "REDIS_URL" "SECRET_KEY")
missing_vars=()

for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "❌ Missing required environment variables:"
    printf '   %s\n' "${missing_vars[@]}"
    echo "Please set these variables in your .env file"
    exit 1
fi

echo "✅ Environment variables checked"

# Check if MCP server is running
if command -v curl >/dev/null 2>&1; then
    echo "🔗 Checking MCP server connectivity..."
    if curl -s --connect-timeout 5 "${MCP_SERVER_URL}/health" >/dev/null; then
        echo "✅ MCP server is reachable at ${MCP_SERVER_URL}"
    else
        echo "⚠️  Warning: MCP server not reachable at ${MCP_SERVER_URL}"
        echo "   Some features may not work properly"
    fi
else
    echo "⚠️  curl not found, skipping MCP server check"
fi

# Start infrastructure services
echo "🐳 Starting infrastructure services (Redis & PostgreSQL)..."
docker-compose up -d redis postgres

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
max_attempts=30
attempt=0

while [ $attempt -lt $max_attempts ]; do
    if docker-compose ps redis postgres | grep -q "healthy"; then
        echo "✅ Infrastructure services are ready"
        break
    fi
    
    attempt=$((attempt + 1))
    echo "   Waiting... (attempt $attempt/$max_attempts)"
    sleep 2
done

if [ $attempt -eq $max_attempts ]; then
    echo "❌ Infrastructure services failed to start"
    docker-compose logs redis postgres
    exit 1
fi

# Install Python dependencies if needed
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "📦 Installing/updating Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations/initialization
echo "🗄️  Initializing database schema..."
python -c "
import asyncio
import asyncpg
import os
from app.config import get_settings

async def init_db():
    settings = get_settings()
    try:
        conn = await asyncpg.connect(settings.database_url)
        
        # Read and execute init.sql
        with open('init.sql', 'r') as f:
            await conn.execute(f.read())
        
        print('✅ Database schema initialized')
        await conn.close()
    except Exception as e:
        print(f'❌ Database initialization failed: {e}')
        exit(1)

asyncio.run(init_db())
"

# Test Redis connection
echo "🔧 Testing Redis connection..."
python -c "
import redis
import os
from urllib.parse import urlparse

redis_url = os.getenv('REDIS_URL')
parsed = urlparse(redis_url)

try:
    r = redis.Redis(
        host=parsed.hostname,
        port=parsed.port or 6379,
        password=parsed.password,
        db=int(parsed.path[1:]) if parsed.path and len(parsed.path) > 1 else 0,
        decode_responses=True
    )
    r.ping()
    print('✅ Redis connection successful')
except Exception as e:
    print(f'❌ Redis connection failed: {e}')
    exit(1)
"

# Start the AI Agent service
echo "🤖 Starting AI Agent service..."
echo "   Access the service at: http://localhost:8000"
echo "   API documentation at: http://localhost:8000/docs"
echo "   Health check at: http://localhost:8000/health"
echo ""
echo "📊 Monitoring (if enabled):"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana: http://localhost:3000 (admin/admin)"
echo ""
echo "🛑 Press Ctrl+C to stop the service"
echo ""

# Start the application with hot reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level info