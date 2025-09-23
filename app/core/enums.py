from enum import Enum

class LogPrefixesEnum(str, Enum):
    """
    Enum for common log detail prefixes to avoid magic strings.
    
    Use these values for consistent filtering in log queries.
    """
    DUAL = "DUAL"
    TAMPER = "Tamper"
    FAILURE = "Failure"
    MANUAL = "Manual"
    ALARM = "Alarm"