# MCP Atlassian Server v1

This is the MCP (Model Context Protocol) server implementation for Atlassian products (Jira and Confluence).

## Overview

The MCP Atlassian Server provides a standardized interface for AI language models to interact with Atlassian tools following Anthropic's MCP specification. It exposes Jira and Confluence operations as MCP tools.

## Installation

```bash
cd mcp_server
uv sync --frozen --all-extras --dev
# Or using pip
pip install -r requirements.txt
```

## Running the Server

### Using the CLI

```bash
# STDIO transport (default)
uv run mcp-atlassian

# HTTP transport
uv run mcp-atlassian --transport streamable-http --port 8000 --host 0.0.0.0

# With verbose logging
uv run mcp-atlassian -vv
```

### Using the scripts

```bash
# Start server with environment variables
./start_mcp_server_with_env.sh

# Run tests
./test_mcp_server.sh
```

## Configuration

Set environment variables or use `.env` file:

### Core Configuration

- `JIRA_URL`: Your Jira instance URL
- `JIRA_USERNAME`: Username for authentication
- `JIRA_API_TOKEN`: API token for Jira Cloud
- `JIRA_PERSONAL_TOKEN`: Personal Access Token for Server/DC
- `READ_ONLY_MODE`: Set to `true` to disable write operations
- `TRANSPORT`: `stdio`, `sse`, or `streamable-http`
- `PORT`: Port for HTTP transports (default: 8000)

**Note on Session Management:**

FastMCP handles session management internally. The server uses validation bypass patches to allow all requests without session ID validation. No custom session management or database setup is required.

See `CREDENTIALS_SETUP.md` for detailed authentication setup and `FASTMCP_FIXES.md` for details on how session management works.

## Development

```bash
# Install dev dependencies
uv sync --frozen --all-extras --dev

# Run tests
uv run pytest

# Linting and type checking
pre-commit run --all-files
```

## Architecture

- `src/mcp_atlassian/`: Core library code
  - `jira/`: Jira client and operations
  - `models/`: Pydantic data models
  - `servers/`: FastMCP server implementation
    - `main.py`: Main server setup with FastMCP validation bypass
    - `jira.py`: Jira-specific tools and operations
    - `context.py`: Application context
  - `utils/`: Shared utilities

- `scripts/`: OAuth setup and testing scripts
- `tests/`: Test suite

## Session Management

FastMCP handles session management internally. The server uses validation bypass patches to allow all requests without requiring session ID validation. This simplifies the architecture and removes the need for custom session management.

For details on how FastMCP sessions work, see `FASTMCP_FIXES.md`.

For more details, see `AGENTS.md` and `CONTRIBUTING.md`.
