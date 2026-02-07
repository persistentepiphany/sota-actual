#!/bin/bash
# Start the Flare Butler API

echo "🚀 Starting SOTA Flare Butler API..."

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

echo "📦 Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt

echo "✅ Starting Flare Butler API server..."
python flare_butler_api.py
