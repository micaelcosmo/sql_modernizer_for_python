import httpx
import pytest

# URL padrao do Uvicorn
BASE_URL = "http://127.0.0.1:8000"


def test_health_check_status_ok():
    """Verifica se o servidor real responde ao health check."""
    response = httpx.get(f"{BASE_URL}/health")
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_modernize_endpoint_success():
    """Valida o contrato de sucesso enviando um SQL para o servidor rodando."""
    payload = {
        "sql_code": "CREATE FUNCTION teste() RETURNS VOID AS $$ BEGIN END; $$ LANGUAGE plpgsql;",
        "schema_context": ""
    }
    
    response = httpx.post(f"{BASE_URL}/modernize", json=payload, timeout=60.0)
    data = response.json()
    
    assert response.status_code == 200, f"Erro na API: {data}"
    assert data["status"] == "sucesso"
    assert "generated_code" in data


def test_modernize_endpoint_validation_error_on_missing_sql():
    """Garante que o Pydantic da API rejeite campos ausentes."""
    payload = {"schema_context": "..."}
    
    response = httpx.post(f"{BASE_URL}/modernize", json=payload)
    
    assert response.status_code == 422