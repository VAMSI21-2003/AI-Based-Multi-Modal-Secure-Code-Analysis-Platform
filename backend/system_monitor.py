# =============================================================================
# system_monitor.py -- lightweight, in-memory operational telemetry.
#
# Deliberately NOT persisted to the database: this is process-local runtime
# telemetry (model load time, prediction latency, live CPU/RAM), not
# scan data. Keeping it in-memory means zero schema changes to the existing
# ScanRecord table -- nothing about the current DB or API contracts changes.
# =============================================================================

import time
import psutil
from collections import deque

_state = {
    "model_load_times_sec": {},   # {"xgboost": 0.4, "random_forest": 0.1, "codebert": 6.2}
    "prediction_latencies_ms": deque(maxlen=200),
    "process": psutil.Process(),
}

_process_start = time.time()


def record_model_load(name: str, seconds: float):
    _state["model_load_times_sec"][name] = round(seconds, 3)


def record_prediction_latency(seconds: float):
    _state["prediction_latencies_ms"].append(round(seconds * 1000, 1))


def timed_model_load(name: str, load_fn):
    """Wraps a zero-arg loader function, recording how long it took the
    FIRST time it actually runs. Safe no-op wrapper -- does not change what
    the loader returns or how caching (lru_cache) behaves upstream."""
    start = time.time()
    result = load_fn()
    record_model_load(name, time.time() - start)
    return result


def get_stats(files_scanned: int = 0) -> dict:
    proc = _state["process"]
    latencies = list(_state["prediction_latencies_ms"])
    avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else None

    return {
        "cpu_percent": psutil.cpu_percent(interval=0.05),
        "process_cpu_percent": proc.cpu_percent(interval=0.05),
        "ram_percent": psutil.virtual_memory().percent,
        "ram_used_mb": round(psutil.virtual_memory().used / (1024 * 1024), 1),
        "ram_total_mb": round(psutil.virtual_memory().total / (1024 * 1024), 1),
        "process_ram_mb": round(proc.memory_info().rss / (1024 * 1024), 1),
        "model_load_times_sec": _state["model_load_times_sec"],
        "avg_prediction_latency_ms": avg_latency,
        "recent_prediction_latencies_ms": latencies[-30:],
        "prediction_count_tracked": len(latencies),
        "files_scanned_total": files_scanned,
        "uptime_sec": round(time.time() - _process_start, 1),
    }
