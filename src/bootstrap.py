from pathlib import Path

from src.inf.tools.web.ddgs_web_search_tool import DDGSWebSearchTool
from src.inf.tools.web.ddgs_open_url_tool import DDGSOpenURLTool
from src.inf.tools.web.tavily_open_url_tool import TavilyOpenURLTool
from src.inf.tools.web.tavily_web_search_tool import TavilyWebSearchTool
from src.inf.tools.youtube.youtube_search_tool import YoutubeSearchTool
from src.inf.tools.youtube.youtube_transcript_tool import YoutubeTranscriptTool
from src.inf.tools.research.extract_insights_tool import ExtractInsightsTool
from src.inf.tools.research.find_unique_stories_tool import FindUniqueStoriesTool
from src.inf.tools.research.verify_claims_tool import VerifyClaimsTool
from src.inf.tools.research.build_outline_tool import BuildOutlineTool
from src.inf.tools.skill.load_skill_tool import LoadSkillTool
from src.inf.tools.file.get_file_info_tool import GetFileInfoTool
from src.inf.tools.file.list_files_tool import ListFilesTool
from src.inf.tools.file.move_path_tool import MovePathTool
from src.inf.tools.file.patch_file_tool import PatchFileTool
from src.inf.tools.file.read_file_tool import ReadFileTool
from src.inf.tools.file.rename_path_tool import RenamePathTool
from src.inf.tools.file.search_files_tool import SearchFilesTool
from src.inf.tools.file.write_file_tool import WriteFileTool

from src.inf.model_reasoner.openai_model_reasoner import OpenAIModelReasoner
from src.inf.model_reasoner.groq_model_reasoner import GroqModelReasoner
from src.inf.model_reasoner.ollama_model_reasoner import OllamaModelReasoner
from src.app.services.tool_executor import ToolExecutor
from src.app.services.agent_service import AgentService
from src.app.services.workspace_service import WorkspaceService
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.services.postgre_db import create_postgres_connection
from src.app.usecases.chat_usecase import ChatUseCase
from src.app.services.jwt_service import JWTService
from src.dom.entities.skill import Skill
# from src.pre.controllers.agent.agent_controller import AgentController
from src.config import Config


def build_reasoner():
    # return GroqModelReasoner(
    #     api_key=Config.GROQ_API_KEY,
    #     model='qwen/qwen3.8-27b'
    # )

    # return OllamaModelReasoner(
    #     # host=Config.OLLAMA_HOST,
    #     # model='qwen3:0.6b',
    #     model='gpt-oss:120b',
    #     # model='gpt-oss:20b',
    #     # model='nemotron-3-nano:30b',
    #     api_key=Config.OLLAMA_API_KEY,
    #     think='medium',  # gpt-oss chỉ nhận 'low'/'medium'/'high', qwen3 thì dùng True/False
    # )

    return OpenAIModelReasoner(
        api_key=Config.OPEN_API_KEY,
        model="gpt-5.6-luna",
        # model='gpt-5-nano'
        reasoning_effort="high",
    )


def build_title_reasoner():
    '''Model đặt tên hội thoại: việc ngắn nên suy nghĩ ít cho nhanh'''
    return OllamaModelReasoner(
        model='gpt-oss:120b',
        api_key=Config.OLLAMA_API_KEY,
        think='low',
    )


def build_tool_manager(agent_workspace_dir: Path, reasoner, skills: list[Skill] = ()):
    # agent_workspace_dir = Config.AGENT_WORKSPACE

    # Skill không always_on chỉ được liệt kê tên trong system prompt, agent dùng load_skill để đọc chỉ dẫn đầy đủ
    on_demand_skills = [skill for skill in skills if not skill.always_on]

    return ToolExecutor(
        tools=[
            # Web
            DDGSWebSearchTool(),
            # DDGSOpenURLTool(workspace_dir=agent_workspace_dir),
            # TavilyWebSearchTool(api_key=Config.TAVILY_API_KEY),
            TavilyOpenURLTool(workspace_dir=agent_workspace_dir, api_key=Config.TAVILY_API_KEY),

            # YouTube
            YoutubeSearchTool(),
            # YoutubeTranscriptTool(workspace_dir=agent_workspace_dir),

            # Phân tích: các tool lọc thông tin cần gọi model nên nhận chung reasoner với agent,
            # đọc/ghi theo đường dẫn do agent chọn, phần đọc/ghi còn lại dùng tool file bên dưới
            # ExtractInsightsTool(workspace_dir=agent_workspace_dir, reasoner=reasoner),
            # VerifyClaimsTool(workspace_dir=agent_workspace_dir, reasoner=reasoner),
            # FindUniqueStoriesTool(workspace_dir=agent_workspace_dir, reasoner=reasoner),
            # BuildOutlineTool(workspace_dir=agent_workspace_dir, reasoner=reasoner),

            # file (không có tool xóa: người dùng tự xóa trên giao diện)
            GetFileInfoTool(workspace_dir=agent_workspace_dir),
            ListFilesTool(workspace_dir=agent_workspace_dir),
            ReadFileTool(workspace_dir=agent_workspace_dir),
            SearchFilesTool(workspace_dir=agent_workspace_dir),
            WriteFileTool(workspace_dir=agent_workspace_dir),
            PatchFileTool(workspace_dir=agent_workspace_dir),
            MovePathTool(workspace_dir=agent_workspace_dir),
            RenamePathTool(workspace_dir=agent_workspace_dir),

            # Skill
            # *([LoadSkillTool(skills=on_demand_skills)] if on_demand_skills else []),
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


def build_agent_service(agent_workspace_dir, skills: list[Skill] = ()):
    reasoner = build_reasoner()

    return AgentService(
        model_reasoner=reasoner,
        tool_executor=build_tool_manager(agent_workspace_dir, reasoner, skills),
    )

# def build_agent_controller():
#     return AgentController(
#         agent=build_agent_service()
#     )
