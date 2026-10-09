"""Productivity routing and governed execution tool APIs."""

from .productivity_router import ToolCandidate, ToolSelection, ProductivityRouter
from .execution_fabric import (
    AuditEvent,
    AuditLedger,
    ExecutionGateway,
    Principal,
    SAFE_TEST_PATTERNS,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    build_default_gateway,
)
from .research_adapters import GitHubRepositorySearchProvider, LocalRepositorySearchProvider

__all__ = [
    "AuditEvent", "AuditLedger", "ExecutionGateway", "GitHubRepositorySearchProvider",
    "LocalRepositorySearchProvider", "Principal", "ProductivityRouter", "SAFE_TEST_PATTERNS",
    "ToolCandidate", "ToolRegistry", "ToolResult", "ToolSelection", "ToolSpec",
    "build_default_gateway",
]
