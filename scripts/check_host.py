#!/usr/bin/env python3
"""Read-only compatibility report. Never requests privileges or writes sysctls."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.loader import build_registry_from_config
from scheduler.backend import SysctlBackend


def inspect_host(registry):
    backend = SysctlBackend()
    parameters = []
    for meta in registry.get_all():
        row = {"name": meta.name, "path": meta.path, "available": False}
        try:
            row.update({"available": True, "value": meta.type(backend.read(meta.path))})
        except Exception as exc:
            row["error"] = str(exc)
        parameters.append(row)
    tools = {}
    for name in ("sysctl", "stress-ng", "sysbench", "hackbench", "cyclictest", "fio"):
        path = shutil.which(name)
        row = {"path": path, "version_output": None}
        if path:
            try:
                result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=3)
                row["version_output"] = (result.stdout + result.stderr).strip()[:1000]
                row["version_exit_code"] = result.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                row["error"] = str(exc)
        tools[name] = row
    governors = {}
    for path in Path("/sys/devices/system/cpu/cpufreq").glob("policy*/scaling_governor"):
        try:
            governors[path.parent.name] = path.read_text().strip()
        except OSError:
            pass
    return {"kernel": platform.release(), "machine": platform.machine(),
            "python": platform.python_version(), "cpu_count": os.cpu_count(),
            "parameters": parameters, "tools": tools, "governors": governors,
            "all_parameters_readable": all(row["available"] for row in parameters),
            "scope": "Read availability only; write access, configuration safety and performance are unverified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/scheduler.yaml")
    parser.add_argument("--output")
    args = parser.parse_args()
    report = inspect_host(build_registry_from_config(args.config))
    encoded = json.dumps(report, indent=2)
    if args.output:
        with Path(args.output).open("x") as output:
            output.write(encoded + "\n")
    print(encoded)


if __name__ == "__main__":
    main()
