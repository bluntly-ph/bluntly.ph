"""Print the environment the app would connect to, for the dev launcher.

Two lines: a human-readable target, then SAFE or PRODUCTION. Kept as a file
rather than an inline `python -c` because quoting a multi-line program through
PowerShell is its own source of bugs, and this one guards production.

Prints no credentials - `describe_target()` shows host and project ref only.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.env_guard import describe_target, load_test_env, production_signals  # noqa: E402

# Mirror what the backend itself will resolve: .env.test wins when present.
load_test_env()
print(describe_target())
print("PRODUCTION" if production_signals() else "SAFE")
