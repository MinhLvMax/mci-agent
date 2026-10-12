from dataclasses import dataclass
from typing import Literal

from pydantic import Field

from src.app.services.memory_service import MemoryService
from src.dom.tool import Tool, ToolKwargs, ToolResult


class RememberToolKwargs(ToolKwargs):
    content: str = Field(
        description=(
            "The lesson to remember, written as a short, self-contained instruction in the user's language "
            "(e.g. 'Always answer with bullet points', 'Prices must be in VND'). "
            "Must make sense without the current conversation."
        )
    )
    scope: Literal['user', 'org'] = Field(
        default='user',
        description=(
            "'user' = personal preference of the current user, applied immediately. "
            "'org' = rule for the whole company (shared terminology, processes, facts about the business); "
            "it becomes a proposal that an admin must approve."
        )
    )
    replace_memory_id: int | None = Field(
        default=None,
        description="Id (the number after #) of an existing memory that this one updates or corrects, if any."
    )


@dataclass
class RememberToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class RememberTool(Tool):
    tool_name = 'remember'
    tool_description = (
        "Save a long-term memory that will be included in future conversations. "
        "Use it when the user states a preference, corrects you, or describes how things should be done next time. "
        "When the user asks you to remember or note something for later (e.g. 'ghi nhớ', 'nhớ giúp', "
        "'cập nhật ghi nhớ', 'lần sau'), you MUST call this tool. Never use workspace files as memory: "
        "files are not read in future conversations. "
        "Do not save one-off task details, secrets, or anything already listed in the long-term memory section."
    )

    tool_kwargs = RememberToolKwargs

    def __init__(self, memory_service: MemoryService, user_id: int, conversation_id: int | None = None):
        # user_id lấy từ token ở router, model không tự khai được
        self._memory_service = memory_service
        self._user_id = user_id
        self._conversation_id = conversation_id

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        memory = self._memory_service.remember(
            user_id=self._user_id,
            scope=args.scope,
            content=args.content,
            source='tool',
            conversation_id=self._conversation_id,
            replace_memory_id=args.replace_memory_id,
        )

        if memory.scope == 'org':
            return RememberToolResult(
                content=f"Proposed company-wide memory #{memory.id}; it will apply after an admin approves it."
            )

        return RememberToolResult(content=f"Saved personal memory #{memory.id}: {memory.content}")
