import logging
from typing import Any, Dict, Optional
from scheduler.registry import ParameterRegistry
from scheduler.backend import SchedulerBackend, SysctlBackend
from scheduler.exceptions import ReadbackError, WriteError

logger = logging.getLogger(__name__)

class Writer:
    def __init__(self, registry: ParameterRegistry, backend: Optional[SchedulerBackend] = None):
        self.registry = registry
        self.backends = {
            "sysctl": backend or SysctlBackend()
        }

    def write_and_verify(self, name: str, value: Any) -> None:
        meta = self.registry.get(name)
        backend = self.backends.get(meta.backend)
        if not backend:
            raise WriteError(f"Backend {meta.backend} not supported")
        
        backend.write(meta.path, value)

        read_val = backend.read(meta.path)
        try:
            read_val_cast = meta.type(read_val)
            if read_val_cast != meta.type(value):
                raise ReadbackError(f"Readback failed for {name}: expected {value}, got {read_val_cast}")
        except ValueError:
             raise ReadbackError(f"Readback failed for {name}: expected {value}, got {read_val} (uncastable)")
        
        logger.debug("Successfully wrote and verified %s=%s", name, value)
