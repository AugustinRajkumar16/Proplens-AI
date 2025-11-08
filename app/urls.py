# app/urls.py
from django.urls import path, include
from .asgi_api import api

# api.urls is a 3-tuple (patterns, app_name, namespace)
patterns, app_name, namespace = api.urls

urlpatterns = [
    # include() expects a (patterns, app_name) tuple and a separate namespace kwarg
    path('', include((patterns, app_name), namespace=namespace)),
]
