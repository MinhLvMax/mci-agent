import json
from typing import Generator
from openai import OpenAI
from src.app.ports.model_reasoner import ModelReasoner
from src.dom.context import Context
from src.dom.decision import Decision
from src.dom.tool import Tool
from src.dom.message import BaseMessage
from src.dom.message.text_message import TextMessage
from src.dom.message.tool_call_message import ToolCallMessage
from src.dom.message.tool_result_message import ToolResultMessage
from src.dom.tool_call import ToolCall
from src.dom.decision.tool_call_decision import ToolCallDecision
from src.dom.decision.final_decision import FinalDecision
from src.dom.agent_event import AgentEvent
from src.config import Config


class OpenAIModelReasoner(ModelReasoner):

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None
    ):
        api_key = api_key or Config.OPEN_API_KEY

        self.client = OpenAI(
            api_key=api_key
        )

        self.model = model or "gpt-5.6-luna"

    def decide(
        self,
        context: Context,
        tools: list[Tool]
    ) -> Decision:

        # -------------------------
        # Convert messages
        # -------------------------

        input_items = []

        for message in context.messages:
            converted = self._convert_message(message)

            # ToolCallMessage có thể sinh ra nhiều
            # function_call item
            if isinstance(converted, list):
                input_items.extend(converted)
            else:
                input_items.append(converted)

        # -------------------------
        # Convert tools
        # -------------------------

        tool_schemas = [
            self._convert_tool(tool)
            for tool in tools
        ]

        # -------------------------
        # Call OpenAI
        # -------------------------

        response = self.client.responses.create(
            model=self.model,
            input=input_items,
            tools=tool_schemas,
            tool_choice="auto",
        )

        # -------------------------
        # Check tool calls
        # -------------------------

        tool_calls = []

        for item in response.output:
            if item.type == "function_call":
                tool_calls.append(
                    self._convert_tool_call(item)
                )

        if tool_calls:
            return ToolCallDecision(
                tool_calls=tool_calls
            )

        # -------------------------
        # Final answer
        # -------------------------

        return FinalDecision(
            final_content=response.output_text or ""
        )

    def decide_stream(
        self,
        context: Context,
        tools: list[Tool]
    ) -> Generator[AgentEvent, None, Decision]:
        '''Chưa stream với OpenAI: gọi decide như cũ, không phát event thinking nào'''
        return self.decide(context, tools)
        yield  # Có yield thì Python mới coi hàm này là generator

    # =========================================================
    # MESSAGE MAPPER
    # =========================================================

    def _convert_message(
        self,
        message: BaseMessage
    ) -> dict | list[dict]:

        if isinstance(message, TextMessage):
            return self._convert_text_message(message)

        if isinstance(message, ToolCallMessage):
            return self._convert_tool_call_message(message)

        if isinstance(message, ToolResultMessage):
            return self._convert_tool_result_message(message)

        raise TypeError(
            f"Unsupported message type: "
            f"{type(message).__name__}"
        )

    # =========================================================
    # TOOL
    # =========================================================

    def _convert_tool(
        self,
        tool: Tool
    ) -> dict:

        return {
            "type": "function",
            "name": tool.tool_name,
            "description": tool.tool_description,
            "parameters": tool.tool_kwargs.model_json_schema(),
        }

    # =========================================================
    # TEXT MESSAGE
    # =========================================================

    def _convert_text_message(
        self,
        message: TextMessage
    ) -> dict:

        return {
            "role": message.role,
            "content": message.content,
        }

    # =========================================================
    # TOOL CALL MESSAGE
    # =========================================================

    def _convert_tool_call_message(
        self,
        message: ToolCallMessage
    ) -> list[dict]:

        return [
            {
                "type": "function_call",
                "call_id": call.tool_call_id,
                "name": call.name,
                "arguments": json.dumps(call.kwargs),
            }
            for call in message.list_tool_call
        ]

    # =========================================================
    # TOOL RESULT MESSAGE
    # =========================================================

    def _convert_tool_result_message(
        self,
        message: ToolResultMessage
    ) -> dict:

        return {
            "type": "function_call_output",
            "call_id": message.tool_call_id,
            "output": str(message.tool_result),
        }

    # =========================================================
    # OPENAI TOOL CALL -> DOMAIN TOOL CALL
    # =========================================================

    def _convert_tool_call(
        self,
        call
    ) -> ToolCall:

        return ToolCall(
            tool_call_id=call.call_id,
            name=call.name,
            kwargs=json.loads(
                call.arguments
            ),
        )

    def print_models_list(self):
        models = self.client.models.list()

        for model in models.data:
            print(model.id)

if __name__ == '__main__':
    print(OpenAIModelReasoner().print_models_list())