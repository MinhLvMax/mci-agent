'''Controller là thằng nối Presentation với use case'''
from src.app.agent import Agent
from src.pre.controllers.agent.agent_request import AgentRequest
from src.pre.controllers.agent.agent_response import AgentResponse
from src.pre.controllers.agent.agent_mapper import AgentMapper


class AgentController:

    def __init__(self, agent: Agent):
        self.agent = agent
        self.mapper = AgentMapper()

    def invoke(self, raw_request: dict) -> AgentResponse:
        # 1. JSON/dict → Presentation DTO
        request = AgentRequest.model_validate(
            raw_request
        )

        # 2. Presentation DTO → Domain/Application
        context = self.mapper.to_context(
            request=request
        )

        # 3. Gọi nghiệp vụ thật
        result = self.agent.invoke(
            context
        )

        # 4. Application result → Presentation response
        return AgentResponse(
            role='assistant',
            content=result
        )
