#!/bin/bash
# Setup script for VA/NVA Worker Activity Analysis System

set -e  # Exit on any error

echo "========================================="
echo "VA/NVA Analysis System - Setup"
echo "========================================="

# Check Python version
echo "✓ Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.9+"
    exit 1
fi
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "  Found Python $PYTHON_VERSION"

# Check Node version
echo "✓ Checking Node.js version..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 16+"
    exit 1
fi
NODE_VERSION=$(node --version)
echo "  Found Node.js $NODE_VERSION"

# Backend setup
echo ""
echo "=== Backend Setup ==="
cd backend

if [ ! -d "venv" ]; then
    echo "✓ Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "✓ Activating virtual environment..."
source venv/bin/activate

echo "✓ Installing Python dependencies..."
pip install -q -r requirements.txt

echo "✓ Initializing database..."
python3 -c "from app.db import init_db; init_db()"

cd ..

# Frontend setup
echo ""
echo "=== Frontend Setup ==="
cd frontend

echo "✓ Installing Node dependencies..."
npm install -q

cd ..

echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "========================================="
echo ""
echo "To run the system:"
echo "  1. ./run.sh  (for both services)"
echo ""
echo "Or manually:"
echo "  Terminal 1: cd backend && source venv/bin/activate && python3 -m uvicorn app.main:app --reload --port 8000"
echo "  Terminal 2: cd frontend && npm run dev"
echo ""
echo "Then open: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo ""
