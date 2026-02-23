"""
Intent detection for classifying user queries.

Analyzes user messages to determine what action they want to perform:
- Analyze a specific application
- Show lists of applications (bad, recent, driver-heavy, etc.)
- Analyze skew or scaling for specific apps
- General chat/questions
"""
import re
from typing import Dict, Any, Optional


def extract_application_id(message: str) -> Optional[str]:
    """
    Extract Spark application ID from message text.
    
    Supports formats:
    - application_1771438258399_0001
    - app 12345
    - application-12345
    
    Args:
        message: User message text
        
    Returns:
        Extracted application ID or None if not found
    """
    message_lower = message.lower()
    
    # Pattern for full application ID format: application_TIMESTAMP_INDEX
    full_match = re.search(r'(application[_\s-]+\d+[_\s-]+\d+)', message, re.IGNORECASE)
    if full_match:
        return full_match.group(1).replace(" ", "_").replace("-", "_")
    
    # Fallback patterns for partial IDs
    patterns = [
        r'app[_\s-]*(\d+)',
        r'application[_\s-]*(\d+)',
        r'spark[_\s-]*app[_\s-]*(\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message_lower)
        if match:
            return f"application_{match.group(1)}"
    
    return None


def detect_intent(message: str) -> Dict[str, Any]:
    """
    Classify user message intent using keyword matching and regex.
    
    Priority order:
    1. Analyze skew (for specific app)
    2. Analyze scaling (for specific app)
    3. Analyze application
    4. Show various app lists (bad, recent, driver-heavy, etc.)
    5. General chat
    
    Args:
        message: User message text
    
    Returns:
        Dictionary with "intent" and "params" keys
    """
    message_lower = message.lower()
    
    # INTENT: analyze_skew (high priority - check first)
    skew_triggers = [
        "skew", "imbalance", "task imbalance", "shuffle imbalance",
        "data skew", "partition skew", "skewed data", "skewed partitions",
        "uneven distribution", "straggler", "stragglers"
    ]
    if any(trigger in message_lower for trigger in skew_triggers):
        app_id = extract_application_id(message)
        if app_id:
            return {
                "intent": "analyze_skew",
                "params": {"application_id": app_id}
            }
    
    # INTENT: analyze_scaling (high priority)
    scaling_patterns = [
        r'\badd(?:ing)?\s+(?:more\s+)?executors?\b',
        r'\bmore\s+executors?\b',
        r'\bscal(?:e|ing)\s+(?:up|down|out)?\b',
        r'\bwill\s+scaling\s+help\b',
        r'\bshould\s+(?:i|we)\s+scale\b',
        r'\b(?:add(?:ing)?|more|fewer|less)\s+(?:resources?|nodes?|executors?)\b',
        r'\b(?:increase|reduce|decrease)\s+(?:executors?|nodes?|resources?)\b',
        r'\bexecutor\s+count\b',
    ]
    
    if any(re.search(pattern, message_lower) for pattern in scaling_patterns):
        app_id = extract_application_id(message)
        if app_id:
            return {
                "intent": "analyze_scaling",
                "params": {"application_id": app_id}
            }
    
    # INTENT: analyze_app
    analyze_triggers = [
        "analyze", "recommendations for", "what issues",
        "best practices for", "check app", "review app"
    ]
    if any(trigger in message_lower for trigger in analyze_triggers):
        app_id = extract_application_id(message)
        if app_id:
            return {
                "intent": "analyze_app",
                "params": {"application_id": app_id}
            }
    
    # INTENT: show_bad_apps
    bad_triggers = [
        "bad apps", "which apps have issues", "problem applications",
        "apps with errors", "show issues", "worst apps",
        "poor coding", "bad practices"
    ]
    if any(trigger in message_lower for trigger in bad_triggers):
        return {
            "intent": "show_bad_apps",
            "params": {"min_violations": 3}
        }
    
    # INTENT: show_recent_apps
    show_all_pattern = re.compile(
        r'\b(show|list|get|display)\s+(me\s+)?(all|every)\s+(the\s+)?(\w+\s+)?(apps?|applications?)\b'
    )
    if show_all_pattern.search(message_lower):
        hours = 24 * 7  # Default to last 7 days for "all apps"
        hours = _extract_time_period(message_lower, default=hours)
        return {
            "intent": "show_recent_apps",
            "params": {"hours": hours}
        }
    
    recent_triggers = [
        "ran today", "executed today", "today's apps", "applications today",
        "show today", "recent apps", "recent applications", "recently ran"
    ]
    if any(trigger in message_lower for trigger in recent_triggers):
        hours = _extract_time_period(message_lower, default=24)
        return {
            "intent": "show_recent_apps",
            "params": {"hours": hours}
        }
    
    # INTENT: show_driver_heavy
    driver_triggers = [
        "driver heavy", "driver intensive", "high driver",
        "driver cpu", "driver memory", "driver jobs",
        "driver overhead", "driver bottleneck"
    ]
    if any(trigger in message_lower for trigger in driver_triggers):
        return {
            "intent": "show_driver_heavy",
            "params": {"metric": "driver"}
        }
    
    # INTENT: show_memory_intensive
    memory_triggers = [
        "memory intensive", "memory issues", "oom", "out of memory",
        "memory spill", "high memory", "executor memory"
    ]
    if any(trigger in message_lower for trigger in memory_triggers):
        return {
            "intent": "show_memory_intensive",
            "params": {"metric": "memory"}
        }
    
    # INTENT: show_shuffle_issues
    shuffle_triggers = [
        "shuffle spill", "shuffle issues", "bad shuffle",
        "shuffle heavy", "high shuffle", "shuffle problems"
    ]
    if any(trigger in message_lower for trigger in shuffle_triggers):
        return {
            "intent": "show_shuffle_issues",
            "params": {"metric": "shuffle"}
        }
    
    # INTENT: show_best_practice_apps
    best_triggers = [
        "best practices", "follow best", "healthy apps",
        "well optimized", "good apps", "no issues",
        "clean apps", "compliant apps", "green apps"
    ]
    if any(trigger in message_lower for trigger in best_triggers):
        return {
            "intent": "show_best_practice_apps",
            "params": {"min_score": 80}
        }
    
    # Default: general_chat
    return {
        "intent": "general_chat",
        "params": {}
    }


def _extract_time_period(message_lower: str, default: int = 24) -> int:
    """
    Extract time period in hours from message.
    
    Args:
        message_lower: Lowercased message text
        default: Default hours if not specified
    
    Returns:
        Number of hours
    """
    hour_match = re.search(r'last\s+(\d+)\s+hour', message_lower)
    day_match = re.search(r'last\s+(\d+)\s+day', message_lower)
    week_match = re.search(r'last\s+(\d+)\s+week', message_lower)
    
    if hour_match:
        return int(hour_match.group(1))
    elif day_match:
        return int(day_match.group(1)) * 24
    elif week_match:
        return int(week_match.group(1)) * 24 * 7
    elif any(x in message_lower for x in ["today", "ran today", "executed today"]):
        return 24
    
    return default
