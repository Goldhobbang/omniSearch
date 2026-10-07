"""MCP stdio 서버: Claude Code / opencode 등에서 검색 도구로 사용.
설치: pip install "omnisearch[mcp]"   실행: omnisearch-mcp
"""
from mcp.server.mcpserver import MCPServer

from . import __version__, core

mcp = MCPServer("omnisearch", version=__version__)


@mcp.tool()
def search(query: str) -> dict:
    """Keyless web search. Routes the query (entity, paper, news, Korean slang, ...)
    to the best free engine and returns the top results with a relevance score."""
    return core.search(query)


@mcp.tool()
def multi_search(query: str) -> dict:
    """Run every engine in the query's chain and return all results grouped per
    engine, sorted by relevance. Use for ambiguous names with several meanings."""
    return core.multi_search(query)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
