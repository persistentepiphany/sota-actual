"""
Tool Base — Local tool abstractions for SOTA agents.

Replaces spoon_ai.tools.base.BaseTool and spoon_ai.tools.ToolManager
with a minimal, OpenAI-function-calling-compatible implementation.
"""

from __future__ import annotations

import json
import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  BaseTool
# ──────────────────────────────────────────────────────────────

class BaseTool(BaseModel, ABC):
    """
    Abstract base for every agent tool.

    Subclasses MUST define:
      - name:        unique tool identifier
      - description: what the tool does (shown to the LLM)
      - parameters:  JSON Schema dict for the tool's arguments
      - execute(**kwargs) -> str:  async implementation
    """

    name: str = ""
    description: str = ""
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {},
        "required": [],
    })

    class Config:
        arbitrary_types_allowed = True

    # ── OpenAI function-calling schema ──────────────────────

    def to_openai_function(self) -> dict:
        """Return the OpenAI `tools` entry for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description.strip(),
                "parameters": self.parameters,
            },
        }

    # ── Execution ───────────────────────────────────────────

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """Run the tool and return a JSON-serialisable string result."""
        ...

    async def __call__(self, **kwargs: Any) -> str:
        return await self.execute(**kwargs)


# ──────────────────────────────────────────────────────────────
#  ToolManager
# ──────────────────────────────────────────────────────────────

class ToolManager:
    """
    Registry that holds a collection of :class:`BaseTool` instances.

    Provides:
    * ``to_openai_tools()`` — list of OpenAI function schemas
    * ``call(name, arguments_json)`` — dispatch + execute a tool by name
    """

    def __init__(self, tools: Sequence[BaseTool] | None = None):
        self._tools: Dict[str, BaseTool] = {}
        for t in tools or []:
            self.register(t)

    # ── Registration ────────────────────────────────────────

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            logger.warning("Overwriting existing tool: %s", tool.name)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    @property
    def tools(self) -> List[BaseTool]:
        return list(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def __iter__(self):
        return iter(self._tools.values())

    # ── OpenAI integration ──────────────────────────────────

    def to_openai_tools(self) -> List[dict]:
        """List of tool schemas suitable for ``openai.chat.completions.create(tools=...)``."""
        return [t.to_openai_function() for t in self._tools.values()]

    # ── Dispatch ────────────────────────────────────────────

    async def call(self, name: str, arguments: str | dict) -> str:
        """
        Look up a tool by *name*, parse *arguments* (JSON string or dict),
        call ``execute(**kwargs)`` and return the string result.
        """
        tool = self._tools.get(name)
        if tool is None:
            return json.dumps({"error": f"Unknown tool: {name}"})

        # Parse arguments
        if isinstance(arguments, str):
            try:
                kwargs = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError:
                return json.dumps({"error": f"Invalid JSON arguments for {name}"})
        else:
            kwargs = arguments or {}

        # Execute
        try:
            result = await tool.execute(**kwargs)
            return result
        except Exception as exc:
            logger.exception("Tool %s raised an exception", name)
            return json.dumps({"error": f"Tool {name} failed: {exc}"})
