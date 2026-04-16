# Re-export for backward compatibility.
# Implementation lives in app.services.seed_data.
from app.services.seed_data import seed_data_service

__all__ = ["seed_data_service"]
