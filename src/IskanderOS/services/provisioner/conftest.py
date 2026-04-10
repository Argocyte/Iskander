"""
Pytest configuration for the provisioner service.

Adds src/IskanderOS/services/ to sys.path so that
`from provisioner.db import ...` resolves correctly regardless of
which directory pytest is invoked from.
"""
import os
import sys

# __file__ = .../services/provisioner/conftest.py
# dirname once  → .../services/provisioner/
# dirname twice → .../services/          ← this is what we need on sys.path
_services_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _services_dir not in sys.path:
    sys.path.insert(0, _services_dir)
