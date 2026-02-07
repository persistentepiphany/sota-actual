"""
CV Magic Services — Core functionality for job scouring.
"""

from .models import UserProfileForScouring, ScouredJob, ScourPreferences
from .document_text import extract_text_from_bytes, ExtractedText

__all__ = [
    "UserProfileForScouring",
    "ScouredJob", 
    "ScourPreferences",
    "extract_text_from_bytes",
    "ExtractedText",
]
