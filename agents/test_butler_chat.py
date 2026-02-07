"""
Quick Butler Agent smoke-test.

Usage:
    cd agents
    python test_butler_chat.py
"""

import asyncio
import os
import sys
import logging

# Ensure project root is on path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)
logger = logging.getLogger("test_butler")


async def main():
    # ── Pre-flight checks ────────────────────────────────────
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("sk-proj-xxx"):
        print("❌ OPENAI_API_KEY is not set in .env")
        sys.exit(1)

    private_key = os.getenv("FLARE_PRIVATE_KEY", "")
    if not private_key:
        # Generate a throwaway key so we can still test the LLM loop
        # (no real on-chain tx will happen)
        print("⚠️  FLARE_PRIVATE_KEY not set — using dummy key (no on-chain ops)")
        os.environ["FLARE_PRIVATE_KEY"] = "0x" + "ab" * 32

    # ── Create agent ─────────────────────────────────────────
    from agents.src.butler.agent import ButlerAgent

    butler = ButlerAgent()
    print(f"✅ Butler Agent created  (model={butler.model})")
    print(f"   Tools loaded: {[t.name for t in butler.tool_manager.tools]}")
    print()

    # ── Interactive chat loop ────────────────────────────────
    print("💬 Chat with the Butler  (type 'quit' to exit)")
    print("─" * 50)

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break

        print("⏳ Thinking…")
        response = await butler.chat(user_input)
        print(f"\n🤖 Butler: {response}")

    print("\n👋 Done.")


if __name__ == "__main__":
    asyncio.run(main())
