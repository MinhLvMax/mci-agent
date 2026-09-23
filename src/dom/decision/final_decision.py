from dataclasses import dataclass
from src.dom.decision import Decision


@dataclass
class FinalDecision(Decision):
    final_content: str
