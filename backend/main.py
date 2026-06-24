"""
main.py — FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from database import lifespan
from routers.products import router as products_router

app = FastAPI(
    title="Product Catalog API",
    description=(
        "Browse 200,000 products with stable cursor-based (keyset) pagination. "
        "Inserting or updating products while a client is browsing will never "
        "cause duplicate or skipped rows."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — allow the bundled frontend and local dev servers
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
app.include_router(products_router, prefix="/api", tags=["Products"])


@app.get("/api/health", tags=["Health"])
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Serve the frontend (if the /static directory exists inside the container)
# ---------------------------------------------------------------------------
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(os.path.join(_static_dir, "index.html"))
