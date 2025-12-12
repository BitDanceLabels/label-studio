from __future__ import annotations

import importlib
import logging
import os
import pkgutil
from typing import Iterable

from app.celery_app import app as celery_app  # noqa: F401
import app.tasks  # noqa: F401  # keep the existing task module

logger = logging.getLogger(__name__)


def _from_env() -> Iterable[str]:
    raw = os.getenv("EXTRA_TASK_MODULES", "")
    return [m.strip() for m in raw.split(",") if m.strip()]


def _from_yaml_config() -> Iterable[str]:
    cfg_path = os.getenv("EXTRA_TASK_CONFIG", "config/worker_modules.yaml")
    if not os.path.exists(cfg_path):
        return []

    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.warning("YAML config set but PyYAML not installed (%s)", exc)
        return []

    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to read YAML task config %s: %s", cfg_path, exc)
        return []

    modules: list[str] = []
    for entry in data.get("modules", []):
        if isinstance(entry, str):
            modules.append(entry.strip())
            continue
        if isinstance(entry, dict):
            if not entry.get("enabled", True):
                continue
            mod = entry.get("module") or entry.get("path")
            if mod:
                modules.append(str(mod).strip())
    return modules


def _from_db() -> Iterable[str]:
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        return []

    table_name = os.getenv("WORKER_MODULES_TABLE", "worker_task_modules")
    try:
        from sqlalchemy import create_engine, text  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.warning("DATABASE_URL set but SQLAlchemy not installed (%s)", exc)
        return []

    engine = create_engine(db_url)
    query = text(
        f"select module_path from {table_name} where enabled = true"  # nosec B608
    )

    try:
        with engine.connect() as conn:
            rows = conn.execute(query)
            return [r[0] for r in rows if r and r[0]]
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to fetch modules from DB table %s: %s", table_name, exc)
        return []
    finally:
        try:
            engine.dispose()
        except Exception:
            pass


def _load_extra_modules_from_env() -> None:
    """
    Allow adding task modules without touching this file.
    Sources (in order):
    - EXTRA_TASK_MODULES (env)
    - YAML file (EXTRA_TASK_CONFIG or config/worker_modules.yaml)
    - DB table (WORKER_MODULES_TABLE, default worker_task_modules) using DATABASE_URL
    """
    modules = set(_from_env()) | set(_from_yaml_config()) | set(_from_db())
    for mod in sorted(modules):
        try:
            importlib.import_module(mod)
            logger.info("Loaded extra task module: %s", mod)
        except Exception as exc:  # pragma: no cover - import failures should not crash worker
            logger.warning("Failed to import extra task module %s: %s", mod, exc)


def _autodiscover_plugins() -> None:
    """
    Auto-import all modules under app.plugins.* so dropping a new file there
    will register tasks on next worker restart.
    """
    try:
        import app.plugins  # type: ignore
    except ImportError:
        return

    prefix = app.plugins.__name__ + "."
    for _, mod, _ in pkgutil.iter_modules(app.plugins.__path__, prefix):
        try:
            importlib.import_module(mod)
            logger.info("Auto-discovered plugin: %s", mod)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to import plugin %s: %s", mod, exc)


_load_extra_modules_from_env()
_autodiscover_plugins()

# Celery CLI expects an attribute named "celery" on the module when using "-A app.worker_main".
celery = celery_app

if __name__ == "__main__":
    celery.worker_main()
