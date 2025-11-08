from app.langgraph_nodes.router import LangRouter

def test_rag_route():
    router = LangRouter()
    out = router.handle('What are the amenities of Godrej Vistas?', {})
    assert 'answer' in out
