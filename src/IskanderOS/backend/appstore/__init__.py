"""
backend.appstore
~~~~~~~~~~~~~~~~
Phase 13: Democratic App Store & Container Orchestration.

Exports:
  AppCatalog      — loads and queries the vetted FOSS catalog.
  DockerManager   — Glass-Box-logged Docker SDK wrapper.
"""
from backend.appstore.catalog import AppCatalog
from backend.appstore.docker_manager import DockerManager

__all__ = ["AppCatalog", "DockerManager"]
