from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.analytics import router as analytics_router
from app.api.bambu import router as bambu_router
from app.api.calibrations import router as calibrations_router
from app.api.health import router as health_router
from app.api.gcode_uploads import router as gcode_uploads_router
from app.api.manufacturers import router as manufacturers_router
from app.api.materials import router as materials_router
from app.api.prints import router as prints_router
from app.api.reconciliation import router as reconciliation_router
from app.api.spools import router as spools_router
from app.api.tare_profiles import router as tare_profiles_router
from app.integrations.bambu.service import BambuIntegration


@asynccontextmanager
async def lifespan(application: FastAPI):
    bambu_integration = BambuIntegration()
    application.state.bambu_integration = bambu_integration
    bambu_integration.start()
    try:
        yield
    finally:
        bambu_integration.stop()


app = FastAPI(
    title="Filament Command Center API",
    version="0.1.0",
    lifespan=lifespan,
)

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
app.include_router(analytics_router, prefix="/api")
app.include_router(bambu_router, prefix="/api")
app.include_router(calibrations_router, prefix="/api")
app.include_router(gcode_uploads_router, prefix="/api")
app.include_router(manufacturers_router, prefix="/api")
app.include_router(materials_router, prefix="/api")
app.include_router(prints_router, prefix="/api")
app.include_router(reconciliation_router, prefix="/api")
app.include_router(spools_router, prefix="/api")
app.include_router(tare_profiles_router, prefix="/api")
