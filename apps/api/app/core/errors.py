import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FieldError(BaseModel):
    field: str
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    field_errors: Optional[List[FieldError]] = None


class StandardErrorResponse(BaseModel):
    error: ErrorDetail
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class AppException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        field_errors: Optional[List[FieldError]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field_errors = field_errors
        super().__init__(message)


AppError = AppException
