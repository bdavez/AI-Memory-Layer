# backend/api.py
#
# Legacy placeholder module for API routing.
# The Flask app in backend/server.py registers blueprints directly from:
#   - backend.api_jobs
#   - backend.api_memory
#   - backend.api_models
#
# This module exists only to keep the backend package importable and
# to provide a stable place for future API aggregation if needed.

from .api_jobs import bp as jobs_bp
from .api_memory import bp as memory_bp
from .api_models import bp as models_bp
from .api_assistant import bp as assistant_bp

__all__ = ["jobs_bp", "memory_bp", "models_bp"]