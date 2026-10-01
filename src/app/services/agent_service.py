from typing import Iterator

from src.app.services.tool_executor import ToolExecutor
from src.app.ports.model_reasoner import ModelReasoner
from src.dom.context import Context
from src.dom.agent_event import AgentEvent
from src.dom.decision.final_decision import FinalDecision
from src.dom.decision.tool_call_decision import ToolCallDecision
from src.config import Config


class AgentService:
    TOOL_RESULT_PREVIEW_CHARS = 500  # Kết quả tool gửi lên UI chỉ để xem, cắt bớt cho nhẹ

    def __init__(
            self,
            model_reasoner: ModelReasoner | None = None,
            tool_executor: ToolExecutor | None = None
    ):
        self.model_reasoner = model_reasoner
        self.tool_executor = tool_executor

    def invoke(self, context: Context):
        '''Chạy hết invoke_stream, chỉ lấy câu trả lời cuối (dùng cho CLI, /chat/ cũ)'''
        for event in self.invoke_stream(context):
            if event.type == 'done':
                return event.data['content']

    def invoke_stream(self, context: Context) -> Iterator[AgentEvent]:

        while True:
            '''Vòng lặp suy nghĩa của agent'''
            Config.logger.debug('Thinking...')

            decision = yield from self.model_reasoner.decide_stream(
                context=context,
                tools=self.tool_executor.tools
            )
            '''Ra quyết định, trong lúc model sinh chữ thì các event thinking/content đã được yield lên trên'''

            if isinstance(decision, FinalDecision):
                '''Trả lời được ngay thì trả lời luôn'''
                context.add_final_message(
                    content=decision.final_content,
                )
                yield AgentEvent(type='done', data={"content": decision.final_content})
                return

            if isinstance(decision, ToolCallDecision):
                '''Cần gọi tool thì thực thi từng tool và thêm kết quả vào bối cảnh'''
                Config.logger.debug(f'Preparing to execute {len(decision.tool_calls)} tool calls.')

                context.add_tool_call_message(
                    tool_calls=decision.tool_calls
                )

                for call in decision.tool_calls:
                    Config.logger.debug(f'{call.name}, {call.kwargs}'[:500])
                    yield AgentEvent(
                        type='tool_call',
                        data={"id": call.tool_call_id, "name": call.name, "kwargs": call.kwargs}
                    )

                    tool_result = self.tool_executor.execute_tool(
                        tool_name=call.name,
                        **call.kwargs,
                    )
                    result_text = tool_result.to_text()

                    context.add_tool_result_message(
                        id=call.tool_call_id,
                        result=result_text,
                        tool_name=call.name
                    )
                    yield AgentEvent(
                        type='tool_result',
                        data={
                            "id": call.tool_call_id,
                            "name": call.name,
                            "result": result_text[:self.TOOL_RESULT_PREVIEW_CHARS],
                        }
                    )
