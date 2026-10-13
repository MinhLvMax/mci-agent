from dataclasses import dataclass
from typing import Protocol, Generator
from src.dom.decision import Decision
from src.dom.context import Context
from src.dom.tool import Tool
from src.dom.agent_event import AgentEvent


class ModelReasoner(Protocol):
    def decide(self, context: Context, tools: list[Tool]) -> Decision:
        '''Quyết định bước tiếp theo cần phải làm gì, có nhiều phiên bản triển khai nên nó là Port'''

    def decide_stream(self, context: Context, tools: list[Tool]) -> Generator[AgentEvent, None, Decision]:
        '''
        Giống decide nhưng yield dần các AgentEvent (thinking, content) trong lúc model sinh chữ,
        hết stream thì return Decision. Bên gọi dùng: decision = yield from reasoner.decide_stream(...)
        '''


class ModelUnavailableError(Exception):
    '''
    Model người dùng chọn không gọi được vì cấu hình sai: tên model, chế độ suy luận,
    nhà cung cấp hoặc API key. message là câu tiếng Việt để hiện thẳng cho người dùng.
    '''


@dataclass(frozen=True)
class ProviderInfo:
    '''Một nhà cung cấp model đã có adapter: name lưu ở cột models.provider, label hiện trên giao diện'''
    name: str
    label: str
