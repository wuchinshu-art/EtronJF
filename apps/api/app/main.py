import uuid
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import AppException, StandardErrorResponse, ErrorDetail, FieldError
from app.api.v1.router import api_v1_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 同源與 CORS 策略 (CORS & Same-origin Policy)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """應用程式自訂例外處理 (Application Custom Exception Handler)"""
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    response_data = StandardErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            field_errors=exc.field_errors,
        ),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=response_data.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """輸入驗證例外處理 (Validation Exception Handler)"""
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    field_errors = []
    for err in exc.errors():
        loc = ".".join(str(l) for l in err.get("loc", []))
        field_errors.append(FieldError(field=loc, message=err.get("msg", "驗證錯誤")))

    response_data = StandardErrorResponse(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="請求輸入資料驗證失敗",
            field_errors=field_errors,
        ),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response_data.model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """未預期內部錯誤防護 (Internal Server Error Handler - 防止洩漏 Traceback)"""
    import traceback
    traceback.print_exc()
    request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
    response_data = StandardErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="系統內部發生未預期錯誤，請聯絡系統管理員",
        ),
        request_id=request_id,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_data.model_dump(),
    )


# 掛載 API v1 路由
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "health": f"{settings.API_V1_STR}/health",
    }
