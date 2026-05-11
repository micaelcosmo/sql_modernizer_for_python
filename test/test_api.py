import pytest
from fastapi.testclient import TestClient

from main_api import app


client = TestClient(app)


def test_health_check_status_ok():
    """
    Verifica se o endpoint de integridade responde com status 200
    e o payload esperado de status 'ok'.
    """
    response = client.get("/health")
    
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_modernize_endpoint_success():
    """
    Simula uma submissao valida de codigo SQL legado para garantir
    que os contratos Pydantic e a rota estao processando a entrada.
    """
    payload = {
        "sql_code": "SELECT * FROM clientes;",
        "schema_context": "CREATE TABLE clientes (id INT);"
    }
    
    response = client.post("/modernize", json=payload)
    data = response.json()
    
    assert response.status_code == 200
    assert data["status"] == "sucesso"
    assert "generated_code" in data
    assert "report" in data
    assert data["report"]["parsing"] == "pendente_implementacao"


def test_modernize_endpoint_validation_error_on_missing_sql():
    """
    Garante que a API rejeite requisicoes que nao contenham
    o campo obrigatorio 'sql_code', retornando erro 422 (Unprocessable Entity).
    """
    payload = {
        "schema_context": "CREATE TABLE clientes (id INT);"
    }
    
    response = client.post("/modernize", json=payload)
    
    assert response.status_code == 422
    assert "detail" in response.json()