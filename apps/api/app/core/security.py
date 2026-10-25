import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

# 初始化 Argon2id 密碼雜湊器 (Argon2id Password Hasher)
ph = PasswordHasher(
    time_cost=3,        # 迭代次數
    memory_cost=65536,  # 64 MiB
    parallelism=4,      # 4 並行線程
    hash_len=32,
    type=Type.ID,
)


def hash_password(password: str) -> str:
    """使用 Argon2id 對密碼進行雜湊"""
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """驗證明文密碼是否與 Argon2id 雜湊匹配"""
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_session_token() -> str:
    """產生 256 位元高熵不透明工作階段權杖 (High-entropy Opaque Session Token)"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """計算 Token 的 SHA-256 雜湊 (用於資料庫安全比對)"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    """產生 CSRF Token"""
    return secrets.token_hex(32)
