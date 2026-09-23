from pydantic import BaseModel
from abc import ABC, abstractmethod


class ToolKwargs(BaseModel):
    '''Tool nào nhận tham số gì thì phải tự thừa kế và triển khai riêng'''
    ...


class ToolResult(ABC):
    '''Tool nào trả về gì thì tự thừa kế và khai báo riêng'''

    @abstractmethod
    def to_text(self) -> str:
        '''Mỗi kết quả tool phải tự biết cách biểu diễn mình thành chuỗi'''
        ...


class Tool(ABC):
    '''Một tool mới được khai báo thì phải tự thừa kế và triển khai theo quy tắc'''
    tool_name: str
    tool_description: str
    tool_kwargs: type[ToolKwargs]

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        ...
