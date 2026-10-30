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
            # Newer stress-ng (v0.14+) writes ALL output including metrc: lines to stdout.
            # Older versions wrote to stderr. Combine both so the adapter works with either.
            output = res.stdout + res.stderr
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
                else:
                    # A successful process without a parsed metric is not a
                    # successful measurement. Do not train/evaluate on zero.
                    success = False

            return BenchmarkResult(
                name=self.name,
                workload_type=self.workload_type,
                success=success,
                score=score,
                score_is_higher_better=True,
                metrics=metrics,
                raw_output=output,
                error_message=(output or "No CPU throughput metric parsed") if not success else "",
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
            output = res.stdout + res.stderr
            success = res.returncode == 0
            
            score = 0.0
            metrics = {}
            if success:
                match = re.search(r"Total operations:\s+\d+\s+\(([\d.]+)\s+per second\)", output)
                if match:
                    score = float(match.group(1))
                    metrics["ops_per_sec"] = score
                else:
                    success = False

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
            output = res.stdout + res.stderr
            success = res.returncode == 0
            
            score = 0.0
            metrics = {}
            if success:
                match = re.search(r"Time:\s+([\d.]+)", output)
                if match:
                    score = float(match.group(1))
                    metrics["time_sec"] = score
                else:
                    success = False

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
            output = res.stdout + res.stderr
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
                else:
                    success = False

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
            output = res.stdout + res.stderr
            success = res.returncode == 0
            
            score = 0.0
            metrics = {}
            if success:
                try:
                    data = json.loads(res.stdout)
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


class GamingAdapter(BenchmarkRunner):
    """Benchmark for gaming workloads.

    Priority:
      1. glmark2      — OpenGL benchmark, ``apt install glmark2``
      2. vkmark       — Vulkan benchmark,  ``apt install vkmark``
      3. stress-ng    — CPU/memory fallback (always available)

    The score is always *higher-is-better* (FPS / bogo-ops / ops-per-sec).
    """

    def __init__(self) -> None:
        super().__init__(name="gaming", workload_type="gaming")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _try_glmark2(self) -> "BenchmarkResult | None":
        """Run glmark2 offscreen and parse Score line.  Returns None on FileNotFoundError."""
        import re
        cmd = ["glmark2", "--off-screen", "--run-forever=false"]
        try:
            res = self._execute_cmd(cmd, timeout=120)
        except FileNotFoundError:
            return None
        output = res.stdout + res.stderr
        success = res.returncode == 0
        score = 0.0
        metrics: dict = {}
        if success:
            m = re.search(r"glmark2\s+Score:\s*(\d+)", output)
            if m:
                score = float(m.group(1))
                metrics["glmark2_score"] = score
        return BenchmarkResult(
            name="glmark2",
            workload_type=self.workload_type,
            success=success,
            score=score,
            score_is_higher_better=True,
            metrics=metrics,
            raw_output=output,
            error_message=output if not success else "",
        )

    def _try_vkmark(self) -> "BenchmarkResult | None":
        """Run vkmark offscreen and parse final score.  Returns None on FileNotFoundError."""
        import re
        cmd = ["vkmark", "--winsys-dir=/usr/lib/x86_64-linux-gnu/vkmark",
               "--data-dir=/usr/share/vkmark", "--run-forever=false"]
        try:
            res = self._execute_cmd(cmd, timeout=120)
        except FileNotFoundError:
            return None
        output = res.stdout + res.stderr
        success = res.returncode == 0
        score = 0.0
        metrics: dict = {}
        if success:
            m = re.search(r"vkmark\s+Score:\s*(\d+)", output)
            if m:
                score = float(m.group(1))
                metrics["vkmark_score"] = score
        return BenchmarkResult(
            name="vkmark",
            workload_type=self.workload_type,
            success=success,
            score=score,
            score_is_higher_better=True,
            metrics=metrics,
            raw_output=output,
            error_message=output if not success else "",
        )

    def _fallback_stress(self, timeout: int = 10, workers: int = 4) -> "BenchmarkResult":
        """stress-ng CPU fallback — always runnable."""
        import re
        cmd = ["stress-ng", "--cpu", str(workers), "--timeout", f"{timeout}s",
               "--metrics-brief"]
        try:
            res = self._execute_cmd(cmd)
        except FileNotFoundError:
            return BenchmarkResult(
                self.name, self.workload_type, False, 0.0, True,
                error_message="No gaming benchmark tool found (glmark2/vkmark/stress-ng all missing)",
            )
        # Combine stdout+stderr: newer stress-ng writes to stdout, older to stderr
        output = res.stdout + res.stderr
        success = res.returncode == 0
        score = 0.0
        metrics: dict = {}
        if success:
            m = re.search(
                r"(?:info|metrc):\s+\[\d+\]\s+cpu[\s\-]\S*\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+[\d.]+\s+([\d.]+)",
                output,
            )
            if m:
                score = float(m.group(1))
                metrics["bogo_ops_per_sec"] = score
        return BenchmarkResult(
            name="stress-ng-gaming-fallback",
            workload_type=self.workload_type,
            success=success,
            score=score,
            score_is_higher_better=True,
            metrics=metrics,
            raw_output=output,
            error_message=output if not success else "",
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, prefer: str = "auto", timeout: int = 10,
            workers: int = 4, **kwargs) -> "BenchmarkResult":
        """Run the best available gaming benchmark.

        Args:
            prefer: ``"glmark2"`` | ``"vkmark"`` | ``"stress-ng"`` | ``"auto"``
                    (default). ``"auto"`` tries glmark2 → vkmark → stress-ng.
            timeout: seconds for stress-ng fallback run.
            workers: CPU workers for stress-ng fallback.
        """
        if prefer == "glmark2":
            result = self._try_glmark2()
            if result is None:
                result = self._fallback_stress(timeout, workers)
            return result

        if prefer == "vkmark":
            result = self._try_vkmark()
            if result is None:
                result = self._fallback_stress(timeout, workers)
            return result

        if prefer == "stress-ng":
            return self._fallback_stress(timeout, workers)

        # auto: try GPU benchmarks first, fall back to CPU
        result = self._try_glmark2()
        if result is not None and result.success:
            return result
        result = self._try_vkmark()
        if result is not None and result.success:
            return result
        return self._fallback_stress(timeout, workers)
