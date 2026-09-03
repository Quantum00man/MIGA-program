"""Run with: python -m uvicorn tgf_controller.app:app --host 0.0.0.0 --port 8005"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Path as ApiPath, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import ChannelSettings, ConnectionSettings, OutputRequest
from .service import Controller
from .transport import InstrumentError

ChannelId = Annotated[int, ApiPath(ge=1, le=2)]


def create_app(controller=None):
    control = controller if controller is not None else Controller()

    @asynccontextmanager
    async def lifespan(app):
        yield
        control.disconnect()

    app = FastAPI(title="TGF3162 Controller", version="0.1.0", lifespan=lifespan,
        description="Two independent sine channels over LAN. All hardware channel values are last accepted commands, not readback. Run one server worker.")
    app.state.controller = control

    @app.exception_handler(InstrumentError)
    async def instrument_error(request: Request, exc: InstrumentError):
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    @app.get("/api/state")
    def state():
        return control.state()

    @app.put("/api/connection")
    def configure(settings: ConnectionSettings):
        return control.save(settings)

    @app.post("/api/connection/test")
    def test(settings: ConnectionSettings):
        """Identity-only test. Does not save settings or enable outputs."""
        return control.test(settings)

    @app.post("/api/connect")
    def connect():
        return control.connect()

    @app.post("/api/disconnect")
    def disconnect():
        """Close the connection. Does not switch off hardware outputs."""
        return control.disconnect()

    @app.post("/api/refresh")
    def refresh():
        return control.refresh()

    @app.put("/api/channels/{channel}/settings")
    def apply(channel: ChannelId, settings: ChannelSettings):
        """Apply a complete sine configuration without changing the output enable state."""
        return control.apply(channel, settings)

    @app.put("/api/channels/{channel}/output")
    def output(channel: ChannelId, request: OutputRequest):
        return control.output(channel, request.enabled)

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(static / "index.html")

    return app


app = create_app()
