# app/langgraph_nodes/router.py
from app.langgraph_nodes.t2sql_node import T2SQLNode
from app.langgraph_nodes.doc_rag_node import DocRAGNode

class LangRouter:
    def __init__(self):
        self.t2sql = T2SQLNode()
        self.rag = DocRAGNode()

    def handle(self, query: str, context: dict) -> dict:
        # Very simple classifier: if query contains 'how many' or 'show' treat as T2SQL
        q = query.lower()
        if any(k in q for k in ['how many', 'show', 'list', 'count', 'select']):
            return self.t2sql.run(query, context)
        return self.rag.run(query, context)