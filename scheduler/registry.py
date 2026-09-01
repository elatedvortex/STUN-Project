from typing import Dict, List, Optional
from scheduler.types import ParameterMeta
from scheduler.exceptions import ParameterNotFoundError

class ParameterRegistry:
    def __init__(self):
        self._parameters: Dict[str, ParameterMeta] = {}

    def register(self, param: ParameterMeta) -> None:
        self._parameters[param.name] = param

    def get(self, name: str) -> ParameterMeta:
        if name not in self._parameters:
            raise ParameterNotFoundError(f"Parameter {name} not found in registry")
        return self._parameters[name]

    def get_all(self) -> List[ParameterMeta]:
        return list(self._parameters.values())

    def clear(self) -> None:
        self._parameters.clear()
