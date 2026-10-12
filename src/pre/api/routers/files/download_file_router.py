import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id



from src.app.usecases.file_management_usecases.download_file_usecase import (
    DownloadFileUseCase,
    DownloadFileCommand,
)



class DownloadFileRequest(BaseModel):
    file_id: int


download_file_router = APIRouter(
    prefix="/download_file"
)


@download_file_router.post(
    path="/",
    response_class=FileResponse,
)
def download_file(
        request: DownloadFileRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
        container: ApiContainer = Depends(get_container),
) -> FileResponse:
    """
    Trả về nguyên bytes của file gốc.

    Khác với /get_file/:
    - /get_file/ parse nội dung (json -> dict, csv -> list[dict])
      để hiển thị preview, chỉ hỗ trợ một số extension.
    - /download_file/ trả file y nguyên, hỗ trợ mọi loại file.
    """

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
                detail="File not found"  # Cùng thông báo với file không tồn tại để không lộ thông tin
            )

        workspace_dir = container.workspace_service().get_conversation_workspace(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
        )

        usecase = DownloadFileUseCase(
            files_repository=files_repository,
            file_storage=container.file_storage(workspace_dir),
        )

        try:
            result = usecase.execute(
                DownloadFileCommand(
                    file_id=request.file_id
                )
            )

        except FileNotFoundError as e:
            # Có metadata trong DB nhưng file vật lý đã mất.
            raise HTTPException(
                status_code=404,
                detail=str(e)
            )

        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

        # FileResponse tự set Content-Disposition: attachment
        # (kể cả tên file tiếng Việt) khi truyền filename.
        return FileResponse(
            path=result.physical_path,
            filename=result.download_name,
            media_type=result.media_type,
            # Zip tạm của thư mục: gửi xong thì xóa để không đầy thư mục tạm
            background=(
                BackgroundTask(os.remove, result.physical_path)
                if result.is_temporary
                else None
            ),
        )

