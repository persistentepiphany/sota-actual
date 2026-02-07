"""
CV Magic Agent — Job Scouring for SOTA Marketplace

This agent searches job boards based on user CVs/resumes and preferences,
returning scored and filtered job listings.
"""

from .agent import CVMagicAgent, create_cv_magic_agent

__all__ = ["CVMagicAgent", "create_cv_magic_agent"]
