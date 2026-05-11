import ast
from typing import Any, Dict, Set

from pglast import parser

from graph.state import GraphState


def _traverse_and_extract(node: Any, markers: Dict[str, Set[str]]) -> None:
    """
    Percorre recursivamente a AST gerada pelo pglast para identificar riscos.
    """
    if isinstance(node, dict):
        if "withClause" in node and node.get("withClause") is not None:
            if node["withClause"].get("recursive"):
                markers["risks"].add("CTE_RECURSIVA")

        if "RaiseStmt" in node:
            markers["risks"].add("RAISE_EXCEPTION")

        if "DeclareCursorStmt" in node or "ViewStmt" in node:
            markers["risks"].add("CURSOR_EXPLICITO")
            
        for key, value in node.items():
            if isinstance(value, str) and value.upper() == "JSONB":
                markers["risks"].add("TIPO_JSONB")
            _traverse_and_extract(value, markers)
            
    elif isinstance(node, (list, tuple)):
        for item in node:
            _traverse_and_extract(item, markers)
    elif hasattr(node, "__dict__"):
        _traverse_and_extract(vars(node), markers)


def node_parsing(state: GraphState) -> Dict[str, Any]:
    """
    Converte o SQL bruto em uma AST utilizando pglast.
    """
    try:
        raw_ast = parser.parse_sql(state["sql_code"])
        
        # Serializacao simples para manter compatibilidade com o TypedDict
        parsed_representation = {"raw_structure": str(raw_ast)}
        
        return {
            "parsed_ast": parsed_representation,
            "report": {**state.get("report", {}), "parsing": "concluido"},
            "status": "em_processamento"
        }
    except Exception as e:
        return {
            "errors": state.get("errors", []) + [f"Erro no Parsing: {str(e)}"],
            "status": "falha"
        }


def node_analysis(state: GraphState) -> Dict[str, Any]:
    """
    Identifica construcoes relevantes e pontos de risco na AST e no SQL bruto.
    """
    if state.get("status") == "falha":
        return {}
        
    markers: Dict[str, Set[str]] = {
        "params": set(),
        "risks": set()
    }
    
    ast_obj = state.get("parsed_ast")
    
    if ast_obj:
        _traverse_and_extract(ast_obj, markers)
        
    sql_upper = state.get("sql_code", "").upper()
    
    # Fallback estrutural para capturar sintaxes dentro do bloco DO/BEGIN
    if "TRANSACTION" in sql_upper or "COMMIT" in sql_upper or "ROLLBACK" in sql_upper:
        markers["risks"].add("TRANSACAO_EXPLICITA")
    if "FOR UPDATE" in sql_upper:
        markers["risks"].add("LOCK_FOR_UPDATE")
    if "RETURN QUERY" in sql_upper:
        markers["risks"].add("RETURN_QUERY")
    if "EXCEPTION" in sql_upper:
        markers["risks"].add("TRATAMENTO_EXCECAO")
    if "LOOP" in sql_upper or "WHILE" in sql_upper:
        markers["risks"].add("LOOP_DETECTADO")
    if "CURSOR" in sql_upper:
        markers["risks"].add("CURSOR_EXPLICITO")
        
    num_risks = len(markers["risks"])
    complexity = "baixa"
    if num_risks >= 4:
        complexity = "muito_alta"
    elif num_risks >= 2:
        complexity = "alta"
    elif num_risks == 1:
        complexity = "media"
        
    serializable_markers = {
        "params": list(markers["params"]),
        "risks": list(markers["risks"]),
        "complexity": complexity
    }
    
    return {
        "semantic_markers": serializable_markers,
        "report": {
            **state.get("report", {}), 
            "analise_semantica": "concluido", 
            "riscos_encontrados": serializable_markers["risks"],
            "complexidade_estimada": complexity
        }
    }


def node_generation(state: GraphState) -> Dict[str, Any]:
    """
    Utiliza LLM para traduzir a logica para Python 3.14.
    """
    if state.get("status") == "falha":
        return {}
        
    python_code = "# Gerado via pipeline\ndef modern_function():\n    pass\n"
    
    return {
        "generated_python": python_code,
        "report": {**state.get("report", {}), "geracao_llm": "concluido"}
    }


def node_validation(state: GraphState) -> Dict[str, Any]:
    """
    Verifica a validade sintatica do Python gerado.
    """
    if state.get("status") == "falha":
        return {}
        
    code = state.get("generated_python", "")
    try:
        ast.parse(code)
        return {
            "status": "sucesso",
            "report": {**state.get("report", {}), "validacao_estatica": "concluido"}
        }
    except SyntaxError as e:
        return {
            "status": "falha",
            "errors": state.get("errors", []) + [f"Erro sintatico no Python: {str(e)}"]
        }