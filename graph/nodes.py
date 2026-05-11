import ast
import os
import httpx
from typing import Any, Dict, Set

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pglast import parser
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from graph.state import GraphState


load_dotenv()


class ModernizedCode(BaseModel):
    """Contrato de saida estruturada para o LLM via OpenRouter."""
    codigo_python: str = Field(description="O codigo Python 3.14 gerado.")
    justificativa_arquitetural: str = Field(description="Explicacao tecnica.")
    dependencias: list[str] = Field(description="Bibliotecas necessarias.")


def _traverse_and_extract(node: Any, markers: Dict[str, Set[str]]) -> None:
    """Detecta complexidades como cursores e recursividade para o prompt."""
    if isinstance(node, dict):
        if "withClause" in node and node.get("withClause", {}).get("recursive"):
            markers["risks"].add("CTE_RECURSIVA")
        if "DeclareCursorStmt" in node:
            markers["risks"].add("CURSOR_EXPLICITO")
        for key, value in node.items():
            if isinstance(value, str) and value.upper() == "JSONB":
                markers["risks"].add("TIPO_JSONB")
            _traverse_and_extract(value, markers)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _traverse_and_extract(item, markers)


def _sanitize_python_code(raw_code: str) -> str:
    """Remove delimitadores de markdown e garante a limpeza do codigo."""
    code = raw_code.replace("```python", "").replace("```", "").strip()
    # Remove linhas vazias no inicio que podem quebrar a indentacao global
    lines = code.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines)


def node_parsing(state: GraphState) -> Dict[str, Any]:
    """Etapa de parsing usando pglast para validar SQL legado."""
    try:
        raw_ast = parser.parse_sql(state["sql_code"])
        return {
            "parsed_ast": {"raw": str(raw_ast)},
            "report": {**state.get("report", {}), "parsing": "concluido"},
            "status": "em_processamento"
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [f"Erro no Parsing: {str(e)}"],
            "status": "falha"
        }


def node_analysis(state: GraphState) -> Dict[str, Any]:
    """Identifica riscos transacionais e semanticos antes da geracao."""
    if state.get("status") == "falha":
        return {}
    
    markers = {"risks": set()}
    _traverse_and_extract(state.get("parsed_ast"), markers)
    
    if "FOR UPDATE" in state["sql_code"].upper():
        markers["risks"].add("LOCK_FOR_UPDATE")
        
    return {
        "semantic_markers": {"risks": list(markers["risks"])},
        "report": {**state.get("report", {}), "analise": "concluido"}
    }


def node_generation(state: GraphState) -> Dict[str, Any]:
    """Gera o codigo Python via OpenRouter com rigor de indentacao."""
    if state.get("status") == "falha":
        return {}
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    
    try:
        client = httpx.Client(trust_env=False, timeout=60.0)
        
        llm = ChatOpenAI(
            model="deepseek/deepseek-chat",
            openai_api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            http_client=client,
            temperature=0.1
        )
        
        system_msg = (
            "Voce e um Arquiteto de Software Senior especialista em Python 3.14. "
            "Sua tarefa e converter PL/pgSQL para Python moderno usando SQLAlchemy 2.0. "
            "REGRAS OBRIGATORIAS:\n"
            "1. Use 4 espacos para indentacao.\n"
            "2. Nunca deixe um bloco (def, try, except, with, if) vazio.\n"
            "3. Garanta que o codigo seja sintaticamente valido.\n"
            "4. Nao inclua explicacoes fora do campo justificativa_arquitetural."
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_msg),
            ("human", "SQL Legado:\n{sql}\n\nRiscos Semanticos:\n{risks}")
        ])

        structured_llm = llm.with_structured_output(ModernizedCode)
        response = structured_llm.invoke(prompt.format(
            sql=state["sql_code"],
            risks=state.get("semantic_markers", {})
        ))

        return {
            "generated_python": _sanitize_python_code(response.codigo_python),
            "report": {
                **state.get("report", {}), 
                "geracao": "concluido",
                "justificativa": response.justificativa_arquitetural
            }
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [f"Erro na Geracao LLM: {str(e)}"],
            "status": "falha"
        }


def node_validation(state: GraphState) -> Dict[str, Any]:
    """Valida se o Python gerado e sintaticamente correto."""
    if state.get("status") == "falha":
        return {}
    
    try:
        ast.parse(state["generated_python"])
        return {
            "status": "sucesso", 
            "report": {**state.get("report", {}), "validacao": "concluido"}
        }
    except Exception as e:
        # Retorna o erro de indentacao ou sintaxe para o reporte
        return {
            "status": "falha", 
            "errors": state.get("errors", []) + [f"Erro Sintatico: {str(e)}"],
            "generated_python": state["generated_python"]
        }