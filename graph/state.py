from typing import Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict):
    """
    Representa o estado do grafo de modernizacao.
    
    Atributos:
        sql_code: Codigo original em PL/pgSQL.
        schema_context: Contexto opcional das tabelas do banco legado.
        parsed_ast: Representacao estruturada gerada pelo pglast.
        semantic_markers: Metadados extraidos na analise (variaveis, riscos).
        generated_python: Codigo Python 3.14 produzido pelo LLM.
        report: Relatorio detalhado de cada etapa para auditoria.
        errors: Lista de falhas encontradas durante a execucao.
        status: Desfecho da execucao (sucesso, falha, parcial).
    """

    sql_code: str
    schema_context: Optional[str]
    parsed_ast: Optional[Dict[str, Any]]
    semantic_markers: Optional[Dict[str, Any]]
    generated_python: Optional[str]
    report: Dict[str, Any]
    errors: List[str]
    status: str