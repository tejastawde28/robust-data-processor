import os
import sys

# Ensure the app module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mangum import Mangum
from asgiref.wsgi import WsgiToAsgi
from app import app

# Wrap Flask (WSGI) app to ASGI
asgi_app = WsgiToAsgi(app)

# Create the Lambda handler
handler = Mangum(asgi_app, lifespan="off")