import sys
import os

# allow Vercel to find the backend module
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.app.main import app