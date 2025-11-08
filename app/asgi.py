# app/asgi.py
import os

# Make sure DJANGO_SETTINGS_MODULE is set before importing Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

# Import Django and initialize it
import django
django.setup()

# Use Django's ASGI application
from django.core.asgi import get_asgi_application
application = get_asgi_application()
# Uvicorn expects the callable to be named 'app' per our previous uvicorn command.
# So expose the same object under name 'app' as well.
app = application
