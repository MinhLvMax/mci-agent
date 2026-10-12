from fastapi import APIRouter, Depends, File as FormFile, Form, HTTPException, UploadFile
from pydantic import BaseModel

from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation

from src.app.services.workspace_sync_service import WorkspaceSyncService


from src.app.usecases.file_management_usecases.upload_file_usecase import (
    UploadFileUseCase,
    UploadFileCommand,
)

from src.dom.entities.file import File

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # Giới hạn 50 MB cho mỗi file
CHUNK_BYTES = 1024 * 1024  # Đọc từng khối 1 MB để dừng sớm khi file quá lớn


class UploadFileResponse(BaseModel):
    file: File


upload_file_router = APIRouter(
    prefix="/upload_file"
)


def _read_limited(
        upload: UploadFile
) -> bytes:
    """
    Đọc file upload nhưng dừng ngay khi vượt MAX_UPLOAD_BYTES,
    không nạp hết file quá lớn vào RAM rồi mới từ chối.
    """

    chunks: list[bytes] = []  # Các khối đã đọc
    total = 0  # Tổng số byte đã đọc

    while chunk := upload.file.read(CHUNK_BYTES):  # Đọc đồng bộ từ file tạm FastAPI đã lưu
        total += len(chunk)  # Cộng dồn kích thước

        if total > MAX_UPLOAD_BYTES:  # Vượt giới hạn
            raise HTTPException(
                status_code=413,  # 413 = Payload Too Large
                detail="File exceeds 50 MB limit",
            )

        chunks.append(chunk)  # Còn trong giới hạn thì giữ lại

    return b"".join(chunks)  # Ghép lại thành nội dung đầy đủ


@upload_file_router.post(
    path="/",
    response_model=UploadFileResponse,
)
def upload_file(  # Dùng def thường để FastAPI chạy trong threadpool, không chặn event loop khi gọi DB
        conversation_id: int = Form(),  # Gửi dạng form field vì request là multipart
        file: UploadFile = FormFile(),  # File người dùng chọn
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
        container: ApiContainer = Depends(get_container),
) -> UploadFileResponse:
    content = _read_limited(file)  # Kiểm tra dung lượng trước khi đụng tới DB hay ổ đĩa

    with container.unit_of_work() as uow:
        conversation = get_owned_conversation(  # Chỉ cho upload vào conversation của chính mình
            uow.conversations,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        workspace_dir = container.workspace_service().get_conversation_workspace(  # Thư mục vật lý của conversation
            user_id=conversation.user_id,
            conversation_id=conversation.id,
        )

        files_repository = uow.files

        # Đồng bộ trước để metadata cũ khớp với ổ đĩa,
        # tránh trùng unique (conversation_id, path) với bản ghi đã lỗi thời.
        WorkspaceSyncService(
            files_repository=files_repository,
            scanner=container.workspace_scanner(),
        ).sync(
            conversation_id=conversation.id,
            workspace_dir=workspace_dir,
        )

        usecase = UploadFileUseCase(
            files_repository=files_repository,
            file_storage=container.file_storage(workspace_dir),
        )

        try:
            result = usecase.execute(
                UploadFileCommand(
                    conversation_id=conversation.id,
                    filename=file.filename or "",  # Client có thể không gửi tên file
                    content=content,
                )
            )

        except ValueError as e:  # Tên file không hợp lệ sau khi làm sạch
            raise HTTPException(
                status_code=400,
                detail=str(e),
            )

        return UploadFileResponse(
            file=result.file
        )

