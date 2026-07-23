from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from api.trajectory import router as trajectory_router
from api.detect import router as detect_router
from api.yolo_server import router as yolo_server_router
from api.ws_telemetry import broadcaster, camera_broadcaster, router as telemetry_router
from services.telemetry.robot_client import RobotClient
from services.telemetry.camera_client import CameraFrameClient
from config import settings

app  = FastAPI()
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.camera_frames_url],
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    # Robot telemetry (joints, pose, gripper)
    app.state.robot_client = RobotClient(settings.robot_telemetry_url)
    app.state.robot_client.subscribe(broadcaster.on_sample)
    app.state.robot_client.start()

    # Camera frame stream (RGB JPEG only, forwarded to frontend)
    app.state.camera_client = CameraFrameClient(settings.camera_frames_url)
    app.state.camera_client.subscribe(camera_broadcaster.on_frame)
    app.state.camera_client.start()

@app.on_event("shutdown")
async def shutdown():
    await app.state.camera_client.stop()
    await app.state.robot_client.stop()

api.include_router(trajectory_router)
api.include_router(detect_router)
api.include_router(telemetry_router)
app.include_router(api)

# YOLO server endpoints (GET /image, POST /detections) — registered directly
# on app, NOT under /api, so the remote detection server can reach them.
app.include_router(yolo_server_router)
