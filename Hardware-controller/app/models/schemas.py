from typing import Any

from pydantic import BaseModel, Field

import config


class IgnoreExtraBaseModel(BaseModel):
    class Config:
        extra = "ignore"


class MessageResponse(BaseModel):
    status: str
    message: str
    data: Any | None = None


class LoginRequest(BaseModel):
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class ChannelPowerOverrideRequest(BaseModel):
    power: str | None = None


class BraggSetpointRequest(BaseModel):
    value_dbm: float


class BatchActionRequest(BaseModel):
    device_ids: list[str] = Field(default_factory=list)


class EdfaChannelPayload(IgnoreExtraBaseModel):
    key: str
    label: str | None = None
    power: str | None = None


class EdfaSchedulePayload(IgnoreExtraBaseModel):
    enabled: bool = False
    days: list[int] = Field(default_factory=lambda: list(config.DEFAULT_WEEKDAYS))
    on_time: str = "08:00"
    off_time: str = "18:00"


class EdfaDevicePayload(IgnoreExtraBaseModel):
    device_type: str = "network_edfa"
    name: str | None = None
    ip: str = ""
    serial_port: str = ""
    apc_setpoint_dbm: float = 33.0
    port: int = config.EDFA_DEFAULT_PORT
    timeout_sec: float = config.NETWORK_TIMEOUT_SEC
    command_delay_sec: float = config.EDFA_COMMAND_DELAY_SEC
    channels: list[EdfaChannelPayload] = Field(default_factory=list)
    schedule: EdfaSchedulePayload = Field(default_factory=EdfaSchedulePayload)
    notes: str = ""


class EdfaTemplateApplyRequest(IgnoreExtraBaseModel):
    device_ids: list[str] = Field(default_factory=list)
    channels: list[EdfaChannelPayload] = Field(default_factory=list)
    schedule: EdfaSchedulePayload | None = None


class PsuScheduleChannelPayload(IgnoreExtraBaseModel):
    enabled: bool = False
    days: list[int] = Field(default_factory=lambda: list(config.DEFAULT_WEEKDAYS))
    on_time: str = ""
    off_time: str = ""


class PsuSchedulePayload(IgnoreExtraBaseModel):
    channels: dict[str, PsuScheduleChannelPayload] = Field(default_factory=dict)


class PsuDevicePayload(IgnoreExtraBaseModel):
    name: str | None = None
    ip: str
    port: int = config.PSU_DEFAULT_PORT
    timeout_sec: float = config.NETWORK_TIMEOUT_SEC
    schedule: PsuSchedulePayload = Field(default_factory=PsuSchedulePayload)
    notes: str = ""


class LaserLockSystemPayload(IgnoreExtraBaseModel):
    name: str = "MIGA2 Laser Lock"
    ip: str
    port: int = config.LASER_LOCK_DEFAULT_PORT
    timeout_sec: float = config.NETWORK_TIMEOUT_SEC
    notes: str = ""
