from pathlib import Path

from src.inf.tools.web.ddgs_tool import DDGSTool
from src.inf.tools.web.open_url_tool import OpenURLTool
from src.inf.tools.file.get_file_info_tool import GetFileInfoTool
from src.inf.tools.file.list_files_tool import ListFilesTool
from src.inf.tools.file.patch_file_tool import PatchFileTool
from src.inf.tools.file.read_file_tool import ReadFileTool
from src.inf.tools.file.search_files_tool import SearchFilesTool
from src.inf.tools.file.write_file_tool import WriteFileTool

from src.inf.model_reasoner.openai_model_reasoner import OpenAIModelReasoner
from src.inf.model_reasoner.groq_model_reasoner import GroqModelReasoner
from src.app.services.tool_executor import ToolExecutor
from src.app.services.agent_service import AgentService
from src.app.services.workspace_service import WorkspaceService
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.services.postgre_db import create_postgres_connection
from src.app.usecases.chat_usecase import ChatUseCase
from src.app.services.jwt_service import JWTService
# from src.pre.controllers.agent.agent_controller import AgentController
from src.config import Config


def build_reasoner():
    return GroqModelReasoner(
        api_key=Config.GROQ_API_KEY,
        model='qwen/qwen3.8-27b'
    )

    # return OpenAIModelReasoner(
    #     api_key=Config.OPEN_API_KEY,
    #     model="gpt-5.6-luna",
    #     # model='gpt-5-nano'
    # )


def build_tool_manager(agent_workspace_dir: Path):
    # agent_workspace_dir = Config.AGENT_WORKSPACE

    return ToolExecutor(
        tools=[
            # Web
            DDGSTool(),
            OpenURLTool(),

            # file
            GetFileInfoTool(workspace_dir=agent_workspace_dir),
            ListFilesTool(workspace_dir=agent_workspace_dir),
            PatchFileTool(workspace_dir=agent_workspace_dir),
            ReadFileTool(workspace_dir=agent_workspace_dir),
            SearchFilesTool(workspace_dir=agent_workspace_dir),
            WriteFileTool(workspace_dir=agent_workspace_dir),

        ]
    )


def build_workspace_service() -> WorkspaceService:
    """
    Tạo service quản lý workspace.

    ROOT_AGENT_WORKSPACE là thư mục gốc chứa toàn bộ
    workspace của các user/conversation.
    """
    return WorkspaceService(
        workspace_root=Config.AGENT_ROOT_WORKSPACE
    )


def build_jwt_service() -> JWTService:
    return JWTService(
        secret_key=Config.JWT_SECRET_KEY,  # Khóa bí mật dùng để ký và kiểm tra token
        algorithm=Config.JWT_ALGORITHM,  # Thuật toán ký, ví dụ HS256
        expire_minutes=Config.JWT_EXPIRE_MINUTES,  # Số phút token còn hiệu lực
    )


def build_agent_service(agent_workspace_dir):
    return AgentService(
        model_reasoner=build_reasoner(),
        tool_executor=build_tool_manager(agent_workspace_dir),
    )

# def build_agent_controller():
#     return AgentController(
#         agent=build_agent_service()
#     )
