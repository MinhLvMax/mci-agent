from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.app.services.file_storage import FileStorage

from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_files_repository import (
    PostgreFilesRepository
)
from src.app.services.postgre_db.postgre_conversations_repository import PostgreConversationsRepository
from src.app.services.workspace_service import WorkspaceService

from src.app.usecases.file_management_usecases.get_file_content_usecase import (
    GetFileContentUseCase,
    GetFileContentCommand,
)

from src.dom.entities.file import File
from src.config import Config


# ============================================================
# REQUEST
# ============================================================

class GetFileRequest(BaseModel):
    """
    Frontend chỉ cần gửi ID của file, gửi thêm conversation id để tìm workspace path
    Không cho frontend gửi path trực tiếp vì path phải được
    lấy từ metadata đã lưu trong PostgreSQL.
    """
    file_id: int


# ============================================================
# RESPONSE
# ============================================================

class GetFileResponse(BaseModel):
    file: File
    content: Any


# ============================================================
# ROUTER
# ============================================================

get_file_router = APIRouter(
    prefix="/get_file"
)


@get_file_router.post(
    path="/",
    response_model=GetFileResponse,
)
def get_file(
        request: GetFileRequest
) -> GetFileResponse:
    connection = create_postgres_connection()

    try:
        # Repository dùng để lấy metadata của file.
        files_repository = PostgreFilesRepository(
            connection=connection
        )

        # Call csdl để lấy bản ghi đối tượng file
        file = files_repository.get_by_id(
            file_id=request.file_id
        )

        # Nếu không có bản ghi thì ném lỗi 404
        if file is None:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )

        # Khai báo repo hội thoại
        conversation_repository = PostgreConversationsRepository(connection)

        # tìm hội thoại dựa trên id hội thoại nằm trong bản ghi file
        conversation = conversation_repository.get_by_id(
            conversation_id=file.conversation_id
        )

        # Không thấy hội thoại thì ném lỗi
        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found"
            )

        workspace_service = WorkspaceService(
            workspace_root=Config.AGENT_ROOT_WORKSPACE
        )

        workspace_dir = (
            workspace_service.get_conversation_workspace(
                user_id=conversation.user_id,
                conversation_id=conversation.id,
            )
        )

        # FileStorage dùng để đọc file vật lý trên server.
        file_storage = FileStorage(
            workspace_root=workspace_dir
        )

        # Use case kết hợp:
        #
        # PostgreSQL metadata
        #       +
        # file vật lý
        #
        usecase = GetFileContentUseCase(
            files_repository=files_repository,
            file_storage=file_storage,
        )

        result = usecase.execute(
            GetFileContentCommand(
                file_id=request.file_id
            )
        )

        return GetFileResponse(
            file=result.file,
            content=result.content,
        )

    finally:
        connection.close()
