from src.inf.tools.web.ddgs_tool import DDGSTool
from src.inf.tools.web.open_url_tool import OpenURLTool
from src.inf.tools.file.get_file_info_tool import GetFileInfoTool
from src.inf.tools.file.list_files_tool import ListFilesTool
from src.inf.tools.file.patch_file_tool import PatchFileTool
from src.inf.tools.file.read_file_tool import ReadFileTool
from src.inf.tools.file.search_files_tool import SearchFilesTool
from src.inf.tools.file.write_file_tool import WriteFileTool

from src.inf.model_reasoner.openai_model_reasoner import OpenAIModelReasoner
from src.app.services.tool_executor import ToolExecutor
from src.app.services.agent import Agent
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.services.postgre_db import create_postgres_connection
from src.app.usecases.chat_usecase import ChatUseCase
from src.pre.controllers.agent.agent_controller import AgentController
from src.config import Config


def build_reasoner():
    # reasoner = GroqModelReasoner(
    #     api_key=Config.GROQ_API_KEY,
    #     model='qwen/qwen3.8-27b'
    # )

    return OpenAIModelReasoner(
        api_key=Config.OPEN_API_KEY,
        model="gpt-5.6-luna",
        # model='gpt-5-nano'
    )


def build_tool_manager():
    agent_workspace_dir = Config.AGENT_WORKSPACE

    return ToolExecutor(
        tools=[
            # Web
            DDGSTool(),
            OpenURLTool(),

            # file
            # GetFileInfoTool(workspace_dir=agent_workspace_dir),
            # ListFilesTool(workspace_dir=agent_workspace_dir),
            # PatchFileTool(workspace_dir=agent_workspace_dir),
            # ReadFileTool(workspace_dir=agent_workspace_dir),
            # SearchFilesTool(workspace_dir=agent_workspace_dir),
            # WriteFileTool(workspace_dir=agent_workspace_dir),

        ]
    )


def build_agent_service():
    return Agent(
        model_reasoner=build_reasoner(),
        tool_executor=build_tool_manager(),
    )


def build_agent_controller():
    return AgentController(
        agent=build_agent_service()
    )
