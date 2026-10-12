from dataclasses import dataclass

from pydantic import Field

from src.app.services.memory_service import MemoryService
from src.dom.tool import Tool, ToolKwargs, ToolResult


class ForgetToolKwargs(ToolKwargs):
    memory_id: int = Field(
        description="Id (the number after #) of the personal memory to remove."
    )


@dataclass
class ForgetToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class ForgetTool(Tool):
    tool_name = 'forget'
    tool_description = (
        "Remove one of the current user's personal memories when they no longer want it applied. "
        "Company-wide memories cannot be removed with this tool; tell the user to ask an admin."
    )

    tool_kwargs = ForgetToolKwargs

    def __init__(self, memory_service: MemoryService, user_id: int):
        self._memory_service = memory_service
        self._user_id = user_id

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        # Không phải memory của user thì MemoryPermissionError, ToolExecutor đổi thành lỗi dạng text cho model
        memory = self._memory_service.forget(user_id=self._user_id, memory_id=args.memory_id)
        return ForgetToolResult(content=f"Removed personal memory #{memory.id}.")
