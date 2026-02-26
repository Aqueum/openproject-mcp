"""Entry point: python -m openproject_mcp"""

import asyncio
from openproject_mcp.server import main

if __name__ == "__main__":
    asyncio.run(main())
