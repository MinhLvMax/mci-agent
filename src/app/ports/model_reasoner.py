from typing import Protocol
from src.dom.decision import Decision
from src.dom.context import Context
from src.dom.tool import Tool


class ModelReasoner(Protocol):
    def decide(self, context: Context, tools: list[Tool]) -> Decision:
        '''Quyết định bước tiếp theo cần phải làm gì, có nhiều phiên bản triển khai nên nó là Port'''
