# import json
# import ollama
# from src.app.model_reasoner import ModelReasoner
# from src.dom.context import Context
# from src.dom.decision import Decision
# from src.dom.tool import Tool
# from src.dom.message import BaseMessage
# from src.dom.message.text_message import TextMessage
# from src.dom.message.tool_call_message import ToolCallMessage
# from src.dom.message.tool_result_message import ToolResultMessage
# from src.dom.tool_call import ToolCall
# from src.dom.decision.tool_call_decision import ToolCallDecision
# from src.dom.decision.final_decision import FinalDecision
# from src.config import Config
#
# response = ollama.chat(
#     model="qwen3:0.6b",
#     messages=[
#         {
#             "role": "user",
#             "content": "Giải thích Ollama là gì"
#         }
#     ]
# )
#
# print(response["message"]["content"])
#
#
# class OllamaModelReasoner(ModelReasoner):
#
#     def decide(self, context: Context, tools: list[Tool]) -> Decision:
#         ...
