from src.app.services.tool_executor import ToolExecutor
from src.app.ports.model_reasoner import ModelReasoner
from src.dom.context import Context
from src.dom.decision.final_decision import FinalDecision
from src.dom.decision.tool_call_decision import ToolCallDecision
from src.config import Config


class AgentService:
    def __init__(
            self,
            model_reasoner: ModelReasoner | None = None,
            tool_executor: ToolExecutor | None = None
    ):
        self.model_reasoner = model_reasoner
        self.tool_executor = tool_executor

    def invoke(self, context: Context):

        while True:
            '''Vòng lặp suy nghĩa của agent'''
            Config.logger.debug('Thinking...')

            decision = self.model_reasoner.decide(
                context=context,
                tools=self.tool_executor.tools
            )
            '''Ra quyết định'''

            if isinstance(decision, FinalDecision):
                '''Trả lời được ngay thì trả lời luôn'''
                context.add_final_message(
                    content=decision.final_content,
                )
                return decision.final_content

            if isinstance(decision, ToolCallDecision):
                '''Cần gọi tool thì thực thi từng tool và thêm kết quả vào bối cảnh'''
                Config.logger.debug(f'Preparing to execute {len(decision.tool_calls)} tool calls.')

                context.add_tool_call_message(
                    tool_calls=decision.tool_calls
                )

                for call in decision.tool_calls:
                    Config.logger.debug(f'{call.name}, {call.kwargs}'[:500])
                    tool_result = self.tool_executor.execute_tool(
                        tool_name=call.name,
                        **call.kwargs,
                    )

                    context.add_tool_result_message(
                        id=call.tool_call_id,
                        result=tool_result.to_text(),
                        tool_name=call.name
                    )
