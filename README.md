# FLATICON_MCP_TOOL

FastMCP server (hosted on Prefect Horizon) with one tool, `search_icons(query, count)`,
that returns PNG icons from Flaticon as images.

Entrypoint: `server.py:mcp`

`flaticon/` is a vendored, lightly patched copy of the `flaticon` 1.0.2 package (Apache-2.0),
because the PyPI release pins `aiohttp==3.8.4`, which can't build on Python 3.12.
