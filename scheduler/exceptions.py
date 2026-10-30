class SchedulerError(Exception):
    """Base exception for scheduler module."""
    pass

class ParameterNotFoundError(SchedulerError):
    pass

class ValidationError(SchedulerError):
    pass

class WriteError(SchedulerError):
    pass

class ReadbackError(SchedulerError):
    pass


class RecoveryError(SchedulerError):
    """Restoration failed; stop tuning and retain recovery state for retry."""
