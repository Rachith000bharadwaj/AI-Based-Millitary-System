"""Vercel Serverless Entrypoint for AegisAI Flask API."""
import sys
import os

# Ensure root directory is in sys.path so modules import cleanly
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from api.app import create_app

app = create_app()
