# RobotArmTraining

A three-tier system for robot arm training with real-time telemetry relay and trajectory generation.

## Quick Start

### Prerequisites
- Python 3.8+ (backend)
- Node.js 18+ (frontend)
- Robot service running on port 5000

### Running the Backend

```bash
cd backend
pip install .
uvicorn main:app --reload --port 8000
```

The backend will automatically connect to the robot telemetry service at `ws://localhost:5000/telemetry/ws` on startup.

### Running the Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` and proxies API requests to the backend.

### Connecting to Robot Client

Ensure your robot service is running and exposing a WebSocket endpoint at `ws://localhost:5000/telemetry/ws`. The backend's `RobotClient` will maintain a persistent connection to this endpoint and relay telemetry data to the frontend [3](#0-2) .

## Architecture

- **Backend**: FastAPI server on port 8000, handles trajectory generation and telemetry relay
- **Frontend**: SvelteKit application on port 5173, provides 3D visualization and control interface  
- **Robot Service**: External service on port 5000, provides real-time telemetry stream

The frontend connects to the backend via WebSocket at `/api/telemetry/ws` for live robot state updates.
```
