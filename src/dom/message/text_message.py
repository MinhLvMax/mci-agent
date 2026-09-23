from dataclasses import dataclass
from src.dom.message import BaseMessage


@dataclass
class TextMessage(BaseMessage):
    content: str
