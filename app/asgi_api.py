# app/asgi_api.py
from ninja import NinjaAPI
from ninja.errors import ConfigError
from app.api import auth, agent, ingestion, leads, probe

# Create NinjaAPI instance (keeps the single API object that other modules import)
api = NinjaAPI(title='Proplens Agent API', version='1.0.2', urls_namespace='proplens_api_v1_0001')

# Register routers safely: if add_router raises ConfigError (already attached),
# ignore it. This makes importing this module idempotent (safe if imported multiple times).
for prefix, router in (
    ('/auth/', auth.router),
    ('/agent/', agent.router),
    ('/documents/', ingestion.router),
    ('/leads/', leads.router),
    ('/probe_projects/', probe.router),
    ('/campaigns/', __import__('app.api.campaigns', fromlist=['']).router),
    ('/probe_chroma/', __import__('app.api.chroma_probe', fromlist=['']).router),
):
    try:
        api.add_router(prefix, router)
    except ConfigError as e:
        # Router already attached — that's fine during Django startup where
        # this module can be imported multiple times. Log and continue.
        print(f"[asgi_api] router {prefix} already attached; skipping. ({e})")

