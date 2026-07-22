from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from api.trajectory import router as trajectory_router
from api.ws_telemetry import broadcaster, camera_broadcaster, router as telemetry_router
from services.robot_client import RobotClient
from services.camera_client import CameraFrameClient

robot_telemetry_url = "ws://localhost:5000/telemetry/ws/robot"
camera_frames_url = "ws://localhost:5000/telemetry/ws/frames"
frontend_url = "http://localhost:5173"


app  = FastAPI()
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.get("/health")
def health():
    return {"status": "ok"}

@app.on_event("startup")
async def startup():
    # Robot telemetry (joints, pose, gripper)
    app.state.robot_client = RobotClient(robot_telemetry_url)
    app.state.robot_client.subscribe(broadcaster.on_sample)
    app.state.robot_client.start()

    # Camera frame stream (RGB JPEG only, forwarded to frontend)
    app.state.camera_client = CameraFrameClient(camera_frames_url)
    app.state.camera_client.subscribe(camera_broadcaster.on_frame)
    app.state.camera_client.start()

@app.on_event("shutdown")
async def shutdown():
    await app.state.camera_client.stop()
    await app.state.robot_client.stop()

api.include_router(trajectory_router)
api.include_router(telemetry_router)
app.include_router(api)
