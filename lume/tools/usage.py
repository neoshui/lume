"""App usage frequency tracker."""

import json
import os
import threading
from pathlib import Path
from collections import defaultdict

from lume.config import get_data_dir


USAGE_FILE = get_data_dir() / "usage.json"


class UsageTracker:
    """Track how often each app is launched."""

    def __init__(self):
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}
        self._load()

    def _load(self):
        """Load usage data from disk."""
        if USAGE_FILE.exists():
            try:
                data = json.loads(USAGE_FILE.read_text())
                if isinstance(data, dict):
                    self._counts = data
            except (json.JSONDecodeError, OSError):
                pass

    def _save(self):
        """Save usage data to disk."""
        try:
            USAGE_FILE.write_text(json.dumps(self._counts, indent=2))
        except OSError:
            pass

    def record_launch(self, app_id: str):
        """Record that an app was launched."""
        if not app_id:
            return
        with self._lock:
            self._counts[app_id] = self._counts.get(app_id, 0) + 1
            self._save()

    def get_frequency(self, app_id: str) -> int:
        """Get the launch count for an app."""
        with self._lock:
            return self._counts.get(app_id, 0)

    def get_sorted_apps(self, app_list: list[dict]) -> list[dict]:
        """Sort a list of app dicts by usage frequency (high to low)."""
        with self._lock:

            def sort_key(app):
                return self._counts.get(app["id"], 0)

            return sorted(app_list, key=sort_key, reverse=True)


# Singleton instance
_tracker: UsageTracker | None = None
_tracker_lock = threading.Lock()


def get_tracker() -> UsageTracker:
    """Get the global usage tracker instance."""
    global _tracker
    with _tracker_lock:
        if _tracker is None:
            _tracker = UsageTracker()
        return _tracker


def record_launch(app_id: str):
    """Convenience function to record an app launch."""
    get_tracker().record_launch(app_id)


def get_sorted_by_frequency(app_list: list[dict]) -> list[dict]:
    """Sort app list by launch frequency."""
    return get_tracker().get_sorted_apps(app_list)
