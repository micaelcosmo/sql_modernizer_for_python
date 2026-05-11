import ast
from typing import Any, Dict
from pglast import parser
from graph.state import GraphState


def node_parsing(state: GraphState) -> Dict[str, Any]:
    """
    Converte o SQL bruto em uma AST utilizando pglast.
    """
    try:
        # pglast retorna uma tupla de statements
        raw_ast = parser.parse_sql(state["sql_code"])
        # Serializamos para dicionario para manter o State compativel com JSON
        return {
            "parsed_ast": [stmt.to_dict() for stmt in raw_ast],
            "report": {**state["report"], "parsing": "concluido"},
            "status": "em_processamento"
        }
    except Exception as e:
        return {
            "errors": state["errors"] + [f"Erro no Parsing: {str(e)}"],
            "status": "falha"
        }


def node_analysis(state: GraphState) -> Dict[str, Any]:
    """
    Identifica construcoes relevantes e pontos de risco na AST.
    """
    # Logica deterministica para mapear variaveis e chamadas (mock inicial)
    markers = {
        "params": [],
        "risks": [],
        "complexity": "baixa"
    }
    
    return {
        "semantic_markers": markers,
        "report": {**state["report"], "analise_semantica": "concluido"}
    }


def node_generation(state: GraphState) -> Dict[str, Any]:
    """
    Utiliza LLM para traduzir a lógica para Python 3.14.
    """
    # Aqui sera injetado o LangChain com o prompt estruturado
    python_code = "# Gerado via pipeline\ndef modern_function():\n    pass"
    
    return {
        "generated_python": python_code,
        "report": {**state["report"], "geracao_llm": "concluido"}
    }


def node_validation(state: GraphState) -> Dict[str, Any]:
    """
    Verifica a validade sintatica do Python gerado.
    """
    code = state.get("generated_python", "")
    try:
        ast.parse(code)
        return {
            "status": "sucesso",
            "report": {**state["report"], "validacao_estatica": "concluido"}
        }
    except SyntaxError as e:
        return {
            "status": "falha",
            "errors": state["errors"] + [f"Erro sintatico no Python: {str(e)}"]
        }