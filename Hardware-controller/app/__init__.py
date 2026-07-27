import asyncio
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import config
from app.api.routes import router
from app.core.auth import AuthManager
from app.core.controller_manager import ControllerManager
from app.core.state_store import StateStore


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for websocket in self.active_connections:
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)


def create_app() -> FastAPI:
    app = FastAPI(title=config.APP_TITLE, version=config.APP_VERSION)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    ws_manager = ConnectionManager()
    state_store = StateStore()
    auth_manager = AuthManager(state_store)
    controller_manager = ControllerManager(state_store)
    app.state.ws_manager = ws_manager
    app.state.auth_manager = auth_manager
    app.state.controller_manager = controller_manager

    event_loop_ref = {"loop": None}

    def _is_authenticated(request: Request) -> bool:
        token = request.cookies.get(config.SESSION_COOKIE_NAME)
        return auth_manager.validate_session(token)

    def _bridge_event(message: dict):
        loop = event_loop_ref["loop"]
        if loop and ws_manager.active_connections:
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(message), loop)

    @app.on_event("startup")
    async def _startup():
        event_loop_ref["loop"] = asyncio.get_running_loop()
        controller_manager.set_event_callback(_bridge_event)
        controller_manager.start()

    @app.on_event("shutdown")
    async def _shutdown():
        controller_manager.stop()

    @app.get("/login")
    async def login_page(request: Request):
        if _is_authenticated(request):
            return RedirectResponse(url="/", status_code=302)
        return FileResponse(config.STATIC_DIR / "login.html")

    @app.get("/")
    async def index_page(request: Request):
        if not _is_authenticated(request):
            return RedirectResponse(url="/login", status_code=302)
        return FileResponse(config.STATIC_DIR / "index.html")

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        token = websocket.cookies.get(config.SESSION_COOKIE_NAME)
        if not auth_manager.validate_session(token):
            await websocket.close(code=1008)
            return

        await ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
        except Exception:
            ws_manager.disconnect(websocket)

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=str(Path(config.STATIC_DIR))), name="static")
    return app
