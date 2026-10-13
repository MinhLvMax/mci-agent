'''
Adapter Anthropic: chưa có API key nên thay client thật bằng client giả,
phát lại các event / message giống Messages API để kiểm tra phần chuyển đổi.
'''
import unittest
from types import SimpleNamespace as NS

from anthropic.types import TextBlock, ThinkingBlock, ToolUseBlock
from pydantic import BaseModel

from src.app.ports.model_reasoner import ModelUnavailableError
from src.dom.context import Context
from src.dom.decision.final_decision import FinalDecision
from src.dom.decision.tool_call_decision import ToolCallDecision
from src.dom.message.text_message import TextMessage
from src.dom.message.tool_call_message import ToolCallMessage
from src.dom.message.tool_result_message import ToolResultMessage
from src.dom.tool import Tool
from src.dom.tool_call import ToolCall
from src.inf.model_reasoner.anthropic_model_reasoner import REFUSAL_MESSAGE, AnthropicModelReasoner


class _SearchKwargs(BaseModel):
    query: str


class SearchTool(Tool):
    tool_name = "web_search"
    tool_description = "Tìm kiếm web"
    tool_kwargs = _SearchKwargs

    def execute(self, **kwargs):
        raise NotImplementedError


def delta(kind, text):
    field = "thinking" if kind == "thinking_delta" else "text"
    return NS(type="content_block_delta", delta=NS(type=kind, **{field: text}))


class FakeStream:
    def __init__(self, events, final, error=None):
        self.events, self.final, self.error = events, final, error

    def __enter__(self):
        if self.error:
            raise self.error
        return self

    def __exit__(self, *args):
        return False

    def __iter__(self):
        return iter(self.events)

    def get_final_message(self):
        return self.final


class FakeClient:
    def __init__(self, stream):
        self.calls = []
        self.messages = NS(stream=lambda **params: self.calls.append(params) or stream)


def make_reasoner(stream, effort=None):
    reasoner = AnthropicModelReasoner(api_key="test", model="claude-test", reasoning_effort=effort)
    reasoner.client = FakeClient(stream)
    return reasoner


def run(reasoner, context, tools=()):
    '''Trả về (các event, decision) như agent_service dùng decide_stream'''
    events, generator = [], reasoner.decide_stream(context, list(tools))
    while True:
        try:
            events.append(next(generator))
        except StopIteration as stop:
            return events, stop.value


class FakeAPIError(Exception):
    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code, self.message = status_code, message


class AnthropicReasonerTest(unittest.TestCase):
    def test_final_answer_streams_thinking_and_text(self):
        final = NS(stop_reason="end_turn", content=[
            ThinkingBlock(type="thinking", thinking="Suy nghĩ", signature="sig"),
            TextBlock(type="text", text="Xin chào"),
        ])
        stream = FakeStream([delta("thinking_delta", "Suy nghĩ"), delta("text_delta", "Xin "), delta("text_delta", "chào")], final)
        reasoner = make_reasoner(stream, effort="high")

        events, decision = run(reasoner, Context(messages=[
            TextMessage(role="system", content="Bạn là trợ lý."),
            TextMessage(role="user", content="hi"),
        ]))

        self.assertEqual([(e.type, e.data["text"]) for e in events],
                         [("thinking", "Suy nghĩ"), ("content", "Xin "), ("content", "chào")])
        self.assertIsInstance(decision, FinalDecision)
        self.assertEqual(decision.final_content, "Xin chào")

        params = reasoner.client.calls[0]
        self.assertEqual(params["system"], "Bạn là trợ lý.")  # System tách khỏi messages
        self.assertEqual(params["messages"], [{"role": "user", "content": "hi"}])
        self.assertEqual(params["thinking"], {"type": "adaptive", "display": "summarized"})
        self.assertEqual(params["output_config"], {"effort": "high"})
        self.assertNotIn("tools", params)

    def test_no_reasoning_mode_sends_no_thinking(self):
        reasoner = make_reasoner(FakeStream([], NS(stop_reason="end_turn", content=[TextBlock(type="text", text="ok")])))
        run(reasoner, Context(messages=[TextMessage(role="user", content="hi")]))
        params = reasoner.client.calls[0]
        self.assertNotIn("thinking", params)
        self.assertNotIn("output_config", params)

    def test_tool_call_keeps_full_turn_for_next_request(self):
        content = [
            ThinkingBlock(type="thinking", thinking="Cần tìm", signature="sig-1"),
            ToolUseBlock(type="tool_use", id="toolu_1", name="web_search", input={"query": "Hạ Long"}),
            ToolUseBlock(type="tool_use", id="toolu_2", name="web_search", input={"query": "Sa Pa"}),
        ]
        reasoner = make_reasoner(FakeStream([], NS(stop_reason="tool_use", content=content)), effort="low")

        _, decision = run(reasoner, Context(messages=[TextMessage(role="user", content="tìm")]), [SearchTool()])

        self.assertIsInstance(decision, ToolCallDecision)
        self.assertEqual([(c.tool_call_id, c.kwargs) for c in decision.tool_calls],
                         [("toolu_1", {"query": "Hạ Long"}), ("toolu_2", {"query": "Sa Pa"})])
        self.assertEqual(decision.provider_items[0], {"type": "thinking", "thinking": "Cần tìm", "signature": "sig-1"})
        self.assertEqual(reasoner.client.calls[0]["tools"][0]["name"], "web_search")
        self.assertIn("query", reasoner.client.calls[0]["tools"][0]["input_schema"]["properties"])

        # Lượt sau: gửi lại nguyên vẹn lượt gọi tool, gộp 2 kết quả tool vào một message user
        context = Context(messages=[TextMessage(role="user", content="tìm")])
        context.add_tool_call_message(decision.tool_calls, decision.provider_items)
        context.add_tool_result_message("toolu_1", "kết quả 1", "web_search")
        context.add_tool_result_message("toolu_2", "kết quả 2", "web_search")
        system, messages = reasoner._convert_messages(context.messages)

        self.assertEqual(system, "")
        self.assertEqual(messages[1], {"role": "assistant", "content": decision.provider_items})
        self.assertEqual(messages[2], {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_1", "content": "kết quả 1"},
            {"type": "tool_result", "tool_use_id": "toolu_2", "content": "kết quả 2"},
        ]})

    def test_tool_call_without_provider_items(self):
        message = ToolCallMessage(role="assistant", list_tool_call=[ToolCall("toolu_9", "web_search", {"query": "x"})])
        self.assertEqual(AnthropicModelReasoner._convert_tool_call_message(message),
                         [{"type": "tool_use", "id": "toolu_9", "name": "web_search", "input": {"query": "x"}}])

    def test_refusal_and_truncated_tool_input(self):
        refused = make_reasoner(FakeStream([], NS(stop_reason="refusal", content=[])))
        _, decision = run(refused, Context(messages=[TextMessage(role="user", content="hi")]))
        self.assertEqual(decision.final_content, REFUSAL_MESSAGE)

        truncated = make_reasoner(FakeStream([], NS(stop_reason="max_tokens", content=[
            ToolUseBlock(type="tool_use", id="toolu_1", name="web_search", input={}),
        ])))
        with self.assertRaises(RuntimeError):
            run(truncated, Context(messages=[TextMessage(role="user", content="hi")]))

    def test_api_errors_become_model_errors(self):
        import src.inf.model_reasoner.anthropic_model_reasoner as module

        cases = [
            (404, "model: claude-opsu-5-5", "không tồn tại"),
            (400, "output_config.effort: Input should be 'low', 'medium', 'high', 'xhigh' or 'max'", "chế độ suy luận"),
            (400, "adaptive thinking is not supported on this model", "chế độ suy luận"),
            (401, "invalid x-api-key", "API key"),
        ]
        original = module.APIStatusError
        module.APIStatusError = FakeAPIError  # Lỗi thật của SDK cần response HTTP, dùng lỗi giả cùng thuộc tính
        try:
            for status, message, expected in cases:
                with self.subTest(status=status, message=message):
                    reasoner = make_reasoner(FakeStream([], None, error=FakeAPIError(status, message)), effort="hgih")
                    with self.assertRaises(ModelUnavailableError) as raised:
                        run(reasoner, Context(messages=[TextMessage(role="user", content="hi")]))
                    self.assertIn(expected, str(raised.exception))
        finally:
            module.APIStatusError = original


class AnthropicRegistrationTest(unittest.TestCase):
    def test_provider_is_registered_and_needs_api_key(self):
        from src import bootstrap
        from src.dom.entities.ai_model import AIModel

        self.assertIn("anthropic", [p.name for p in bootstrap.AppContainer().supported_providers()])

        model = AIModel(display_name="Claude", model_name="claude-opus-5-5", provider="anthropic")
        original = bootstrap.Config.ANTHROPIC_API_KEY
        try:
            bootstrap.Config.ANTHROPIC_API_KEY = None
            with self.assertRaises(ModelUnavailableError) as raised:
                bootstrap.build_chat_reasoner(model, "high")
            self.assertIn("API key của Anthropic", str(raised.exception))

            bootstrap.Config.ANTHROPIC_API_KEY = "test-key"
            reasoner = bootstrap.build_chat_reasoner(model, "high")
            self.assertEqual((reasoner.model, reasoner.reasoning_effort), ("claude-opus-5-5", "high"))
        finally:
            bootstrap.Config.ANTHROPIC_API_KEY = original


if __name__ == '__main__':
    unittest.main()
