from typing import Any, Dict
from scheduler.registry import ParameterRegistry
from scheduler.exceptions import ValidationError, ParameterNotFoundError

class Validator:
    def __init__(self, registry: ParameterRegistry):
        self.registry = registry

    def validate(self, params: Dict[str, Any]) -> None:
        for name, value in params.items():
            try:
                meta = self.registry.get(name)
            except ParameterNotFoundError as e:
                raise ValidationError(str(e))
            
            try:
                value_cast = meta.type(value)
            except (ValueError, TypeError):
                raise ValidationError(f"Parameter {name} should be {meta.type.__name__}, got {type(value).__name__}")
            
            if meta.min_value is not None and value_cast < meta.min_value:
                raise ValidationError(f"Parameter {name} value {value_cast} is less than min {meta.min_value}")
            if meta.max_value is not None and value_cast > meta.max_value:
                raise ValidationError(f"Parameter {name} value {value_cast} is greater than max {meta.max_value}")
