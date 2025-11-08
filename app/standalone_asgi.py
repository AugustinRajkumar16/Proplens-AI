# standalone_asgi.py
from ninja import NinjaAPI
from app.api import auth, agent, ingestion, leads

api = NinjaAPI(title='Proplens Agent API', version='1.0.2', urls_namespace='proplens_api_v1_0001')

for prefix, router in (
    ('/auth/', auth.router),
    ('/agent/', agent.router),
    ('/documents/', ingestion.router),
    ('/leads/', leads.router),
):
    api.add_router(prefix, router)

app = api  # NinjaAPI instance is ASGI callable here

