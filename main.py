"""Browser (pygbag) entry point. Desktop players use the `emberwake` command instead."""

import asyncio
import sys
from pathlib import Path

src = Path(__file__).parent / "src"
if src.is_dir():
    sys.path.insert(0, str(src))

from emberwake.app import main  # noqa: E402

asyncio.run(main())
