from pathlib import Path

from src.inf.tools.web.ddgs_web_search_tool import DDGSWebSearchTool
# from src.inf.tools.web.ddgs_open_url_tool import DDGSOpenURLTool
from src.inf.tools.web.tavily_open_url_tool import TavilyOpenURLTool
# from src.inf.tools.web.tavily_web_search_tool import TavilyWebSearchTool
# from src.inf.tools.youtube.youtube_search_tool import YoutubeSearchTool
# from src.inf.tools.youtube.youtube_transcript_tool import YoutubeTranscriptTool
from src.inf.tools.youtube.nexlev_youtube_search_tool import NexlevYoutubeSearchTool
from src.inf.tools.youtube.nexlev_youtube_transcript_tool import NexlevYoutubeTranscriptTool
from src.inf.tools.youtube.nexlev_youtube_comments_tool import NexlevYoutubeCommentsTool
from src.inf.tools.file.get_file_info_tool import GetFileInfoTool
from src.inf.tools.file.list_files_tool import ListFilesTool
from src.inf.tools.file.move_path_tool import MovePathTool
from src.inf.tools.file.patch_file_tool import PatchFileTool
from src.inf.tools.file.read_file_tool import ReadFileTool
from src.inf.tools.file.rename_path_tool import RenamePathTool
from src.inf.tools.file.search_files_tool import SearchFilesTool
from src.inf.tools.file.write_file_tool import WriteFileTool
from src.inf.tools.memory.remember_tool import RememberTool
from src.inf.tools.skill.load_skill_tool import LoadSkillTool
from src.inf.tools.memory.forget_tool import ForgetTool

from src.inf.model_reasoner.openai_model_reasoner import OpenAIModelReasoner
# from src.inf.model_reasoner.groq_model_reasoner import GroqModelReasoner
# from src.inf.model_reasoner.ollama_model_reasoner import OllamaModelReasoner
from src.app.services.tool_executor import ToolExecutor
from src.app.services.agent_service import AgentService
from src.inf.storage.local_workspace_service import LocalWorkspaceService
from src.inf.storage.local_file_storage import LocalFileStorage
from src.inf.storage.local_workspace_scanner import LocalWorkspaceScanner
from src.inf.security.bcrypt_password_hasher import BcryptPasswordHasher
from src.inf.security.jwt_token_service import JWTTokenService
from src.app.ports.security import PasswordHasher, TokenService
from src.app.ports.storage import FileStorage, WorkspaceScanner, WorkspaceService
from src.app.services.memory_service import MemoryService
from src.inf.persistence.postgres.unit_of_work import PostgresUnitOfWork
from src.app.ports.unit_of_work import UnitOfWork
from src.dom.entities.skill import Skill
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
    # return OllamaModelReasoner(
    #     model='gpt-oss:120b',
    #     api_key=Config.OLLAMA_API_KEY,
    #     think='low',
    # )

    return build_reasoner()


def build_lesson_reasoner():
    '''Model trích bài học sau mỗi lượt chat: chạy mọi lượt nên suy nghĩ ít cho rẻ và nhanh'''
    return OpenAIModelReasoner(
        api_key=Config.OPEN_API_KEY,
        model="gpt-5.6-luna",
        reasoning_effort="low",
    )


def build_tool_manager(
        agent_workspace_dir: Path,
        reasoner,
        skills: list[Skill] = (),
        memory_service: MemoryService | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
):
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
            # YoutubeSearchTool(),  # Bị YouTube chặn IP, thay bằng nexlev_youtube_search
            # YoutubeTranscriptTool(workspace_dir=agent_workspace_dir),

            # NexLev: lấy dữ liệu YouTube qua API của NexLev nên không bị chặn IP
            NexlevYoutubeSearchTool(nexlev_api_key=Config.NEXLEV_API_KEY, youtube_api_key=Config.YOUTUBE_API_KEY),
            NexlevYoutubeTranscriptTool(workspace_dir=agent_workspace_dir, api_key=Config.NEXLEV_API_KEY),
            NexlevYoutubeCommentsTool(workspace_dir=agent_workspace_dir, api_key=Config.NEXLEV_API_KEY),

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
            *([LoadSkillTool(skills=on_demand_skills)] if on_demand_skills else []),

            # Bộ nhớ dài hạn: chỉ có khi router truyền user đang đăng nhập
            *(
                [
                    RememberTool(memory_service=memory_service, user_id=user_id, conversation_id=conversation_id),
                    ForgetTool(memory_service=memory_service, user_id=user_id),
                ]
                if memory_service is not None and user_id is not None else []
            ),
        ]
    )


def build_workspace_service() -> WorkspaceService:
    """
    Tạo service quản lý workspace.
    ROOT_AGENT_WORKSPACE là thư mục gốc chứa toàn bộ
    workspace của các user/conversation.
    """
    return LocalWorkspaceService(
        workspace_root=Config.AGENT_ROOT_WORKSPACE
    )


def build_token_service() -> TokenService:
    return JWTTokenService(
        secret_key=Config.JWT_SECRET_KEY,  # Khóa bí mật dùng để ký và kiểm tra token
        algorithm=Config.JWT_ALGORITHM,  # Thuật toán ký, ví dụ HS256
        expire_minutes=Config.JWT_EXPIRE_MINUTES,  # Số phút token còn hiệu lực
    )


def build_agent_service(
        agent_workspace_dir,
        skills: list[Skill] = (),
        memory_service: MemoryService | None = None,
        user_id: int | None = None,
        conversation_id: int | None = None,
):
    reasoner = build_reasoner()

    return AgentService(
        model_reasoner=reasoner,
        tool_executor=build_tool_manager(
            agent_workspace_dir,
            reasoner,
            skills,
            memory_service=memory_service,
            user_id=user_id,
            conversation_id=conversation_id,
        ),
    )


def build_password_hasher() -> PasswordHasher:
    return BcryptPasswordHasher()


def build_file_storage(workspace_root: Path) -> FileStorage:
    '''Đọc/ghi file vật lý, chỉ trong workspace_root (thường là workspace của một conversation)'''
    return LocalFileStorage(workspace_root=workspace_root)


def build_workspace_scanner() -> WorkspaceScanner:
    return LocalWorkspaceScanner()


def build_unit_of_work() -> UnitOfWork:
    '''Phiên CSDL: hiện dùng PostgreSQL, đổi CSDL thì chỉ cần thay adapter ở đây'''
    return PostgresUnitOfWork()


class AppContainer:
    '''
    Gom các factory ở trên thành một đối tượng để truyền cho tầng giao tiếp (API).
    Khớp với Protocol ApiContainer ở src/pre/api/container.py mà không cần import tầng pre.
    '''

    def unit_of_work(self) -> UnitOfWork:
        return build_unit_of_work()

    def token_service(self) -> TokenService:
        return build_token_service()

    def password_hasher(self) -> PasswordHasher:
        return build_password_hasher()

    def workspace_service(self) -> WorkspaceService:
        return build_workspace_service()

    def file_storage(self, workspace_root: Path) -> FileStorage:
        return build_file_storage(workspace_root)

    def workspace_scanner(self) -> WorkspaceScanner:
        return build_workspace_scanner()

    def agent_service(
            self,
            workspace_dir: Path,
            skills: list[Skill],
            memory_service: MemoryService | None = None,
            user_id: int | None = None,
            conversation_id: int | None = None,
    ) -> AgentService:
        return build_agent_service(
            workspace_dir,
            skills,
            memory_service=memory_service,
            user_id=user_id,
            conversation_id=conversation_id,
        )

    def title_reasoner(self):
        return build_title_reasoner()

    def lesson_reasoner(self):
        return build_lesson_reasoner()
