import argparse
import asyncio
import sys

from app.agent.manus import Manus
from app.logger import logger


async def main():
    parser = argparse.ArgumentParser(description="Run Manus agent with a prompt")
    parser.add_argument("--prompt", type=str, required=False)
    args = parser.parse_args()

    agent = None
    try:
        agent = await Manus.create()

        while True:
            try:
                prompt = args.prompt if args.prompt else input("Enter your prompt: ")
                args.prompt = None  # only once

                if not prompt.strip():
                    logger.warning("Empty prompt.")
                    continue

                logger.info("Processing your request...")
                await agent.run(prompt)
                logger.info("Done.")

            except KeyboardInterrupt:
                logger.warning("Interrupted by user.")
                return

            except Exception as e:
                logger.exception("Runtime error occurred")

                # 🔴 USER CHOICE
                choice = input("Error occurred. Continue? [y/N]: ").strip().lower()
                if choice != "y":
                    return

    finally:
        if agent:
            try:
                await agent.cleanup()
            except Exception:
                logger.exception("Cleanup failed")


def run():
    asyncio.run(main())


if __name__ == "__main__":
    # ❌ no supervisor for interactive mode
    run()
