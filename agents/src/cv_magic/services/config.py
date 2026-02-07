"""
Configuration for CV Magic Agent.

Simplified from the original cv-magic backend config,
removing Firebase/Dropbox dependencies.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    """CV Magic agent settings"""
    
    # OpenAI
    OPENAI_API_KEY: Optional[str]
    OPENAI_MODEL: str
    OPENAI_PROFILE_MAX_INPUT_CHARS: int
    
    # BrightData (for web scraping)
    BRIGHT_DATA_API_KEY: Optional[str]
    BRIGHT_DATA_USERNAME: Optional[str]
    BRIGHT_DATA_COUNTRY: str
    
    # Limits
    MAX_UPLOAD_BYTES: int
    
    # Cache
    DATA_ENCRYPTION_KEY: Optional[str]
    ALLOW_PLAINTEXT_CACHE: bool


def _as_bool(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(value: Optional[str], default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def get_settings() -> Settings:
    """Get CV Magic settings from environment variables"""
    max_upload_mb = _as_int(os.getenv("MAX_UPLOAD_MB"), 20)
    max_upload_bytes = max_upload_mb * 1024 * 1024
    
    return Settings(
        # OpenAI
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        OPENAI_MODEL=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        OPENAI_PROFILE_MAX_INPUT_CHARS=_as_int(os.getenv("OPENAI_PROFILE_MAX_INPUT_CHARS"), 20000),
        
        # BrightData
        BRIGHT_DATA_API_KEY=os.getenv("BRIGHT_DATA_API_KEY"),
        BRIGHT_DATA_USERNAME=os.getenv("BRIGHT_DATA_USERNAME"),
        BRIGHT_DATA_COUNTRY=os.getenv("BRIGHT_DATA_COUNTRY", ""),
        
        # Limits
        MAX_UPLOAD_BYTES=max_upload_bytes,
        
        # Cache
        DATA_ENCRYPTION_KEY=os.getenv("DATA_ENCRYPTION_KEY"),
        ALLOW_PLAINTEXT_CACHE=_as_bool(os.getenv("ALLOW_PLAINTEXT_CACHE")),
    )
