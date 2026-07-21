# =============================================================================
# logging_config.py -- one place to configure the standard library `logging`
# module for the live FastAPI service.
#
# Scope note: grepping this codebase for print() found it almost entirely in
# standalone CLI scripts (backend/ci_scan.py, backend/precompute_*.py) where
# printed, human-readable stdout output IS the correct, intended behavior --
# converting those to structured log lines would be a regression, not a fix
# (ci_scan.py's report is meant to be read directly in a terminal/CI log,
# not parsed as log records). The real gap was narrower: app/predictor.py's
# model-loading failure paths used bare print() with no severity level, no
# timestamp, and no way to filter/alert on them in a real deployment. This
# module exists for those genuinely operational, service-level log lines.
# =============================================================================

import logging
import os


def setup_logging() -> None:
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
