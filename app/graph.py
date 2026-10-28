from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app import config
from app.engine import FALLBACK_REPLY, build_messages, finalize, llm_round, precheck
from app.llm import chat


class TurnState(TypedDict, total=False):
    user_text: str
    messages: list
    reply: str | None
    rounds: int


def build_graph(db, session, llm = chat):
    def n_precheck(state:TurnState):
        text_in = state["user_text"].strip()
        canned = precheck(db, session, text_in)
        if canned is not None:
            return {"reply": canned}
        return {
            "messages": build_messages(session, text_in),
            "reply": None,
            "rounds": 0,
        }
    def after_precheck(state: TurnState):
        return "finalize" if state.get("reply") else "llm"

    def n_llm(state: TurnState):
        reply, messages = llm_round(db, session, state["messages"], llm)
        return {"reply": reply, "messages": messages, "rounds": state["rounds"] + 1}
    
    def after_llm(state: TurnState):
        if state["reply"] is not None or state["rounds"] >= config.MAX_TOOL_ROUNDS:
            return "finalize"
        return "llm"

    def n_finalize(state: TurnState):
        result = finalize(
            db, session, state["user_text"], state.get("reply") or FALLBACK_REPLY
        )
        return {"reply": result.reply}   
    

    g = StateGraph(TurnState)
    g.add_node("precheck", n_precheck)
    g.add_node("llm", n_llm)
    g.add_node("finalize", n_finalize)
    g.add_edge(START, "precheck")
    g.add_conditional_edges("precheck", after_precheck, {"finalize": "finalize", "llm": "llm"})
    g.add_conditional_edges("llm", after_llm, {"finalize": "finalize", "llm": "llm"})
    g.add_edge("finalize", END)
    return g.compile()