# FLATICON_MCP_TOOL

FastMCP server (Prefect Horizon) with one tool, `search_icons(requests)`.
One request per line: `query,type,number` — type `I` icons, `S` stickers, `A` animated (GIF).

- Entrypoint: `server.py:mcp`
- Requirements: `requirements.txt` (installs offline from `wheels/`, built for Linux x86_64 / Python 3.12)

To go back to installing from PyPI, delete the first two lines of `requirements.txt`.

Rebuild the wheels:
    pip download -r requirements.txt -d wheels --only-binary=:all: --python-version 3.12 --implementation cp --abi cp312 --abi abi3 --abi none --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 --platform manylinux_2_28_x86_64 --platform any
