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
