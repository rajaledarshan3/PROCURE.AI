
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent.nodes import (
    evaluate_vendors_node,
    parse_quotations_node,
    prepare_approval_node,
    record_approval_node,
)
from app.agent.state import ProcurementState
from app.db.checkpointer import checkpointer


def approval_gate(state: ProcurementState) -> dict:
    winner = state.get("selected_vendor")

    if winner is None:
        return {"approval_status": "no_eligible_vendor"}

    decision = interrupt(
        {
            "type": "procurement_approval_required",
            "message": "Review the recommended vendor before proceeding.",
            "selected_vendor": winner,
            "eligible_vendors": [
                vendor
                for vendor in state.get("ranked_vendors", [])
                if vendor.get("eligible")
            ],
        }
    )

    return {"approval_decision": decision}


def route_after_preparation(
    state: ProcurementState,
) -> Literal["approval_gate", "__end__"]:
    if state.get("selected_vendor") is None:
        return "__end__"
    return "approval_gate"


def build_procurement_graph():
    workflow = StateGraph(ProcurementState)

    workflow.add_node("parse_quotations", parse_quotations_node)
    workflow.add_node("evaluate_vendors", evaluate_vendors_node)
    workflow.add_node("prepare_approval", prepare_approval_node)
    workflow.add_node("approval_gate", approval_gate)
    workflow.add_node("record_approval", record_approval_node)

    workflow.add_edge(START, "parse_quotations")
    workflow.add_edge("parse_quotations", "evaluate_vendors")
    workflow.add_edge("evaluate_vendors", "prepare_approval")

    workflow.add_conditional_edges(
        "prepare_approval",
        route_after_preparation,
        {
            "approval_gate": "approval_gate",
            "__end__": END,
        },
    )

    workflow.add_edge("approval_gate", "record_approval")
    workflow.add_edge("record_approval", END)

    return workflow.compile(checkpointer=checkpointer)


procurement_graph = build_procurement_graph()
