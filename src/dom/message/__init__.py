from typing import Literal
from dataclasses import dataclass


@dataclass
class BaseMessage:
    role: Literal['system', 'user', 'assistant', 'tool']
