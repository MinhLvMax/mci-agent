'''Format mà tầng trình bày sẽ trả về UI'''
'''Controller trả về cái gì'''
from typing import Literal
from pydantic import BaseModel


class AgentResponse(BaseModel):
    role: Literal['assistant']
    content: str
