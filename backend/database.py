# =============================================================================
# database.py -- SQLite persistence for scan history / analytics / dashboard.
# New addition for the platform layer; does not touch the ML pipeline.
# =============================================================================

import os
import uuid
import datetime as dt

from sqlalchemy import create_engine, Column, String, Float, Integer, Text, DateTime, text
from sqlalchemy.orm import sessionmaker, declarative_base

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "backend", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Overridable so the test suite can point this at a throwaway file instead of
# the real platform database (see backend/tests/conftest.py) -- every pytest
# run used to write permanent rows into the same platform.db the live app
# reads from (e.g. "zip-slip-test"/"skip-reason-test" batches visible in the
# real Dashboard/History/Reports UI). Defaults to the original path so
# production behavior is unchanged when the env var isn't set.
DB_PATH = os.environ.get("SECURECODE_DB_PATH") or os.path.join(DATA_DIR, "platform.db")

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class ScanRecord(Base):
    __tablename__ = "scans"

    id = Column(String, primary_key=True, default=new_id)
    batch_id = Column(String, index=True, nullable=True)
    project_name = Column(String, default="Untitled Project")
    filename = Column(String, default="pasted_code.c")
    source = Column(String, default="paste")  # paste | upload | zip | example
    code = Column(Text)

    verdict = Column(String)
    vuln_probability = Column(Float)
    safe_probability = Column(Float)
    confidence = Column(Float)
    risk_level = Column(String)
    risk_tag = Column(String)
    risk_color = Column(String)
    model_used = Column(String)
    is_demo = Column(Integer, default=0)

    ast_features_json = Column(Text)
    metric_features_json = Column(Text)
    embedding_dims = Column(Integer, default=0)
    embedding_2d_x = Column(Float, nullable=True)
    embedding_2d_y = Column(Float, nullable=True)

    lines = Column(Integer, default=0)
    loc = Column(Integer, default=0)

    # Phase 11 (Project Management) -- additive, nullable-safe columns for
    # bookmarking/pinning and free-form tagging. Existing rows default to
    # "not pinned" / "no tags" via the migration below; no existing data
    # is touched.
    is_pinned = Column(Integer, default=0)
    tags = Column(Text, default="")

    # Apply-Patch -> Re-Scan loop (docs/APPLY_PATCH_LOOP_DESIGN.md): nullable
    # link from a patched, derived scan back to the original it was applied
    # from. NULL for every ordinary scan (paste/batch/GitHub/live) -- only
    # set on records created by POST /api/scan/{id}/apply-patch. No FK
    # constraint (SQLite + this codebase's existing columns don't use them
    # elsewhere either, e.g. batch_id above), just an indexed lookup column.
    derived_from_scan_id = Column(String, index=True, nullable=True)

    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)


class GitHubBatchMeta(Base):
    """
    Per-batch repository provenance for a GitHub Mode scan -- a new table
    (not new columns on `scans`) so this is a purely additive change: no
    ALTER TABLE on the existing, already-populated `scans` table, and a
    fresh SQLite database with no rows here is exactly as valid as one with
    many. One row per batch_id, written once when github_service.scan_repo()
    finishes cloning+scanning.
    """
    __tablename__ = "github_batch_meta"

    batch_id = Column(String, primary_key=True)
    repo_url = Column(String)
    repo_name = Column(String)
    branch = Column(String, nullable=True)
    commit_sha = Column(String, nullable=True)
    files_detected = Column(Integer, default=0)
    files_analyzed = Column(Integer, default=0)
    files_skipped = Column(Integer, default=0)
    skip_reasons = Column(Text, default="")  # human-readable, comma-joined
    scanned_at = Column(DateTime, default=dt.datetime.utcnow)


Base.metadata.create_all(bind=engine)


def _migrate_add_columns():
    """
    SQLAlchemy's create_all() only creates missing TABLES, not missing
    COLUMNS on an already-existing table. Since `scans` already has rows
    from earlier phases, new nullable columns are added here via a plain
    ALTER TABLE, guarded by a check so this is a no-op on repeated startup.
    """
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(scans)"))}
        if "is_pinned" not in existing:
            conn.execute(text("ALTER TABLE scans ADD COLUMN is_pinned INTEGER DEFAULT 0"))
        if "tags" not in existing:
            conn.execute(text("ALTER TABLE scans ADD COLUMN tags TEXT DEFAULT ''"))
        if "derived_from_scan_id" not in existing:
            conn.execute(text("ALTER TABLE scans ADD COLUMN derived_from_scan_id TEXT"))
        conn.commit()


_migrate_add_columns()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
