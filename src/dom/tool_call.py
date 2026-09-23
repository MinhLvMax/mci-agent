from dataclasses import dataclass


@dataclass
class ToolCall:
    '''Các tool call phải tuân theo hợp đồng này'''
    tool_call_id: str
    name: str
    kwargs: dict
