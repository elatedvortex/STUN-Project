import re
import json
from benchmarks.base import BenchmarkRunner
from benchmarks.types import BenchmarkResult

class StressNgAdapter(BenchmarkRunner):
    """Adapter for stress-ng (CPU workload)."""
    def __init__(self):
        super().__init__(name="stress-ng", workload_type="cpu")

    def run(self, timeout: int = 5, workers: int = 2, **kwargs) -> BenchmarkResult:
        cmd = ["stress-ng", "--cpu", str(workers), "--timeout", f"{timeout}s", "--metrics-brief"]

        try:
            res = self._execute_cmd(cmd)
            # stress-ng writes metrics to stderr in both old (info:) and new (metrc:) formats
            output = res.stderr
            success = res.returncode == 0

            score = 0.0
            metrics = {}
            if success:
                # Matches both:
                #   old: stress-ng: info:  [...] cpu   <bogo>  <real>  <usr>  <sys>  <bogo/s_real>  <bogo/s_usr+sys>
                #   new: stress-ng: metrc: [...] cpu   <bogo>  <real>  <usr>  <sys>  <bogo/s_real>  <bogo/s_usr+sys>
                match = re.search(
                    r"(?:info|metrc):\s+\[\d+\]\s+cpu[\s\-]\S*\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)",
                    output,
                )
                if match:
                    score = float(match.group(1))
                    metrics["bogo_ops"] = score

            return BenchmarkResult(
                name=self.name,
                workload_type=self.workload_type,
                success=success,
                score=score,
                score_is_higher_better=True,
                metrics=metrics,
                raw_output=output,
                error_message=output if not success else "",
            )
        except FileNotFoundError:
            return BenchmarkResult(self.name, self.workload_type, False, 0.0, True, error_message="stress-ng not found")

class SysbenchAdapter(BenchmarkRunner):
    """Adapter for sysbench (Memory/CPU)."""
    def __init__(self):
        super().__init__(name="sysbench", workload_type="memory")

    def run(self, timeout: int = 5, threads: int = 2, **kwargs) -> BenchmarkResult:
        cmd = ["sysbench", "memory", f"--threads={threads}", f"--time={timeout}", "run"]
        
        try:
            res = self._execute_cmd(cmd)
            output = res.stdout
            success = res.returncode == 0
            
            score = 0.0
            metrics = {}
            if success:
                match = re.search(r"Total operations:\s+\d+\s+\(([\d.]+)\s+per second\)", output)
                if match:
                    score = float(match.group(1))
                    metrics["ops_per_sec"] = score

            return BenchmarkResult(
                name=self.name,
                workload_type=self.workload_type,
                success=success,
                score=score,
                score_is_higher_better=True,
                metrics=metrics,
                raw_output=output,
                error_message=res.stderr if not success else ""
            )
        except FileNotFoundError:
            return BenchmarkResult(self.name, self.workload_type, False, 0.0, True, error_message="sysbench not found")

class HackbenchAdapter(BenchmarkRunner):
    """Adapter for hackbench (Scheduler latency)."""
    def __init__(self):
        super().__init__(name="hackbench", workload_type="mixed")

    def run(self, groups: int = 1, loops: int = 1000, **kwargs) -> BenchmarkResult:
        cmd = ["hackbench", "-g", str(groups), "-l", str(loops)]
        
        try:
            res = self._execute_cmd(cmd)
            output = res.stdout
            success = res.returncode == 0
            
            score = 0.0
            metrics = {}
            if success:
                match = re.search(r"Time:\s+([\d.]+)", output)
                if match:
                    score = float(match.group(1))
                    metrics["time_sec"] = score

            return BenchmarkResult(
                name=self.name,
                workload_type=self.workload_type,
                success=success,
                score=score,
                score_is_higher_better=False,
                metrics=metrics,
                raw_output=output,
                error_message=res.stderr if not success else ""
            )
        except FileNotFoundError:
            return BenchmarkResult(self.name, self.workload_type, False, 0.0, False, error_message="hackbench not found")

class CyclictestAdapter(BenchmarkRunner):
    """Adapter for cyclictest (Real-time Latency)."""
    def __init__(self):
        super().__init__(name="cyclictest", workload_type="interactive")

    def run(self, loops: int = 10000, **kwargs) -> BenchmarkResult:
        # -q (quiet), -l loops, -m (lock memory)
        cmd = ["cyclictest", "-q", "-l", str(loops)]
        
        try:
            res = self._execute_cmd(cmd)
            output = res.stdout
            success = res.returncode == 0
            
            score = 0.0
            metrics = {}
            if success:
                # Output example:
                # T: 0 (12345) P: 0 I:1000 C:  10000 Min:      2 Act:    3 Avg:    3 Max:      15
                match = re.search(r"Avg:\s+(\d+)\s+Max:\s+(\d+)", output)
                if match:
                    avg_lat = float(match.group(1))
                    max_lat = float(match.group(2))
                    score = max_lat # Typically max latency is the most important score for cyclictest
                    metrics["avg_latency_us"] = avg_lat
                    metrics["max_latency_us"] = max_lat

            return BenchmarkResult(
                name=self.name,
                workload_type=self.workload_type,
                success=success,
                score=score,
                score_is_higher_better=False, # Lower latency is better
                metrics=metrics,
                raw_output=output,
                error_message=res.stderr if not success else ""
            )
        except FileNotFoundError:
            return BenchmarkResult(self.name, self.workload_type, False, 0.0, False, error_message="cyclictest not found")

class FioAdapter(BenchmarkRunner):
    """Adapter for fio (IO Workload)."""
    def __init__(self):
        super().__init__(name="fio", workload_type="io")

    def run(self, size: str = "100M", **kwargs) -> BenchmarkResult:
        cmd = [
            "fio", "--name=randwrite", "--ioengine=sync", "--rw=randwrite",
            "--bs=4k", f"--size={size}", "--output-format=json"
        ]
        
        try:
            res = self._execute_cmd(cmd)
            output = res.stdout
            success = res.returncode == 0
            
            score = 0.0
            metrics = {}
            if success:
                try:
                    data = json.loads(output)
                    write_iops = data["jobs"][0]["write"]["iops"]
                    score = float(write_iops)
                    metrics["write_iops"] = score
                    metrics["write_bw"] = float(data["jobs"][0]["write"]["bw"])
                except (json.JSONDecodeError, KeyError, IndexError):
                    success = False

            return BenchmarkResult(
                name=self.name,
                workload_type=self.workload_type,
                success=success,
                score=score,
                score_is_higher_better=True, # Higher IOPS is better
                metrics=metrics,
                raw_output=output,
                error_message=res.stderr if not success else ""
            )
        except FileNotFoundError:
            return BenchmarkResult(self.name, self.workload_type, False, 0.0, True, error_message="fio not found")
