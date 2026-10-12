from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation

from src.app.services.workspace_sync_service import WorkspaceSyncService
from src.app.usecases.file_management_usecases.list_files_usecase import (
    ListFilesUseCase,
    ListFilesCommand,
)

from src.dom.entities.file import File


# ============================================================
# REQUEST
# ============================================================

class ListFilesRequest(BaseModel):
    """
    Dữ liệu frontend gửi lên để yêu cầu lấy danh sách file
    của một conversation.
    """

    conversation_id: int


# ============================================================
# RESPONSE
# ============================================================

class ListFilesResponse(BaseModel):
    """
    Danh sách metadata file thuộc conversation.

    API này KHÔNG trả nội dung file.
    Nội dung chỉ được load khi frontend gọi API get_file.
    """

    files: list[File]


# ============================================================
# ROUTER
# ============================================================

list_files_router = APIRouter(
    prefix="/list_files"
)


@list_files_router.post(
    path="/",
    response_model=ListFilesResponse,
)
def list_files(
        request: ListFilesRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
        container: ApiContainer = Depends(get_container),
) -> ListFilesResponse:

    # Mỗi request mở một phiên CSDL, ra khỏi "with" là tự đóng.
    with container.unit_of_work() as uow:
        conversation = get_owned_conversation(  # Chỉ cho xem file trong conversation của chính mình
            uow.conversations,
            conversation_id=request.conversation_id,
            user_id=user_id,
        )

        # Repository chịu trách nhiệm truy vấn bảng files.
        repository = uow.files

        # Filesystem là nguồn sự thật, nên đồng bộ metadata trước khi list.
        #
        # Nếu chỉ sync ở cuối request /chat/ thì khi request đó bị lỗi
        # hoặc bị ngắt giữa chừng, file Agent đã tạo sẽ không bao giờ
        # xuất hiện trong DB và trên giao diện.
        workspace_dir = container.workspace_service().get_conversation_workspace(
            user_id=conversation.user_id,
            conversation_id=conversation.id,
        )

        WorkspaceSyncService(
            files_repository=repository,
            scanner=container.workspace_scanner(),
        ).sync(
            conversation_id=conversation.id,
            workspace_dir=workspace_dir,
        )

        # Khởi tạo use case.
        usecase = ListFilesUseCase(
            files_repository=repository
        )

        # Chuyển request DTO thành command của application layer.
        result = usecase.execute(
            ListFilesCommand(
                conversation_id=request.conversation_id
            )
        )

        # Chuyển kết quả use case thành response API.
        return ListFilesResponse(
            files=result.files
        )