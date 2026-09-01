from typing import Any, Dict, List

class RollbackStack:
    def __init__(self):
        self._stack: List[Dict[str, Any]] = []

    def push(self, state: Dict[str, Any]) -> None:
        self._stack.append(state)

    def pop(self) -> Dict[str, Any]:
        if not self._stack:
            return {}
        return self._stack.pop()
        
    def peek(self) -> Dict[str, Any]:
        if not self._stack:
            return {}
        return self._stack[-1]

    def clear(self) -> None:
        self._stack.clear()
