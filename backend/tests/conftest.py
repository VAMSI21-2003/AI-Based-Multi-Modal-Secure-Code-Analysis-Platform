# =============================================================================
# conftest.py -- shared pytest fixtures/path setup for backend/tests/.
#
# Mirrors the same sys.path setup main.py and ml_bridge.py already use, so
# tests can `import main` and `import ml_bridge` exactly as the real app
# does, without duplicating or changing that logic.
# =============================================================================

import atexit
import os
import shutil
import sys
import tempfile

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ── Test database isolation ──────────────────────────────────────────────────
#
# MUST run before any test module (or anything it imports) pulls in
# `database.py` or `main.py`, since database.py reads this env var exactly
# once, at import time, to pick its SQLite file. Pytest always imports a
# directory's conftest.py before collecting/importing the test modules in
# that directory, so setting this here -- at conftest module load time --
# is early enough. Without this, every test run wrote permanent rows
# (batches literally named "zip-slip-test", "skip-reason-test", etc.) into
# the same backend/data/platform.db the live running app reads from.
_TEST_DB_DIR = tempfile.mkdtemp(prefix="securecode_test_db_")
os.environ["SECURECODE_DB_PATH"] = os.path.join(_TEST_DB_DIR, "test_platform.db")
atexit.register(shutil.rmtree, _TEST_DB_DIR, True)
