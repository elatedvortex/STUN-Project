from typing import Dict, Any, Optional

class ProfileStore:
    def __init__(self):
        self._profiles: Dict[str, Dict[str, Any]] = {}

    def save_profile(self, name: str, params: Dict[str, Any]) -> None:
        self._profiles[name] = params

    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        return self._profiles.get(name)

    def list_profiles(self) -> list[str]:
        return list(self._profiles.keys())
