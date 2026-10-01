import asyncio
import sys

from emberwake.app import main


def run() -> None:
    asyncio.run(main(sys.argv[1:]))


if __name__ == "__main__":
    run()
