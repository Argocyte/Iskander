"""
Pytest configuration for the decision-recorder service.

Adds the decision-recorder directory itself to sys.path so that
`from db import ...` and `import ipfs` resolve correctly regardless of
which directory pytest is invoked from. The service uses direct (non-relative)
imports because it is run as a standalone module, not a distributed package.
"""
import os
import sys

# __file__ = .../services/decision-recorder/conftest.py
# dirname once → .../services/decision-recorder/  ← we want this on sys.path
_service_dir = os.path.dirname(os.path.abspath(__file__))
if _service_dir not in sys.path:
    sys.path.insert(0, _service_dir)
