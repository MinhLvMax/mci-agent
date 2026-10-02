import json
import re

from src.app.ports.model_reasoner import ModelReasoner
from src.dom.context import Context
from src.dom.decision.final_decision import FinalDecision
from src.dom.message.text_message import TextMessage
from src.config import Config


class LLMExtractorError(RuntimeError):
    pass


class LLMExtractor:
    '''
    Gọi model một lượt (không tool) và nhận về JSON.
    Dùng bên trong các tool để xử lý văn bản dài theo từng đoạn, không đi qua context chính của agent.
    '''

    def __init__(self, reasoner: ModelReasoner, retries: int = 1):
        self.reasoner = reasoner
        self.retries = retries

    def ask_json(self, system_prompt: str, user_content: str) -> list | dict:
        messages = [
            TextMessage(role='system', content=system_prompt),
            TextMessage(role='user', content=user_content),
        ]
        last_error = None

        for _ in range(self.retries + 1):
            decision = self.reasoner.decide(context=Context(messages=list(messages)), tools=[])

            if not isinstance(decision, FinalDecision):
                last_error = 'model tried to call a tool instead of answering'
                continue

            try:
                return parse_json(decision.final_content)

            except ValueError as e:
                last_error = str(e)
                Config.logger.debug(f'LLM returned invalid JSON: {decision.final_content[:300]}')
                # Cho model thấy câu trả lời lỗi và yêu cầu trả lại đúng định dạng
                messages = messages[:2] + [
                    TextMessage(role='assistant', content=decision.final_content),
                    TextMessage(role='user', content='Câu trả lời không phải JSON hợp lệ. Chỉ trả về đúng mảng JSON.'),
                ]

        raise LLMExtractorError(f'LLM did not return valid JSON: {last_error}')


def parse_json(text: str) -> list | dict:
    '''Lấy JSON từ câu trả lời của model, chấp nhận cả khi bị bọc trong ```json ... ```'''
    text = text.strip()

    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Model đôi khi viết thêm chữ trước/sau, thử cắt từ dấu [ hoặc { đầu tiên tới dấu đóng cuối cùng
    for open_char, close_char in (('[', ']'), ('{', '}')):
        start, end = text.find(open_char), text.rfind(close_char)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue

    raise ValueError('response is not valid JSON')
