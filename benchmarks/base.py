import abc
import subprocess
import logging
from typing import Dict, Any, List
from benchmarks.types import BenchmarkResult

logger = logging.getLogger(__name__)

class BenchmarkRunner(abc.ABC):
    """Abstract base class for benchmark adapters."""
    
    def __init__(self, name: str, workload_type: str):
        self.name = name
        self.workload_type = workload_type

    @abc.abstractmethod
    def run(self, **kwargs) -> BenchmarkResult:
        """Run the benchmark and return normalized result."""
        pass

    def _execute_cmd(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """Helper to run a subprocess command safely."""
        logger.debug(f"Running benchmark command: {' '.join(cmd)}")
        return subprocess.run(cmd, capture_output=True, text=True)
