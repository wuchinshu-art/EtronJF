from fastapi import status


def test_health_check_endpoint(client):
    """驗證 GET /api/v1/health 能正常回傳 200 與資料庫 healthy 狀態"""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"]["status"] == "healthy"
    assert data["database"]["engine"] == "SQLite"
    assert "sqlite_version" in data["database"]
    assert "timestamp_utc" in data


def test_root_endpoint(client):
    """驗證 API 根端點可存取"""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert "health" in response.json()
