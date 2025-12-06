import os
import sys

# Ensure the app module is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mangum import Mangum
from app import app

# Create the Lambda handler
# Mangum adapts WSGI apps (Flask) to work with AWS Lambda
handler = Mangum(app, lifespan="off")