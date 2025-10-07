#!/bin/bash

# Casting Solidification Simulator - Startup Script
# This script starts both the backend and frontend servers

set -e  # Exit on error

echo "=========================================="
echo "Casting Solidification Simulator"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to kill processes on exit
cleanup() {
    echo ""
    echo "${YELLOW}Shutting down servers...${NC}"
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    echo "${GREEN}Shutdown complete${NC}"
}

trap cleanup EXIT INT TERM

# Check prerequisites
echo "Checking prerequisites..."

if ! command_exists python3; then
    echo "${RED}Error: Python 3 is not installed${NC}"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

if ! command_exists node; then
    echo "${RED}Error: Node.js is not installed${NC}"
    echo "Please install Node.js 16 or higher"
    exit 1
fi

if ! command_exists npm; then
    echo "${RED}Error: npm is not installed${NC}"
    echo "Please install npm"
    exit 1
fi

echo "${GREEN}✓ Prerequisites satisfied${NC}"
echo ""

# Setup backend
echo "Setting up backend..."
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if requirements are installed
if ! pip show Flask >/dev/null 2>&1; then
    echo "${YELLOW}Installing Python dependencies...${NC}"
    pip install -r requirements.txt
else
    echo "${GREEN}✓ Python dependencies already installed${NC}"
fi

# Start backend server
echo ""
echo "Starting backend server on port 5000..."
python app.py > ../backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

if ps -p $BACKEND_PID > /dev/null; then
    echo "${GREEN}✓ Backend server started (PID: $BACKEND_PID)${NC}"
else
    echo "${RED}Error: Backend server failed to start${NC}"
    echo "Check backend.log for details"
    exit 1
fi

cd ..

# Setup frontend
echo ""
echo "Setting up frontend..."
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "${YELLOW}Installing npm dependencies...${NC}"
    npm install
else
    echo "${GREEN}✓ npm dependencies already installed${NC}"
fi

# Start frontend server
echo ""
echo "Starting frontend development server on port 3000..."
BROWSER=none npm start > ../frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 3

if ps -p $FRONTEND_PID > /dev/null; then
    echo "${GREEN}✓ Frontend server started (PID: $FRONTEND_PID)${NC}"
else
    echo "${RED}Error: Frontend server failed to start${NC}"
    echo "Check frontend.log for details"
    exit 1
fi

cd ..

# Display access information
echo ""
echo "=========================================="
echo "${GREEN}Servers are running!${NC}"
echo "=========================================="
echo ""
echo "Frontend: http://localhost:3000"
echo "Backend:  http://localhost:5000"
echo ""
echo "Logs:"
echo "  Backend:  tail -f backend.log"
echo "  Frontend: tail -f frontend.log"
echo ""
echo "${YELLOW}Press Ctrl+C to stop all servers${NC}"
echo ""

# Wait for user interrupt
wait
