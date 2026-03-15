import sys
sys.path.append('.')

import asyncio
from prometheos.tools.mcp_client import MCPClient

async def main():
    client = MCPClient("local-core")
    await client.start()
    await client.wait_for_connection(timeout=10)

    try:
        # List tools
        tools = await client.list_tools()
        print(f"Available tools: {[tool.name for tool in tools]}")

        # Call web_browse
        browse_result = await client.call_tool(
            "web_browse",
            {"url": "https://www.google.com"}
        )
        print("\n--- Web Browse Result ---")
        print(browse_result)

    finally:
        await client.stop()

if __name__ == "__main__":
    asyncio.run(main())