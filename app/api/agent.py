# app/api/agent.py
from ninja import Router, Schema
from typing import Any
from app.langgraph_nodes.router import LangRouter
from app.api.auth import JWTBearer

router = Router()            # this is the Ninja router (do not overwrite)
auth = JWTBearer()

class QueryIn(Schema):
    query: str
    context: dict | None = None

class QueryOut(Schema):
    answer: str
    provenance: Any | None = None

def _call_component(component, query, context):
    """
    Try common method names on `component` until one works.
    It attempts (query, context) then (query) where appropriate.
    """
    candidate_names = [
        "handle", "run", "query", "process", "call", "invoke", "handle_query", "__call__"
    ]
    for name in candidate_names:
        func = getattr(component, name, None)
        if callable(func):
            # try (query, context)
            try:
                return func(query, context)
            except TypeError:
                # try (query,) only
                try:
                    return func(query)
                except TypeError:
                    # signature mismatch, try next candidate
                    continue
            except Exception:
                # let real errors bubble up (so you see useful tracebacks)
                raise

    # last-resort names
    for name in ["execute", "run_sync", "process_query"]:
        func = getattr(component, name, None)
        if callable(func):
            try:
                return func(query, context)
            except Exception:
                raise

    raise RuntimeError("No suitable callable found on component: " + repr(component))


@router.post('/query/', auth=auth, response=QueryOut)
def query_agent(request, payload: QueryIn):
    """
    Create a LangRouter instance, pick a concrete node (rag or t2sql),
    call it with the query/context using the adapter, and return the result.
    """
    # create LangRouter instance (do NOT reassign the Ninja `router`)
    lg = LangRouter()

    # prefer rag node, then t2sql, else try the LangRouter instance itself
    component = None
    if hasattr(lg, "rag"):
        component = lg.rag
    elif hasattr(lg, "t2sql"):
        component = lg.t2sql
    else:
        component = lg

    # call the component using the adapter
    result = _call_component(component, payload.query, payload.context or {})

    # result should be mapping-like (keep behaviour same as original)
    return {'answer': result.get('answer') if result else None,
            'provenance': result.get('provenance') if result else None}
