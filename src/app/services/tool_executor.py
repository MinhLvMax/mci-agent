from src.dom.tool import Tool, ToolResult


class ToolExecutor:
    def __init__(self, tools: list[Tool]):
        self.tools = tools
        self._tool_map = {
            tool.tool_name: tool
            for tool in tools
        }

    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        '''Gọi 1 tool và thực thi tool đó'''
        tool = self._tool_map[tool_name]
        return tool.execute(**kwargs)
