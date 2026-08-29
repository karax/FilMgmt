from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.locations import router as locations_router
from app.api.manufacturers import router as manufacturers_router
from app.api.materials import router as materials_router
from app.api.spools import router as spools_router

app = FastAPI(title="Filament Command Center API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_methods=["GET"],
    allow_headers=["Accept", "Content-Type"],
)

app.include_router(health_router, prefix="/api")
app.include_router(locations_router, prefix="/api")
app.include_router(manufacturers_router, prefix="/api")
app.include_router(materials_router, prefix="/api")
app.include_router(spools_router, prefix="/api")
