"""
Fixed workload categories used for observation encoding (M6).

Each running process is classified into at most one category based on its
comm name.  The category list is stable — adding a category changes the
observation dimension, so treat this as part of the env contract.
"""

from __future__ import annotations

import re
from typing import Final

# Order defines the one-hot / weight slots in the observation vector.
WORKLOAD_CATEGORIES: Final[tuple[str, ...]] = (
    "browser",
    "compiler",
    "database",
    "dev_tool",
    "gaming",
    "media",
    "container",
    "interactive",
    "system",
)

# Map primary category → benchmark workload_type for historical lookup.
CATEGORY_TO_BENCHMARK_TYPE: Final[dict[str, str]] = {
    "browser": "interactive",
    "compiler": "cpu",
    "database": "mixed",
    "dev_tool": "interactive",
    "gaming": "gaming",
    "media": "mixed",
    "container": "mixed",
    "interactive": "interactive",
    "system": "cpu",
}

_COMM_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (cat, re.compile("|".join(patterns), re.IGNORECASE))
    for cat, patterns in {
        "browser": (
            r"chrome", r"chromium", r"firefox", r"brave", r"msedge",
            r"opera", r"vivaldi", r"electron",
        ),
        "compiler": (
            r"gcc", r"g\+\+", r"cc1", r"clang", r"rustc", r"\bld\b", r"\bmake\b",
            r"\bninja\b", r"cmake", r"cargo", r"go-build",
        ),
        "database": (
            r"postgres", r"mysql", r"mariadb", r"redis", r"mongod",
            r"sqlite", r"etcd",
        ),
        "dev_tool": (
            r"code", r"cursor", r"vim", r"nvim", r"idea", r"pycharm",
            r"node", r"python", r"jupyter",
        ),
        "gaming": (
            r"wine", r"wineserver", r"proton", r"lutris", r"heroic",
            r"hl2_linux", r"cs2", r"dota2", r"tf2", r"deadlock",
            r"minecraft", r"quake", r"baldur",
            r"gamescope", r"mangohud",
        ),
        "media": (
            r"ffmpeg", r"obs", r"mpv", r"vlc", r"gstreamer", r"pipewire",
            r"pulseaudio", r"wireplumber",
        ),
        "container": (
            r"docker", r"containerd", r"podman", r"runc", r"crun",
        ),
        "interactive": (
            r"Xorg", r"wayland", r"gnome-shell", r"kwin", r"sway",
            r"gamescope", r"steam",
        ),
        "system": (
            r"systemd", r"kworker", r"irq/", r"rcu_", r"migration",
            r"kswapd", r"kcompactd",
        ),
    }.items()
)


def classify_comm(comm: str) -> str | None:
    """Return the workload category for a process comm name, or None."""
    for category, pattern in _COMM_PATTERNS:
        if pattern.search(comm):
            return category
    return None
