"""
Pytest configuration for openclaw tests.

Adds src/IskanderOS/openclaw to sys.path so that
`import agents.clerk.tools` resolves correctly regardless of
which directory pytest is invoked from.
"""
import os
import sys

# __file__ = .../openclaw/tests/conftest.py
# dirname once  → .../openclaw/tests/
# dirname twice → .../openclaw/          ← this is what we need on sys.path
_openclaw_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _openclaw_dir not in sys.path:
    sys.path.insert(0, _openclaw_dir)
