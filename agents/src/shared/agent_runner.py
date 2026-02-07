"""
Agent Runner — OpenAI-powered tool-calling agent loop.

Replaces spoon_ai.agents.toolcall.ToolCallAgent and spoon_ai.chat.ChatBot
with a clean implementation backed by the OpenAI Chat Completions API.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from .tool_base import ToolManager

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
#  LLM Client
# ──────────────────────────────────────────────────────────────

class LLMClient:
    """
    Thin wrapper around ``openai.AsyncOpenAI`` for chat completions
    with function calling support.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        temperature: float = 0.3,
    ):
        self.model = model
        self.temperature = temperature
        self._client = AsyncOpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    async def chat(
        self,
        messages: List[dict],
        tools: List[dict] | None = None,
    ) -> Any:
        """
        Send a chat completion request and return the raw response.
        """
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0]


# ──────────────────────────────────────────────────────────────
#  AgentRunner
# ──────────────────────────────────────────────────────────────

class AgentRunner:
    """
    Autonomous tool-calling agent loop.

    1. Send ``system_prompt`` + user message to the LLM.
    2. If the LLM returns tool calls → execute them, feed results back.
    3. Repeat until the LLM emits a text response or ``max_steps`` is reached.

    This is the direct replacement for ``spoon_ai.agents.toolcall.ToolCallAgent``.
    """

    def __init__(
        self,
        *,
        name: str = "agent",
        description: str = "",
        system_prompt: str = "You are a helpful AI assistant.",
        next_step_prompt: str = "",
        max_steps: int = 10,
        tools: ToolManager | None = None,
        llm: LLMClient | None = None,
    ):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.next_step_prompt = next_step_prompt
        self.max_steps = max_steps
        self.tools = tools or ToolManager()
        self.llm = llm or LLMClient()

    async def run(self, user_message: str) -> str:
        """
        Execute the full agent loop for a single user message.

        Returns the final text response from the LLM.
        """
        messages: List[dict] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]

        openai_tools = self.tools.to_openai_tools() or None

        for step in range(self.max_steps):
            logger.debug("[%s] step %d/%d", self.name, step + 1, self.max_steps)

            choice = await self.llm.chat(messages, tools=openai_tools)
            msg = choice.message

            # ── Text response → done ────────────────────────
            if msg.content and not msg.tool_calls:
                logger.debug("[%s] final text response", self.name)
                return msg.content

            # ── Tool calls → execute each ───────────────────
            if msg.tool_calls:
                # Append the assistant message with tool_calls
                messages.append(msg.model_dump())

                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    fn_args = tc.function.arguments
                    logger.info("[%s] calling tool: %s", self.name, fn_name)

                    result = await self.tools.call(fn_name, fn_args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                continue

            # ── No content and no tool calls → done ─────────
            return msg.content or ""

        logger.warning("[%s] max steps (%d) reached", self.name, self.max_steps)
        return "I've reached my step limit. Please try rephrasing your request."

    async def run_with_history(
        self,
        user_message: str,
        history: List[dict],
    ) -> dict:
        """
        Like :meth:`run` but accepts a pre-existing conversation history.
        The system prompt is prepended automatically if not already present.

        Returns a dict with:
          - "response": str — the final text from the LLM
          - "tool_results": list[dict] — raw results from each tool call
        """
        messages: List[dict] = []
        if not history or history[0].get("role") != "system":
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        openai_tools = self.tools.to_openai_tools() or None
        tool_results: List[dict] = []

        for step in range(self.max_steps):
            choice = await self.llm.chat(messages, tools=openai_tools)
            msg = choice.message

            if msg.content and not msg.tool_calls:
                logger.info("[%s] step %d → text response (len=%d)", self.name, step+1, len(msg.content))
                return {"response": msg.content, "tool_results": tool_results}

            if msg.tool_calls:
                messages.append(msg.model_dump())
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    logger.info("[%s] step %d → tool call: %s", self.name, step+1, fn_name)
                    print(f"🔧 [{self.name}] calling tool: {fn_name}")
                    result = await self.tools.call(tc.function.name, tc.function.arguments)
                    tool_results.append({"tool": fn_name, "result": result})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                continue

            return {"response": msg.content or "", "tool_results": tool_results}

        return {"response": "I've reached my step limit. Please try rephrasing your request.", "tool_results": tool_results}
