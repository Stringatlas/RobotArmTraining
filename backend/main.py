import logging

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from api.trajectory import router as trajectory_router
from api.detect import router as detect_router
from api.ws_telemetry import broadcaster, camera_broadcaster, router as telemetry_router
from api.episode_recorder import router as episode_recorder_router
from services.telemetry.robot_client import RobotClient
from services.telemetry.camera_client import CameraFrameClient
from services.object_detection.detector import detector as dino_detector
from config import settings

logger = logging.getLogger(__name__)

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
    # Load Grounding DINO model (local zero-shot detection)
    logger.info("Loading Grounding DINO model...")
    dino_detector.load()
    logger.info("Grounding DINO model loaded.")

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
api.include_router(episode_recorder_router)
app.include_router(api)
