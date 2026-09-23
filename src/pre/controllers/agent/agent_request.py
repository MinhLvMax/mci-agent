'''Mô tả hợp đồng mà tầng pre nhận từ bên ngoài vào'''
'''Controller chấp nhận cái gì ở bên ngoài'''
from typing import Literal, TypeAlias
from pydantic import BaseModel
from src.dom.tool_call import ToolCall


class TextMessageRequest(BaseModel):
    role: Literal['assistant', 'user', 'system']
    content: str


class ToolCallMessageRequest(BaseModel):
    role: Literal['assistant']
    list_tool_call: list[ToolCall]


class ToolResultMessageRequest(BaseModel):
    role: Literal['tool']
    tool_call_id: str
    tool_result: str
    tool_name: str


MessageRequest: TypeAlias = (
        TextMessageRequest
        | ToolCallMessageRequest
        | ToolResultMessageRequest
)


class AgentRequest(BaseModel):
    messages: list[MessageRequest]
