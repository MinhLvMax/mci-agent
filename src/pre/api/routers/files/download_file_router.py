import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from src.pre.api.dependencies import get_current_user_id

from src.app.services.file_storage import FileStorage

from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_files_repository import (
    PostgreFilesRepository
)
from src.app.services.postgre_db.postgre_conversations_repository import (
    PostgreConversationsRepository
)

from src.app.usecases.file_management_usecases.download_file_usecase import (
    DownloadFileUseCase,
    DownloadFileCommand,
)

from src.bootstrap import build_workspace_service


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
) -> FileResponse:
    """
    Trả về nguyên bytes của file gốc.

    Khác với /get_file/:
    - /get_file/ parse nội dung (json -> dict, csv -> list[dict])
      để hiển thị preview, chỉ hỗ trợ một số extension.
    - /download_file/ trả file y nguyên, hỗ trợ mọi loại file.
    """

    connection = create_postgres_connection()

    try:
        files_repository = PostgreFilesRepository(
            connection=connection
        )

        file = files_repository.get_by_id(
            file_id=request.file_id
        )

        if file is None:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )

        conversation = PostgreConversationsRepository(
            connection
        ).get_by_id(
            conversation_id=file.conversation_id
        )

        if conversation is None or conversation.user_id != user_id:  # File của người khác thì coi như không tồn tại
            raise HTTPException(
                status_code=404,
                detail="File not found"  # Cùng thông báo với file không tồn tại để không lộ thông tin
            )

        workspace_dir = build_workspace_service().get_conversation_workspace(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
        )

        usecase = DownloadFileUseCase(
            files_repository=files_repository,
            file_storage=FileStorage(
                workspace_root=workspace_dir
            ),
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

    finally:
        # FileResponse chỉ đọc file khi gửi response,
        # không dùng connection nên đóng ở đây được.
        connection.close()
