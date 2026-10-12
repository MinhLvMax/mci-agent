from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id



from src.app.usecases.file_management_usecases.delete_file_usecase import (
    DeleteFileUseCase,
    DeleteFileCommand,
)



class DeleteFileRequest(BaseModel):
    file_id: int


class DeleteFileResponse(BaseModel):
    success: bool


delete_file_router = APIRouter(
    prefix="/delete_file"
)


@delete_file_router.post(
    path="/",
    response_model=DeleteFileResponse,
)
def delete_file(
        request: DeleteFileRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
        container: ApiContainer = Depends(get_container),
) -> DeleteFileResponse:
    with container.unit_of_work() as uow:
        # ============================================================
        # 1. Lấy metadata file
        # ============================================================

        files_repository = uow.files

        file = files_repository.get_by_id(
            file_id=request.file_id
        )

        if file is None:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )

        # ============================================================
        # 2. Tìm conversation chứa file
        # ============================================================

        conversation_repository = uow.conversations

        conversation = conversation_repository.get_by_id(
            conversation_id=file.conversation_id
        )

        if conversation is None or conversation.user_id != user_id:  # File của người khác thì coi như không tồn tại
            raise HTTPException(
                status_code=404,
                detail="File not found"  # Cùng thông báo với file không tồn tại để không lộ thông tin
            )

        # ============================================================
        # 3. Xác định workspace vật lý của conversation
        # ============================================================

        workspace_service = container.workspace_service()

        workspace_dir = (
            workspace_service.get_conversation_workspace(
                user_id=conversation.user_id,
                conversation_id=conversation.id,
            )
        )

        # ============================================================
        # 4. FileStorage chỉ được phép thao tác trong workspace này
        # ============================================================

        file_storage = container.file_storage(workspace_dir)

        # ============================================================
        # 5. Thực hiện xóa
        # ============================================================

        usecase = DeleteFileUseCase(
            files_repository=files_repository,
            file_storage=file_storage,
        )

        result = usecase.execute(
            DeleteFileCommand(
                file_id=request.file_id
            )
        )

        return DeleteFileResponse(
            success=result.success
        )

