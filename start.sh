#!/bin/bash

# Kill any existing processes on ports 8000 and 5173
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null

# Start Backend
echo "Starting Backend..."
python3 pacong/server.py &
BACKEND_PID=$!

# Wait for backend to be ready
sleep 2

# Start Frontend
echo "Starting Frontend..."
cd web_ui
npm run dev &
FRONTEND_PID=$!

# Handle shutdown
trap "kill $BACKEND_PID $FRONTEND_PID; exit" SIGINT SIGTERM

# Keep script running
wait
