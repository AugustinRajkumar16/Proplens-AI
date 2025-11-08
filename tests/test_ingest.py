# tests/test_ingest.py
import pytest
from app.api.ingestion import upload_document
from ninja.testing import TestClient
from app.asgi import api

client = TestClient(api)

def test_upload_requires_auth():
    resp = client.post('/documents/upload/')
    assert resp.status_code == 401
