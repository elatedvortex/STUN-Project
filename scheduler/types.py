from dataclasses import dataclass
from typing import Any, Dict, Optional, List, Union

@dataclass
class ParameterMeta:
    name: str
    type: type
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    description: str = ""
    backend: str = "sysctl"
    path: str = ""
