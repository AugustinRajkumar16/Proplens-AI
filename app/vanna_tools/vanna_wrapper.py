# app/vanna_tools/vanna_wrapper.py

class VannaWrapper:
    def __init__(self):
    # In production, wire up to the real Vanna/Text-to-SQL model and a Chroma Vanna corpus
        pass

    def nl_to_sql(self, nl: str, schema: str | None = None) -> str:
        # Mock implementation: map a few simple NL patterns to SQL
        nl_l = nl.lower()
        if 'how many' in nl_l and 'leads' in nl_l:
            return 'SELECT COUNT(*) as total FROM leads;'
        if 'show' in nl_l and 'leads' in nl_l:
            return 'SELECT id, name, email FROM leads LIMIT 50;'
        return 'SELECT 1;'
