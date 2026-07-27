from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse

import config
from app.models.schemas import (
    BatchActionRequest,
    ChannelPowerOverrideRequest,
    EdfaDevicePayload,
    EdfaTemplateApplyRequest,
    LoginRequest,
    MessageResponse,
    PasswordChangeRequest,
    PsuDevicePayload,
)


router = APIRouter()


def _session_token(request: Request) -> str | None:
    return request.cookies.get(config.SESSION_COOKIE_NAME)


def _auth_manager(request: Request):
    return request.app.state.auth_manager


def _controller(request: Request):
    return request.app.state.controller_manager


def require_auth(request: Request):
    auth_manager = _auth_manager(request)
    if not auth_manager.validate_session(_session_token(request)):
        raise HTTPException(status_code=401, detail="Authentication required.")


def _ok(message: str, data=None):
    return MessageResponse(status="success", message=message, data=data)


def _model_to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _run_action(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/health")
def health():
    return {
        "status": "ok",
        "title": config.APP_TITLE,
        "version": config.APP_VERSION,
    }


@router.get("/auth/me")
def auth_me(request: Request):
    auth_manager = _auth_manager(request)
    return {"authenticated": auth_manager.validate_session(_session_token(request))}


@router.post("/auth/login", response_model=MessageResponse)
def login(payload: LoginRequest, request: Request, response: Response):
    auth_manager = _auth_manager(request)
    if not auth_manager.verify_login(payload.password):
        raise HTTPException(status_code=401, detail="Invalid password.")

    token = auth_manager.create_session()
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=config.SESSION_TTL_SEC,
        samesite="lax",
    )
    return _ok("Login successful.")


@router.post("/auth/logout", response_model=MessageResponse)
def logout(request: Request, response: Response):
    auth_manager = _auth_manager(request)
    auth_manager.clear_session(_session_token(request))
    response.delete_cookie(config.SESSION_COOKIE_NAME)
    return _ok("Logged out.")


@router.post("/auth/password", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def change_password(payload: PasswordChangeRequest, request: Request, response: Response):
    auth_manager = _auth_manager(request)
    try:
        auth_manager.change_password(payload.current_password, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    token = auth_manager.create_session()
    response.set_cookie(
        key=config.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=config.SESSION_TTL_SEC,
        samesite="lax",
    )
    controller = _controller(request)
    controller.publish_event("warning", "The web password was changed.", category="auth")
    return _ok("Password updated.")


@router.get("/api/overview", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def get_overview(request: Request):
    controller = _controller(request)
    return _ok("Overview loaded.", controller.get_public_state())


@router.get("/api/manual/download", dependencies=[Depends(require_auth)])
def download_manual():
    return FileResponse(
        path=config.LATEX_MANUAL_PATH,
        media_type="application/x-tex",
        filename=config.LATEX_MANUAL_PATH.name,
    )


@router.post("/api/edfa/devices", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def add_edfa_device(payload: EdfaDevicePayload, request: Request):
    controller = _controller(request)
    device = _run_action(controller.add_edfa_device, _model_to_dict(payload))
    return _ok("EDFA device added.", device)


@router.put("/api/edfa/devices/{device_id}", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def update_edfa_device(device_id: str, payload: EdfaDevicePayload, request: Request):
    controller = _controller(request)
    device = _run_action(controller.update_edfa_device, device_id, _model_to_dict(payload))
    return _ok("EDFA device updated.", device)


@router.delete("/api/edfa/devices/{device_id}", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def delete_edfa_device(device_id: str, request: Request):
    controller = _controller(request)
    _run_action(controller.delete_edfa_device, device_id)
    return _ok("EDFA device removed.")


@router.post("/api/edfa/devices/{device_id}/probe", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def probe_edfa_device(device_id: str, request: Request):
    controller = _controller(request)
    _run_action(controller.probe_edfa_device, device_id)
    return _ok("EDFA probe completed.")


@router.post("/api/edfa/devices/{device_id}/channels/{channel_key}/on", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def set_edfa_channel_on(device_id: str, channel_key: str, payload: ChannelPowerOverrideRequest, request: Request):
    controller = _controller(request)
    _run_action(controller.set_edfa_channel_on, device_id, channel_key, payload.power)
    return _ok(f"{channel_key} switched ON.")


@router.post("/api/edfa/devices/{device_id}/channels/{channel_key}/off", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def set_edfa_channel_off(device_id: str, channel_key: str, request: Request):
    controller = _controller(request)
    _run_action(controller.set_edfa_channel_off, device_id, channel_key)
    return _ok(f"{channel_key} switched OFF.")


@router.post("/api/edfa/devices/{device_id}/all/on", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def turn_edfa_device_on(device_id: str, request: Request):
    controller = _controller(request)
    _run_action(controller.turn_edfa_device_on, device_id)
    return _ok("All EDFA channels started.")


@router.post("/api/edfa/devices/{device_id}/all/off", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def turn_edfa_device_off(device_id: str, request: Request):
    controller = _controller(request)
    _run_action(controller.turn_edfa_device_off, device_id)
    return _ok("All EDFA channels shut down.")


@router.post("/api/edfa/batch/on", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def run_edfa_batch_on(payload: BatchActionRequest, request: Request):
    controller = _controller(request)
    _run_action(controller.run_edfa_batch, True, payload.device_ids)
    return _ok("Batch EDFA ON completed.")


@router.post("/api/edfa/batch/off", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def run_edfa_batch_off(payload: BatchActionRequest, request: Request):
    controller = _controller(request)
    _run_action(controller.run_edfa_batch, False, payload.device_ids)
    return _ok("Batch EDFA OFF completed.")


@router.post("/api/edfa/template/apply", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def apply_edfa_template(payload: EdfaTemplateApplyRequest, request: Request):
    controller = _controller(request)
    _run_action(controller.apply_edfa_template_to_all, _model_to_dict(payload))
    return _ok("EDFA template applied.")


@router.post("/api/psu/devices", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def add_psu_device(payload: PsuDevicePayload, request: Request):
    controller = _controller(request)
    device = _run_action(controller.add_psu_device, _model_to_dict(payload))
    return _ok("PSU device added.", device)


@router.put("/api/psu/devices/{device_id}", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def update_psu_device(device_id: str, payload: PsuDevicePayload, request: Request):
    controller = _controller(request)
    device = _run_action(controller.update_psu_device, device_id, _model_to_dict(payload))
    return _ok("PSU device updated.", device)


@router.delete("/api/psu/devices/{device_id}", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def delete_psu_device(device_id: str, request: Request):
    controller = _controller(request)
    _run_action(controller.delete_psu_device, device_id)
    return _ok("PSU device removed.")


@router.post("/api/psu/devices/{device_id}/probe", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def probe_psu_device(device_id: str, request: Request):
    controller = _controller(request)
    _run_action(controller.probe_psu_device, device_id)
    return _ok("PSU probe completed.")


@router.post("/api/psu/devices/{device_id}/disconnect", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def disconnect_psu_device(device_id: str, request: Request):
    controller = _controller(request)
    _run_action(controller.disconnect_psu_device, device_id)
    return _ok("PSU session closed.")


@router.post("/api/psu/devices/{device_id}/refresh", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def refresh_psu_device(device_id: str, request: Request):
    controller = _controller(request)
    _run_action(controller.refresh_psu_device, device_id)
    return _ok("PSU state refreshed.")


@router.post("/api/psu/devices/{device_id}/independent-mode", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def set_psu_independent_mode(device_id: str, request: Request):
    controller = _controller(request)
    _run_action(controller.set_psu_independent_mode, device_id)
    return _ok("PSU independent mode applied.")


@router.post("/api/psu/devices/{device_id}/channels/{channel}/on", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def set_psu_channel_on(device_id: str, channel: int, request: Request):
    controller = _controller(request)
    _run_action(controller.set_psu_channel_output, device_id, channel, True)
    return _ok(f"PSU channel {channel} switched ON.")


@router.post("/api/psu/devices/{device_id}/channels/{channel}/off", response_model=MessageResponse, dependencies=[Depends(require_auth)])
def set_psu_channel_off(device_id: str, channel: int, request: Request):
    controller = _controller(request)
    _run_action(controller.set_psu_channel_output, device_id, channel, False)
    return _ok(f"PSU channel {channel} switched OFF.")
