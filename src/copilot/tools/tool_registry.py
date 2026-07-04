"""
tool_registry.py — Registry for AI tools.
"""

from typing import Dict, Any
from logger import get_logger
from tools.sql_tool import SQLTool

log = get_logger("tool_registry")

class ToolRegistry:
    """Registry to hold and provide access to tools."""
    def __init__(self):
        self._tools = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Register the built-in tools."""
        self.register_tool("sql_tool", SQLTool())
        
        # Future tools placeholders to be expanded as needed
        class DummyTool:
            def __init__(self, name):
                self.name = name
                
        self.register_tool("analytics_tool", DummyTool("AnalyticsTool"))
        self.register_tool("prediction_tool", DummyTool("PredictionTool"))
        self.register_tool("report_tool", DummyTool("ReportTool"))
        
        log.info("ToolRegistry initialized with default tools.")

    def register_tool(self, name: str, tool: Any):
        """Register a new tool."""
        self._tools[name] = tool

    def get_tool(self, name: str) -> Any:
        """Retrieve a tool by name."""
        if name not in self._tools:
            log.error("Tool '%s' not found in registry.", name)
            return None
        return self._tools[name]

# Singleton registry
registry = ToolRegistry()

def get_tool_registry() -> ToolRegistry:
    """Get the singleton ToolRegistry instance."""
    return registry
