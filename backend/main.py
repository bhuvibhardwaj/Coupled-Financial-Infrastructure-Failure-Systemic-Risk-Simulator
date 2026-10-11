"""FastAPI application: authentication, network management, and simulations."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pg8000.dbapi import InterfaceError

from backend.auth import router as auth_router
from backend.network_api import router as network_router
from backend.runs import router as runs_router

app = FastAPI(title="Systemic Risk Simulator API")
app.include_router(auth_router)
app.include_router(network_router)
app.include_router(runs_router)


@app.exception_handler(InterfaceError)
async def database_unavailable(request: Request, exc: InterfaceError):
    return JSONResponse(status_code=503, content={"detail": "PostgreSQL is unavailable"})


@app.get("/api/health")
def health():
    return {"ok": True}
