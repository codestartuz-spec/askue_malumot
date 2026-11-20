from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .init_db import init_db
from .routers import (audit, auth, brigades, drill, dynamics, home, map as map_router, meta, posts, republic, reports, system,
                      telegram, uploads, users)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    try:
        republic.upgrade_stored()
    except Exception:  # noqa: BLE001
        pass
    yield


app = FastAPI(title="ASKUE ma'lumot", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(GZipMiddleware, minimum_size=800)
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth, users, meta, dynamics, drill, brigades, uploads, audit, map_router, telegram, reports, republic, system, posts, home):
    app.include_router(r.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}


dist = settings.frontend_dist
if (dist / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "Topilmadi"}, status_code=404)
        f = (dist / path).resolve()
        if path and f.is_file() and dist in f.parents:
            return FileResponse(f)
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
