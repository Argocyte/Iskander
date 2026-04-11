"""
conftest.py — makes decision-recorder modules importable as top-level modules.

The service dir is added to sys.path so that `import main`, `import db`,
and `import ipfs` all resolve without requiring a package prefix.
"""
import sys
from pathlib import Path

_service_dir = Path(__file__).parent.parent
if str(_service_dir) not in sys.path:
    sys.path.insert(0, str(_service_dir))
