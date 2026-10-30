import json
import os
import logging
import tempfile
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Default to a project-local path instead of volatile /tmp (§6.2)
_DEFAULT_CHECKPOINT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "safety_checkpoint.json",
)


class CheckpointManager:
    """Saves system state to disk to allow crash recovery.

    The checkpoint file stores the kernel parameter state *before* training
    began, so that a crash mid-training can be recovered from.

    By default the file is written to ``data/safety_checkpoint.json`` inside
    the project tree, with restrictive permissions (owner-only read/write)
    to prevent tampering (§6.2).
    """

    def __init__(self, checkpoint_path: str = _DEFAULT_CHECKPOINT_PATH):
        self.checkpoint_path = checkpoint_path
        # Ensure parent directory exists
        Path(self.checkpoint_path).parent.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, state: Dict[str, Any]) -> None:
        """Atomically write checkpoint with restrictive permissions."""
        try:
            # mkstemp creates an owner-only file before any state is written.
            fd, tmp_path = tempfile.mkstemp(dir=Path(self.checkpoint_path).parent,
                                             prefix=".safety-checkpoint-")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(state, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, self.checkpoint_path)
                directory = os.open(Path(self.checkpoint_path).parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            logger.debug("Checkpoint saved to %s", self.checkpoint_path)
        except IOError as e:
            logger.error("Failed to save checkpoint: %s", e)
            raise

    def load_checkpoint(self) -> Dict[str, Any]:
        if not os.path.exists(self.checkpoint_path):
            return {}
        try:
            with open(self.checkpoint_path, 'r') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.error("Failed to load checkpoint: %s", e)
            return {}

    def clear_checkpoint(self) -> None:
        if os.path.exists(self.checkpoint_path):
            os.remove(self.checkpoint_path)
