# =============================================================================
# job_service.py -- async job tracking for batch/GitHub scans
# (docs/ASYNC_SCAN_DESIGN.md).
#
# Callers (routers/scan.py's background task, github_service.py's background
# task) each open their OWN SessionLocal() and pass it in here, the same
# pattern github_service.py already uses for its post-clone DB writes --
# this module never opens a session itself except in reap_orphaned_jobs(),
# which runs once at startup with no request/task context to borrow one from.
# =============================================================================

import datetime as dt
import json

from sqlalchemy.orm import Session

from database import ScanJob, SessionLocal


def create_job(db: Session, batch_id: str, kind: str, files_total: int = 0) -> ScanJob:
    job = ScanJob(
        batch_id=batch_id,
        kind=kind,
        status="queued",
        files_total=files_total,
        files_completed=0,
        files_failed=0,
        created_at=dt.datetime.utcnow(),
    )
    db.add(job)
    db.commit()
    return job


def mark_running(db: Session, batch_id: str) -> None:
    db.query(ScanJob).filter(ScanJob.batch_id == batch_id).update({
        "status": "running",
        "started_at": dt.datetime.utcnow(),
    })
    db.commit()


def set_files_total(db: Session, batch_id: str, files_total: int) -> None:
    """GitHub jobs don't know files_total until after cloning + walking the
    repo -- unlike batch uploads, where it's known synchronously before the
    job is even created. Called once, right after that count is known."""
    db.query(ScanJob).filter(ScanJob.batch_id == batch_id).update({"files_total": files_total})
    db.commit()


def increment_progress(db: Session, batch_id: str, completed_delta: int = 0, failed_delta: int = 0) -> None:
    job = db.query(ScanJob).filter(ScanJob.batch_id == batch_id).first()
    if job is None:
        return
    job.files_completed += completed_delta
    job.files_failed += failed_delta
    db.commit()


def mark_succeeded(db: Session, batch_id: str, result: dict) -> None:
    db.query(ScanJob).filter(ScanJob.batch_id == batch_id).update({
        "status": "succeeded",
        "result_json": json.dumps(result),
        "finished_at": dt.datetime.utcnow(),
    })
    db.commit()


def mark_failed(db: Session, batch_id: str, error: str) -> None:
    db.query(ScanJob).filter(ScanJob.batch_id == batch_id).update({
        "status": "failed",
        "error": error[:2000],  # cap -- a runaway traceback string shouldn't bloat the row
        "finished_at": dt.datetime.utcnow(),
    })
    db.commit()


def get_job(db: Session, batch_id: str) -> ScanJob | None:
    return db.query(ScanJob).filter(ScanJob.batch_id == batch_id).first()


def job_to_dict(job: ScanJob) -> dict:
    return {
        "batch_id": job.batch_id,
        "kind": job.kind,
        "status": job.status,
        "files_total": job.files_total,
        "files_completed": job.files_completed,
        "files_failed": job.files_failed,
        "error": job.error,
        "created_at": job.created_at.isoformat() + "Z" if job.created_at else None,
        "started_at": job.started_at.isoformat() + "Z" if job.started_at else None,
        "finished_at": job.finished_at.isoformat() + "Z" if job.finished_at else None,
        "result": json.loads(job.result_json) if job.result_json else None,
    }


def reap_orphaned_jobs() -> int:
    """
    Called once at backend startup (main.py's lifespan). BackgroundTasks
    run in-process -- if the process restarts (container restart, --reload
    picking up a file change) while a job is mid-flight, that job's row is
    silently orphaned at "queued"/"running" forever, since nothing will
    ever update it again. This is the SAME risk profile Watch Mode's
    threading.Timer-based execution already has (docs/ASYNC_SCAN_DESIGN.md
    Sec 5) -- not a new fragility. Cheap mitigation: on every startup, any
    job still "queued"/"running" from a PREVIOUS process is necessarily
    orphaned (this process has not touched it yet), so mark it failed with
    an honest reason rather than leaving it stuck forever. Returns the
    number of jobs reaped, for startup logging.
    """
    db = SessionLocal()
    try:
        stuck = db.query(ScanJob).filter(ScanJob.status.in_(["queued", "running"])).all()
        for job in stuck:
            job.status = "failed"
            job.error = "Interrupted by a server restart before this job could finish."
            job.finished_at = dt.datetime.utcnow()
        db.commit()
        return len(stuck)
    finally:
        db.close()
