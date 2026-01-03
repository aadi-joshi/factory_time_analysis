#!/bin/bash
# Run script for VA/NVA Worker Activity Analysis System

set -e

echo "========================================="
echo "VA/NVA Analysis System - Starting"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Backend
echo -e "${YELLOW}Starting Backend (FastAPI)...${NC}"
cd backend
source venv/bin/activate
echo -e "${GREEN}✓ Backend ready at http://localhost:8000${NC}"
echo -e "${GREEN}✓ API docs at http://localhost:8000/docs${NC}"
python3 -m uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

sleep 2

# Frontend
echo ""
echo -e "${YELLOW}Starting Frontend (React/Vite)...${NC}"
cd ../frontend
echo -e "${GREEN}✓ Frontend ready at http://localhost:3000${NC}"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "========================================="
echo -e "${GREEN}✅ System Running!${NC}"
echo "========================================="
echo ""
echo "Browser: http://localhost:3000"
echo "API Docs: http://localhost:8000/docs"
echo "Database: backend/tracking.db"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Keep both processes running
wait $BACKEND_PID $FRONTEND_PID
