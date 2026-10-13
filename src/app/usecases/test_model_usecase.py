import time
from dataclasses import dataclass
from typing import Callable

from src.app.ports.model_reasoner import ModelReasoner, ModelUnavailableError
from src.app.usecases.admin_models_usecase import validate_model
from src.dom.context import Context
from src.dom.entities.ai_model import AIModel
from src.dom.message.text_message import TextMessage
from src.dom.tool import Tool, ToolKwargs, ToolResult

TEST_PROMPT = "Đây là tin nhắn kiểm tra kết nối. Trả lời đúng một từ: OK"
MAX_ERROR_CHARS = 300  # Lỗi lạ của nhà cung cấp có thể rất dài, chỉ giữ phần đầu để admin đọc


class _PingKwargs(ToolKwargs):
    pass


class PingTool(Tool):
    '''
    Tool giả chỉ để gửi kèm schema khi chạy thử: agent chat luôn gửi tool,
    model không hỗ trợ gọi tool thì phải lộ ra ngay lúc chạy thử. Không bao giờ được thực thi.
    '''
    tool_name = "ping"
    tool_description = "Kiểm tra kết nối. Không cần gọi tool này."
    tool_kwargs = _PingKwargs

    def execute(self, **kwargs) -> ToolResult:
        raise NotImplementedError


@dataclass
class ModeTestResult:
    mode: str | None  # None là gọi không kèm chế độ suy luận
    ok: bool
    message: str
    seconds: float


class TestModelUsecase:
    '''
    Admin chạy thử model ngay trong form, trước khi lưu/bật cho mọi người:
    gọi model một lần cho mỗi chế độ suy luận (không có chế độ thì gọi một lần) với một câu ngắn.
    Không ghi gì vào CSDL.
    '''
    __test__ = False  # Tên bắt đầu bằng "Test" nhưng không phải test case

    def __init__(
            self,
            reasoner_factory: Callable[[AIModel, str | None], ModelReasoner],
            supported_providers: list[str],
    ):
        self.reasoner_factory = reasoner_factory
        self.supported_providers = supported_providers

    def execute(self, model: AIModel) -> list[ModeTestResult]:
        model.display_name = model.display_name.strip() or "Chạy thử"  # Chạy thử chưa cần tên hiển thị
        model.is_default = False  # Cờ mặc định không liên quan tới chạy thử
        validate_model(model, self.supported_providers)

        return [self._test_mode(model, mode) for mode in (model.reasoning_modes or [None])]

    def _test_mode(self, model: AIModel, mode: str | None) -> ModeTestResult:
        started = time.perf_counter()

        try:
            reasoner = self.reasoner_factory(model, mode)
            reasoner.decide(
                Context(messages=[TextMessage(role="user", content=TEST_PROMPT)]),
                [PingTool()],
            )
        except ModelUnavailableError as e:
            return ModeTestResult(mode, False, str(e), self._elapsed(started))
        except Exception as e:
            detail = f"{type(e).__name__}: {e}"[:MAX_ERROR_CHARS]
            return ModeTestResult(mode, False, f"Lỗi khác từ nhà cung cấp: {detail}", self._elapsed(started))

        return ModeTestResult(mode, True, "Gọi được model", self._elapsed(started))

    @staticmethod
    def _elapsed(started: float) -> float:
        return round(time.perf_counter() - started, 1)
