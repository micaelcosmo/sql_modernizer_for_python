from typing import Dict

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from graph.state import GraphState
from graph.workflow import app_graph
from schemas.schemas import ModernizeRequest, ModernizeResponse
from database.database import get_db, engine, Base
from database.models import ModernizationHistory


app = FastAPI(
    title="Modernization Pipeline API",
    description="API Gateway Híbrido para modernização de rotinas legadas via LangGraph.",
    version="1.0.0"
)


@app.on_event("startup")
async def startup():
    """
    Cria as tabelas no banco de dados se elas nao existirem ao iniciar a API.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Endpoint de verificação de integridade do serviço exigido pelo desafio.
    """
    return {"status": "ok"}


@app.post("/modernize", response_model=ModernizeResponse)
async def modernize_procedure(
    request: ModernizeRequest, 
    db: AsyncSession = Depends(get_db)
) -> ModernizeResponse:
    """
    Recebe a stored procedure, aciona o LangGraph e persiste o resultado no PostgreSQL.
    """
    initial_state: GraphState = {
        "sql_code": request.sql_code,
        "schema_context": request.schema_context,
        "parsed_ast": None,
        "semantic_markers": None,
        "generated_python": None,
        "report": {},
        "errors": [],
        "status": "iniciando"
    }

    try:
        # Execucao do Grafo
        final_state = app_graph.invoke(initial_state)
        
        # Persistencia Obrigatoria
        history_entry = ModernizationHistory(
            source_code=request.sql_code,
            generated_code=final_state.get("generated_python"),
            report=final_state.get("report", {}),
            status=final_state.get("status", "falha")
        )
        
        db.add(history_entry)
        await db.commit()

        return ModernizeResponse(
            status=final_state.get("status", "falha"),
            generated_code=final_state.get("generated_python"),
            report=final_state.get("report", {})
        )

    except Exception as e:
        # Garante que falhas criticas tambem sejam logadas
        error_history = ModernizationHistory(
            source_code=request.sql_code,
            report={"error": str(e)},
            status="falha"
        )
        db.add(error_history)
        await db.commit()
        
        raise HTTPException(status_code=500, detail=f"Erro na pipeline: {str(e)}")