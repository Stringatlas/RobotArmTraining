from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware


app  = FastAPI()
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.get("/health")
def health():
    return {"status": "ok"}

app.include_router(api)