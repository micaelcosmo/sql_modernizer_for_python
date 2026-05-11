from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ModernizeRequest(BaseModel):
    sql_code: str = Field(..., description="Código SQL da stored procedure legado a ser modernizado.")
    schema_context: Optional[str] = Field(default=None, description="Schema do banco de dados legado (opcional).")


class ModernizeResponse(BaseModel):
    status: str = Field(..., description="Status da execução do pipeline: sucesso, falha ou parcial.")
    generated_code: Optional[str] = Field(default=None, description="Código Python 3.14 gerado e validado.")
    report: Dict[str, Any] = Field(default_factory=dict, description="Relatório estruturado com os dados de cada nó do LangGraph.")