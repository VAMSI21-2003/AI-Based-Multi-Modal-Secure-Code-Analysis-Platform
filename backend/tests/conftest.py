# =============================================================================
# conftest.py -- shared pytest fixtures/path setup for backend/tests/.
#
# Mirrors the same sys.path setup main.py and ml_bridge.py already use, so
# tests can `import main` and `import ml_bridge` exactly as the real app
# does, without duplicating or changing that logic.
# =============================================================================

import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
