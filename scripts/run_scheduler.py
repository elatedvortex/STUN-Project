#!/usr/bin/env python3
"""
M2 demo: run the Scheduler Controller and Safety baseline
"""

import sys
import logging
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scheduler import (
    ParameterMeta,
    ParameterRegistry,
    Validator,
    Writer,
    RollbackStack,
    ProfileStore,
    SchedulerController,
    SysctlBackend
)
from safety import SecondaryValidator, Watchdog, CheckpointManager

# A mock backend to not actually mess up the host system during a demo
class DemoMockBackend:
    def __init__(self):
        self.state = {
            "kernel.sched_min_granularity_ns": "3000000",
            "kernel.sched_wakeup_granularity_ns": "4000000"
        }
    def write(self, path, value):
        self.state[path] = str(value)
    def read(self, path):
        return self.state.get(path, "0")

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")
    log = logging.getLogger("run_scheduler")

    log.info("--- M2 Scheduler Controller Demo ---")
    
    # 1. Setup Registry
    registry = ParameterRegistry()
    registry.register(ParameterMeta("sched_min_granularity_ns", int, 100000, 100000000, backend="sysctl", path="kernel.sched_min_granularity_ns"))
    registry.register(ParameterMeta("sched_wakeup_granularity_ns", int, 100000, 100000000, backend="sysctl", path="kernel.sched_wakeup_granularity_ns"))
    
    # 2. Setup Components
    validator = Validator(registry)
    backend = DemoMockBackend() # Using mock for safety during demo
    writer = Writer(registry, backend=backend)
    rollback_stack = RollbackStack()
    profile_store = ProfileStore()
    
    # Load some dummy profiles
    profile_store.save_profile("throughput", {"sched_min_granularity_ns": 10000000, "sched_wakeup_granularity_ns": 15000000})
    profile_store.save_profile("latency", {"sched_min_granularity_ns": 1000000, "sched_wakeup_granularity_ns": 2000000})

    controller = SchedulerController(registry, validator, writer, rollback_stack, profile_store)

    # Demo 1: Apply Parameters
    log.info(f"Initial State: {backend.state}")
    
    log.info("Applying parameters: sched_min_granularity_ns=5000000")
    controller.apply_parameters({"sched_min_granularity_ns": 5000000})
    log.info(f"State after apply: {backend.state}")
    
    # Demo 2: Rollback
    log.info("Rolling back...")
    controller.rollback()
    log.info(f"State after rollback: {backend.state}")
    
    # Demo 3: Profiles
    log.info("Applying profile: 'latency'")
    controller.apply_profile("latency")
    log.info(f"State after profile apply: {backend.state}")

    # Demo 4: Safety Baseline
    log.info("--- M2 Safety Baseline Demo ---")
    sec_validator = SecondaryValidator()
    
    is_safe = sec_validator.validate("kernel.sched_min_granularity_ns", 1000000)
    log.info(f"Secondary Validator check for valid value (1000000): {is_safe}")
    
    is_safe = sec_validator.validate("kernel.sched_min_granularity_ns", 1) # Too small
    log.info(f"Secondary Validator check for dangerously small value (1): {is_safe}")

    log.info("Starting Watchdog (timeout=1.0s)...")
    watchdog_triggered = False
    def on_timeout():
        nonlocal watchdog_triggered
        watchdog_triggered = True
        log.warning("Watchdog callback triggered! System assumed hung, rolling back.")
        controller.rollback()

    watchdog = Watchdog(on_timeout, timeout_sec=1.0)
    watchdog.start()
    
    log.info("Pinging watchdog...")
    watchdog.ping()
    time.sleep(0.5)
    log.info("Sleeping to simulate RL agent hang (1.2s)...")
    time.sleep(1.2)
    
    if watchdog_triggered:
        log.info(f"State after watchdog triggered rollback: {backend.state}")

    log.info("Demo complete.")

if __name__ == "__main__":
    main()
