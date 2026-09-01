import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from app.api.routes import router


app = FastAPI(
    title="Agentic Learning Coach API",
    version="1.0.0",
)


DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
]

# Add your deployed frontend URL via env var, comma-separated if more than one,
# e.g. FRONTEND_ORIGINS=https://your-app.vercel.app
extra_origins = os.getenv("FRONTEND_ORIGINS", "")
ALLOWED_ORIGINS = DEFAULT_ORIGINS + [o.strip() for o in extra_origins.split(",") if o.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)


@app.get("/")
def root():
    return {
        "message": "Agentic Learning Coach API is running"
    }
