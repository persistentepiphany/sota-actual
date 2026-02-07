"""SOTA Agents - Main Entry Point

Run individual agents or the full agent system on Flare.
"""

import os
import sys
import asyncio
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def run_butler_api():
    """Run the Flare Butler API (LangGraph-based)"""
    import uvicorn
    logger.info("🚀 Starting SOTA Butler API on port 3001...")
    uvicorn.run(
        "agents.flare_butler_api:app",
        host="0.0.0.0",
        port=int(os.environ.get("BUTLER_API_PORT", 3001)),
        reload=False,
    )


async def run_manager():
    """Run the Manager Agent server"""
    from agents.src.manager.server import run_server
    logger.info("🚀 Starting Manager Agent on port 3002...")
    run_server()


async def run_caller():
    """Run the Caller Agent server"""
    from agents.src.caller.server import run_server
    logger.info("🚀 Starting Caller Agent on port 3003...")
    run_server()


def main():
    parser = argparse.ArgumentParser(
        description="SOTA Agent Runner (Flare)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agents butler     # Run Butler API (default)
  python -m agents manager    # Run Manager Agent
  python -m agents caller     # Run Caller Agent
  python -m agents all        # Print multi-process instructions
        """
    )

    parser.add_argument(
        "agent",
        choices=["butler", "manager", "caller", "all"],
        help="Which agent to run"
    )

    parser.add_argument(
        "--port",
        type=int,
        help="Override default port for the agent"
    )

    args = parser.parse_args()

    # Set port override
    if args.port:
        if args.agent == "butler":
            os.environ["BUTLER_API_PORT"] = str(args.port)
        elif args.agent == "manager":
            os.environ["MANAGER_PORT"] = str(args.port)
        elif args.agent == "caller":
            os.environ["CALLER_PORT"] = str(args.port)

    # Run selected agent
    if args.agent == "butler":
        asyncio.run(run_butler_api())
    elif args.agent == "manager":
        asyncio.run(run_manager())
    elif args.agent == "caller":
        asyncio.run(run_caller())
    elif args.agent == "all":
        print("""
To run all agents, use separate terminal windows:

Terminal 1:  python -m agents butler   # Butler API (port 3001)
Terminal 2:  python -m agents manager   # Manager (port 3002)
Terminal 3:  python -m agents caller    # Caller  (port 3003)

Or use Docker Compose:  docker compose up
        """)
        sys.exit(0)


if __name__ == "__main__":
    main()
