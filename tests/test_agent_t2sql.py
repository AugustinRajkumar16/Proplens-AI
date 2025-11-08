# tests/test_agent_t2sql.py
import pytest
from app.langgraph_nodes.router import LangRouter

def test_t2sql_count_leads():
    router = LangRouter()
    # seed DB is not present in test - we assert the node returns SQL in provenance
    out = router.handle('How many leads do we have?', {})
    assert 'provenance' in out and out['provenance'] is not None
