import secrets
import time

import config
from app.core.security import build_password_record, verify_password
from app.core.state_store import StateStore


class AuthManager:
    def __init__(self, state_store: StateStore):
        self.state_store = state_store
        self.sessions: dict[str, float] = {}

    def _cleanup(self):
        now = time.time()
        expired = [token for token, expiry in self.sessions.items() if expiry <= now]
        for token in expired:
            self.sessions.pop(token, None)

    def verify_login(self, password: str) -> bool:
        state = self.state_store.get_state()
        return verify_password(password, state["auth"])

    def create_session(self) -> str:
        self._cleanup()
        token = secrets.token_urlsafe(32)
        self.sessions[token] = time.time() + config.SESSION_TTL_SEC
        return token

    def validate_session(self, token: str | None) -> bool:
        self._cleanup()
        if not token:
            return False
        expiry = self.sessions.get(token)
        if not expiry:
            return False
        if expiry <= time.time():
            self.sessions.pop(token, None)
            return False
        self.sessions[token] = time.time() + config.SESSION_TTL_SEC
        return True

    def clear_session(self, token: str | None):
        if not token:
            return
        self.sessions.pop(token, None)

    def clear_all_sessions(self):
        self.sessions.clear()

    def change_password(self, current_password: str, new_password: str) -> None:
        if not self.verify_login(current_password):
            raise ValueError("Current password is incorrect.")
        if len(new_password.strip()) < 4:
            raise ValueError("New password must contain at least 4 characters.")
        self.state_store.replace_auth_record(build_password_record(new_password.strip()))
        self.clear_all_sessions()
