#!/usr/bin/env python3
"""
scripts/run_dashboard.py — Launch the SysWatch performance monitor GUI.

Usage
-----
  # Normal launch (reads /proc live, no sysctl writes)
  python3 scripts/run_dashboard.py

  # With a custom poll interval (milliseconds)
  python3 scripts/run_dashboard.py --interval 500

  # With scheduler write support (requires root for sysctl writes)
  sudo python3 scripts/run_dashboard.py --with-scheduler
"""

import argparse
import logging
import sys
import os

# Make project root importable regardless of cwd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def _build_controller(registry):
    """Build a real SchedulerController (requires root for writes)."""
    from scheduler.controller import SchedulerController
    from scheduler.profile import ProfileStore
    from scheduler.rollback import RollbackStack
    from scheduler.validator import Validator
    from scheduler.writer import Writer
    return SchedulerController(
        registry=registry,
        validator=Validator(registry),
        writer=Writer(registry),
        rollback_stack=RollbackStack(),
        profile_store=ProfileStore(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="SysWatch — Linux Performance Monitor GUI")
    parser.add_argument(
        "--interval", type=int, default=1000,
        help="Poll interval in milliseconds (default: 1000)",
    )
    parser.add_argument(
        "--with-scheduler", action="store_true",
        help="Enable sysctl write support (requires root)",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable DEBUG logging",
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    from dashboard.app import launch_gui, _build_default_registry

    registry   = _build_default_registry()
    controller = _build_controller(registry) if args.with_scheduler else None

    if args.with_scheduler and os.geteuid() != 0:
        logging.warning(
            "Running with --with-scheduler but not root. "
            "Sysctl writes will likely fail with PermissionError."
        )

    launch_gui(registry=registry, controller=controller, interval_ms=args.interval)


if __name__ == "__main__":
    main()
