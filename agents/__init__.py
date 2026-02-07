"""
SOTA Agents

Flare-based agents for decentralized task execution.
"""

__version__ = "0.2.0"
__author__ = "SOTA Protocol"

# Lazy-load agent types to avoid import-time failures when optional deps are missing.
def __getattr__(name):
    if name in {"ManagerAgent", "create_manager_agent"}:
        from agents.src.manager.agent import ManagerAgent, create_manager_agent
        return ManagerAgent if name == "ManagerAgent" else create_manager_agent
    if name in {"CallerAgent", "create_caller_agent"}:
        from agents.src.caller.agent import CallerAgent, create_caller_agent
        return CallerAgent if name == "CallerAgent" else create_caller_agent
    raise AttributeError(name)

__all__ = [
    "ManagerAgent",
    "CallerAgent",
    "create_manager_agent",
    "create_caller_agent",
]
