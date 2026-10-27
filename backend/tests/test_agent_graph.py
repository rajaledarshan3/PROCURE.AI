


from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.agent.state import ProcurementState


def build_test_graph(checkpointer):
    def prepare(state: ProcurementState):
        return {
            "selected_vendor": {
                "name": "Vendor A",
                "price": 50000,
                "eligible": True,
                "rank": 1,
            }
        }

    def approval_gate(state: ProcurementState):
        decision = interrupt(
            {
                "type": "procurement_approval_required",
                "selected_vendor": state["selected_vendor"],
            }
        )
        return {"approval_decision": decision}

    def record_approval(state: ProcurementState):
        decision = state["approval_decision"]
        status = "approved" if decision["approved"] else "rejected"
        return {"approval_status": status}

    workflow = StateGraph(ProcurementState)
    workflow.add_node("prepare", prepare)
    workflow.add_node("approval_gate", approval_gate)
    workflow.add_node("record_approval", record_approval)
    workflow.add_edge(START, "prepare")
    workflow.add_edge("prepare", "approval_gate")
    workflow.add_edge("approval_gate", "record_approval")
    workflow.add_edge("record_approval", END)

    return workflow.compile(checkpointer=checkpointer)


def test_graph_pauses_then_resumes_after_approval():
   

    # An in-memory saver is used so this test needs no database.
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_test_graph(MemorySaver())
    config = {"configurable": {"thread_id": "test-approval-run"}}

    paused = graph.invoke({}, config=config)

    assert paused["__interrupt__"]
    assert paused["__interrupt__"][0].value["type"] == (
        "procurement_approval_required"
    )

    completed = graph.invoke(
        Command(
            resume={
                "approved": True,
                "reviewer": "Test Reviewer",
                "notes": "Test approval",
            }
        ),
        config=config,
    )

    assert completed["approval_status"] == "approved"
    assert completed["approval_decision"]["approved"] is True


def test_graph_records_rejection_after_resume():
    from langgraph.checkpoint.memory import MemorySaver

    graph = build_test_graph(MemorySaver())
    config = {"configurable": {"thread_id": "test-rejection-run"}}

    paused = graph.invoke({}, config=config)
    assert paused["__interrupt__"]

    completed = graph.invoke(
        Command(
            resume={
                "approved": False,
                "reviewer": "Test Reviewer",
                "notes": "Rejected during test",
            }
        ),
        config=config,
    )

    assert completed["approval_status"] == "rejected"
    assert completed["approval_decision"]["approved"] is False
