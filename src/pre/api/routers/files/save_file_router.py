from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id

from src.app.usecases.file_management_usecases.save_file_content_usecase import (
    SaveFileContentUseCase,
    SaveFileContentCommand,
)

from src.dom.entities.file import File


class SaveFileRequest(BaseModel):
    file_id: int
    content: str  # Nội dung thô user gõ, kể cả file json/csv


class SaveFileResponse(BaseModel):
    file: File


save_file_router = APIRouter(
    prefix="/save_file"
)


@save_file_router.post(
    path="/",
    response_model=SaveFileResponse,
)
def save_file(
        request: SaveFileRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
        container: ApiContainer = Depends(get_container),
) -> SaveFileResponse:
    with container.unit_of_work() as uow:
        files_repository = uow.files

        file = files_repository.get_by_id(
            file_id=request.file_id
        )

        if file is None:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )

        conversation = uow.conversations.get_by_id(
            conversation_id=file.conversation_id
        )

        if conversation is None or conversation.user_id != user_id:  # File của người khác thì coi như không tồn tại
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )

        workspace_dir = container.workspace_service().get_conversation_workspace(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
        )

        usecase = SaveFileContentUseCase(
            files_repository=files_repository,
            file_storage=container.file_storage(workspace_dir),
        )

        try:
            result = usecase.execute(
                SaveFileContentCommand(
                    file_id=request.file_id,
                    content=request.content,
                )
            )

        except FileNotFoundError:  # Có bản ghi nhưng file vật lý đã mất
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )

        except ValueError as e:  # Thư mục hoặc loại file không sửa được
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

        return SaveFileResponse(
            file=result.file,
        )
