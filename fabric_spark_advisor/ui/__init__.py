"""UI package for Gradio interface and formatters."""

from .formatters import (
    format_app_analysis,
    format_scaling_analysis,
    format_skew_analysis
)
from .intent import detect_intent

# Gradio is optional — only import if available
try:
    from .gradio_app import create_gradio_interface
    __all__ = [
        "format_app_analysis",
        "format_scaling_analysis",
        "format_skew_analysis",
        "create_gradio_interface",
        "detect_intent"
    ]
except ImportError:
    __all__ = [
        "format_app_analysis",
        "format_scaling_analysis",
        "format_skew_analysis",
        "detect_intent"
    ]
