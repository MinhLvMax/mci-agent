from dataclasses import dataclass

from pydantic import ValidationError

from src.dom.tool import Tool, ToolResult
from src.config import Config


@dataclass
class ToolErrorResult(ToolResult):
    '''Kết quả khi gọi tool thất bại, trả về dạng text để model tự sửa lời gọi'''
    content: str

    def to_text(self) -> str:
        return self.content


class ToolExecutor:
    def __init__(self, tools: list[Tool]):
        self.tools = tools
        self._tool_map = {
            tool.tool_name: tool
            for tool in tools
        }

    def execute_tool(self, tool_name: str, **kwargs) -> ToolResult:
        '''Gọi 1 tool và thực thi tool đó, lỗi thì trả về text thay vì làm hỏng vòng lặp agent'''
        tool = self._tool_map.get(tool_name)

        if tool is None:
            return ToolErrorResult(
                content=(
                    f"Unknown tool: {tool_name}. "
                    f"Available tools: {', '.join(self._tool_map)}"
                )
            )

        try:
            return tool.execute(**kwargs)

        except ValidationError as e:
            # Model truyền sai tham số, báo lại chi tiết để model gọi lại cho đúng
            return ToolErrorResult(
                content=f"Invalid arguments for tool '{tool_name}': {e}"
            )

        except Exception as e:
            Config.logger.exception(f'Tool {tool_name} failed')
            return ToolErrorResult(
                content=f"Tool '{tool_name}' failed: {type(e).__name__}: {e}"
            )
