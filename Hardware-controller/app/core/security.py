import hashlib
import secrets

import config


def generate_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        config.PASSWORD_ITERATIONS,
    ).hex()


def build_password_record(password: str) -> dict:
    salt = generate_salt()
    return {
        "salt": salt,
        "hash": hash_password(password, salt),
        "iterations": config.PASSWORD_ITERATIONS,
    }


def verify_password(password: str, record: dict) -> bool:
    salt = str(record.get("salt") or "")
    stored_hash = str(record.get("hash") or "")
    if not salt or not stored_hash:
        return False
    calculated = hash_password(password, salt)
    return secrets.compare_digest(calculated, stored_hash)
