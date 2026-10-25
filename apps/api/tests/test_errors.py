from fastapi import status
from app.core.errors import AppException, FieldError
from app.main import app


@app.get("/api/v1/test-app-exception")
def trigger_app_exception():
    raise AppException(
        code="UNAUTHORIZED_ACCESS",
        message="無權存取該公司資源",
        status_code=status.HTTP_403_FORBIDDEN,
        field_errors=[FieldError(field="company_id", message="無存取權限")],
    )


@app.get("/api/v1/test-unhandled-exception")
def trigger_unhandled_exception():
    raise RuntimeError("敏感內部連線字串不應外洩")


def test_standard_app_exception_response(client):
    """驗證業務自訂例外符合統一錯誤回應格式且無 traceback 洩漏"""
    response = client.get("/api/v1/test-app-exception")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "UNAUTHORIZED_ACCESS"
    assert data["error"]["message"] == "無權存取該公司資源"
    assert len(data["error"]["field_errors"]) == 1
    assert data["error"]["field_errors"][0]["field"] == "company_id"
    assert "request_id" in data


def test_unhandled_exception_sanitization(client):
    """驗證系統未預期錯誤會被遮罩，不洩露系統 Traceback 或敏感訊息"""
    response = client.get("/api/v1/test-unhandled-exception")
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    data = response.json()
    assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "敏感內部連線字串" not in data["error"]["message"]
    assert "request_id" in data
