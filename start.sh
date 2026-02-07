#!/bin/bash
#
# SOTA - Start All Services
# Starts backend (port 3001) and frontend (port 3000)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_DIR="$SCRIPT_DIR/agents"
FRONTEND_DIR="$SCRIPT_DIR/mobile_frontend"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         SOTA - Starting Services       ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
echo ""

# Kill existing processes on ports 3000 and 3001
echo -e "${YELLOW}🧹 Cleaning up existing processes...${NC}"
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3001 2>/dev/null | xargs kill -9 2>/dev/null || true
pkill -f "flare_butler_api.py" 2>/dev/null || true
sleep 1

# Check if .env exists
if [ ! -f "$AGENTS_DIR/.env" ]; then
    echo -e "${RED}❌ Missing $AGENTS_DIR/.env${NC}"
    echo "   Copy .env.example and fill in your keys"
    exit 1
fi

# Start Backend
echo -e "${GREEN}🚀 Starting Backend (FastAPI on port 3001)...${NC}"
cd "$AGENTS_DIR"
python3 flare_butler_api.py > /tmp/sota_backend.log 2>&1 &
BACKEND_PID=$!
echo "   PID: $BACKEND_PID"
echo "   Logs: /tmp/sota_backend.log"

# Wait for backend to be ready
echo -e "${YELLOW}   Waiting for backend to start...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:3001/ > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Backend ready!${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}   ❌ Backend failed to start. Check logs:${NC}"
        tail -20 /tmp/sota_backend.log
        exit 1
    fi
    sleep 1
done

# Start Frontend
echo -e "${GREEN}🌐 Starting Frontend (Next.js on port 3000)...${NC}"
cd "$FRONTEND_DIR"
npx next dev > /tmp/sota_frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   PID: $FRONTEND_PID"
echo "   Logs: /tmp/sota_frontend.log"

# Wait for frontend to be ready
echo -e "${YELLOW}   Waiting for frontend to start...${NC}"
for i in {1..60}; do
    if curl -s http://localhost:3000/ > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Frontend ready!${NC}"
        break
    fi
    if [ $i -eq 60 ]; then
        echo -e "${RED}   ❌ Frontend failed to start. Check logs:${NC}"
        tail -20 /tmp/sota_frontend.log
        exit 1
    fi
    sleep 1
done

echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          All Services Running!         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BLUE}Frontend:${NC}  http://localhost:3000"
echo -e "  ${BLUE}Backend:${NC}   http://localhost:3001"
echo ""
echo -e "  ${YELLOW}Logs:${NC}"
echo -e "    Backend:  tail -f /tmp/sota_backend.log"
echo -e "    Frontend: tail -f /tmp/sota_frontend.log"
echo ""
echo -e "  ${YELLOW}Stop all:${NC} pkill -f 'flare_butler_api|next dev'"
echo ""

# Function to handle cleanup
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✅ All services stopped${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Show combined logs
echo -e "${BLUE}📋 Showing combined logs (Ctrl+C to stop all)...${NC}"
echo ""
tail -f /tmp/sota_backend.log /tmp/sota_frontend.log
