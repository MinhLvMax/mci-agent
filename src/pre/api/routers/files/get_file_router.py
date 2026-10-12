from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id



from src.app.usecases.file_management_usecases.get_file_content_usecase import (
    GetFileContentUseCase,
    GetFileContentCommand,
)

from src.dom.entities.file import File

class GetFileRequest(BaseModel):
    file_id: int

class GetFileResponse(BaseModel):
    file: File
    content: Any


get_file_router = APIRouter(
    prefix="/get_file"
)

@get_file_router.post(
    path="/",
    response_model=GetFileResponse,
)
def get_file(
        request: GetFileRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
        container: ApiContainer = Depends(get_container),
) -> GetFileResponse:
    with container.unit_of_work() as uow:
        # Repository dùng để lấy metadata của file.
        files_repository = uow.files

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
        conversation_repository = uow.conversations

        # tìm hội thoại dựa trên id hội thoại nằm trong bản ghi file
        conversation = conversation_repository.get_by_id(
            conversation_id=file.conversation_id
        )

        # Không thấy hội thoại thì ném lỗi
        if conversation is None or conversation.user_id != user_id:  # File của người khác thì coi như không tồn tại
            raise HTTPException(
                status_code=404,
                detail="File not found"  # Cùng thông báo với file không tồn tại để không lộ thông tin
            )

        workspace_service = container.workspace_service()

        workspace_dir = (
            workspace_service.get_conversation_workspace(
                user_id=conversation.user_id,
                conversation_id=conversation.id,
            )
        )

        # FileStorage dùng để đọc file vật lý trên server.
        file_storage = container.file_storage(workspace_dir)

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

