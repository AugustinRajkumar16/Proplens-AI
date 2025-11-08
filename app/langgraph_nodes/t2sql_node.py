# app/langgraph_nodes/t2sql_node.py
from app.vanna_tools.vanna_wrapper import VannaWrapper
import sqlite3
from pathlib import Path

# DB_PATH: repo root / db.sqlite3
DB_PATH = Path(__file__).resolve().parents[2] / "db.sqlite3"

class T2SQLNode:
    def __init__(self):
        self.vanna = VannaWrapper()

    def run(self, query: str, context: dict) -> dict:
        # Ask Vanna to produce SQL
        sql = self.vanna.nl_to_sql(query, schema=context.get('schema_sql'))

        def _is_sql_safe(sql: str) -> bool:
            """
            Basic safety checks for SQL produced by the NL->SQL layer.
            - must start with SELECT
            - no multiple statements (no stray semicolons)
            - only allow queries referencing whitelisted tables (quick heuristic)
              (expand/relax this whitelist as needed)
            """
            if not sql:
                return False
            s = sql.strip().lower()
            if not s.startswith('select'):
                return False
            # disallow embedded semicolons (multiple statements)
            if ';' in s.rstrip(';'):
                return False
            # quick whitelist: only allow queries that mention 'leads' for now
            # (you can expand ALLOWED_TABLES later)
            if 'leads' not in s:
                return False
            return True

        # If SQL is not safe, return denial with provenance for debugging
        if not _is_sql_safe(sql):
            return {'answer': 'Denied: only safe read queries are allowed', 'provenance': {'sql': sql}}

        # Execute against sqlite using context manager to ensure closure
        try:
            with sqlite3.connect(str(DB_PATH)) as conn:
                cur = conn.cursor()
                cur.execute(sql)
                rows = cur.fetchall()
                cols = [d[0] for d in cur.description] if cur.description else []
            return {'answer': {'columns': cols, 'rows': rows}, 'provenance': {'sql': sql}}
        except Exception as e:
            return {'answer': f'Execution error: {e}', 'provenance': {'sql': sql}}
