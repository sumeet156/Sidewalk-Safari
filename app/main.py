import logging
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.generator import generate_pack
from app.providers.ollama import create_provider
from app.validator import MissionPack, PackRequest

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
app = FastAPI(title="Sidewalk Safari", version="0.1.0")
provider = create_provider()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/generate", response_model=MissionPack)
def generate(request: PackRequest) -> MissionPack:
    return generate_pack(request, provider).pack


static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
