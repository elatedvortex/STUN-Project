import abc
import os
import re
import subprocess
import logging
from typing import Any

from scheduler.exceptions import WriteError

logger = logging.getLogger(__name__)

# Valid sysctl path pattern — must be dotted identifiers only (§6.1)
_SYSCTL_PATH_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*$")

# Default subprocess timeout in seconds (§5.4)
_SYSCTL_TIMEOUT = 10


class SchedulerBackend(abc.ABC):
    @abc.abstractmethod
    def write(self, path: str, value: Any) -> None:
        pass

    @abc.abstractmethod
    def read(self, path: str) -> Any:
        pass


class SysctlBackend(SchedulerBackend):
    """Backend that reads/writes kernel parameters via the sysctl command.

    Safety features (§5.4, §6.1, §6.3):
    - Subprocess calls have a timeout to prevent indefinite hangs
    - sysctl paths are validated against a whitelist regex
    - Capability check available at startup
    """

    def __init__(self, timeout: int = _SYSCTL_TIMEOUT):
        self._timeout = timeout

    @staticmethod
    def check_capabilities() -> None:
        """Verify we have permission to write sysctl values (§6.3).

        Call at startup to fail fast with a clear error message instead of
        letting the first sysctl write produce a cryptic CalledProcessError.
        """
        if os.geteuid() != 0:
            # Check for CAP_SYS_ADMIN via /proc/self/status
            try:
                with open("/proc/self/status") as f:
                    for line in f:
                        if line.startswith("CapEff:"):
                            cap_hex = int(line.split(":")[1].strip(), 16)
                            cap_sys_admin = 1 << 21
                            if cap_hex & cap_sys_admin:
                                return  # We have CAP_SYS_ADMIN
            except (IOError, ValueError):
                pass
            logger.warning(
                "Process is not running as root and may lack CAP_SYS_ADMIN. "
                "sysctl writes will likely fail. Run with sudo or set capabilities."
            )

    @staticmethod
    def _validate_path(path: str) -> None:
        """Validate that a sysctl path only contains safe characters (§6.1)."""
        if not _SYSCTL_PATH_RE.match(path):
            raise WriteError(
                "Invalid sysctl path %r — must match %s" % (path, _SYSCTL_PATH_RE.pattern)
            )

    def write(self, path: str, value: Any) -> None:
        self._validate_path(path)
        try:
            subprocess.run(
                ["sysctl", "-w", "%s=%s" % (path, value)],
                capture_output=True,
                text=True,
                check=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            raise WriteError("sysctl write timed out after %ds for %s" % (self._timeout, path))
        except subprocess.CalledProcessError as e:
            raise WriteError("Failed to write sysctl %s: %s" % (path, e.stderr))

    def read(self, path: str) -> Any:
        self._validate_path(path)
        try:
            result = subprocess.run(
                ["sysctl", "-n", path],
                capture_output=True,
                text=True,
                check=True,
                timeout=self._timeout,
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise WriteError("sysctl read timed out after %ds for %s" % (self._timeout, path))
        except subprocess.CalledProcessError as e:
            raise WriteError("Failed to read sysctl %s: %s" % (path, e.stderr))
