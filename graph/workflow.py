from langgraph.graph import StateGraph, START, END
from graph.state import GraphState
from graph.nodes import (
    node_parsing,
    node_analysis,
    node_generation,
    node_validation
)


def create_modernizer_graph():
    """
    Constroi e compila o grafo de execucao.
    """
    workflow = StateGraph(GraphState)

    # Definicao dos nos
    workflow.add_node("parsing", node_parsing)
    workflow.add_node("analysis", node_analysis)
    workflow.add_node("generation", node_generation)
    workflow.add_node("validation", node_validation)

    # Definicao das arestas (fluxo linear conforme o desafio)
    workflow.add_edge(START, "parsing")
    workflow.add_edge("parsing", "analysis")
    workflow.add_edge("analysis", "generation")
    workflow.add_edge("generation", "validation")
    workflow.add_edge("validation", END)

    return workflow.compile()


# Instancia singleton para ser importada pela API
app_graph = create_modernizer_graph()