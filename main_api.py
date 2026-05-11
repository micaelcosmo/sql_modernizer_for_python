from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from graph.state import GraphState
from graph.workflow import app_graph
from schemas.schemas import ModernizeRequest, ModernizeResponse
from database.database import get_db, engine, Base
from database.models import ModernizationHistory


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicia o banco de dados e garante a limpeza de conexoes no Windows."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="Modernizer Pipeline",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Rota de integridade para validacao do desafio."""
    return {"status": "ok"}


@app.post("/modernize", response_model=ModernizeResponse)
async def modernize_procedure(
    request: ModernizeRequest, 
    db: AsyncSession = Depends(get_db)
) -> ModernizeResponse:
    """Orquestra a modernizacao e garante a propagacao de erros do Grafo."""
    state: GraphState = {
        "sql_code": request.sql_code,
        "schema_context": request.schema_context,
        "report": {},
        "errors": [],
        "status": "iniciando"
    }

    try:
        # Chamada assincrona nativa para estabilidade
        final_state = await app_graph.ainvoke(state)
        
        # Consolida o relatorio injetando os erros capturados nos nos
        report_final = final_state.get("report", {})
        if final_state.get("errors"):
            report_final["detalhes_erro"] = final_state.get("errors")

        history = ModernizationHistory(
            source_code=request.sql_code,
            generated_code=final_state.get("generated_python"),
            report=report_final,
            status=final_state.get("status", "falha")
        )
        
        db.add(history)
        await db.commit()

        # Mapeamento explicito para evitar 'None' no Pydantic
        return ModernizeResponse(
            status=final_state.get("status", "falha"),
            generated_code=final_state.get("generated_python") or "",
            report=report_final
        )

    except Exception as e:
        await db.rollback()
        # Fallback de seguranca para o endpoint nao retornar 500 puro
        return ModernizeResponse(
            status="falha",
            generated_code="",
            report={"erro_critico": str(e)}
        )
    finally:
        await db.close()