import shutil
from pathlib import Path


class LocalWorkspaceService:
    """
    Service chịu trách nhiệm xác định workspace vật lý
    tương ứng với từng user và conversation.

    Cấu trúc:

        workspace_root/
            user_{user_id}/
                conversation_{conversation_id}/
    """

    def __init__(
            self,
            workspace_root: str | Path
    ):
        self.workspace_root = Path(
            workspace_root
        ).resolve()

        self.workspace_root.mkdir(
            parents=True,
            exist_ok=True,
        )

    def get_conversation_workspace(
            self,
            user_id: int,
            conversation_id: int,
    ) -> Path:
        """
        Trả về workspace của một conversation.

        Nếu chưa tồn tại thì tự tạo.
        """

        workspace = (
                self.workspace_root
                / f"user_{user_id}"
                / f"conversation_{conversation_id}"
        ).resolve()

        # Kiểm tra an toàn để đảm bảo workspace
        # không thể thoát ra ngoài workspace_root.
        if not workspace.is_relative_to(
                self.workspace_root
        ):
            raise ValueError(
                "Invalid workspace path"
            )

        workspace.mkdir(
            parents=True,
            exist_ok=True,
        )

        return workspace

    def delete_conversation_workspace(
            self,
            user_id: int,
            conversation_id: int,
    ) -> bool:
        """
        Xóa toàn bộ workspace vật lý của một conversation.

        Trả về:
            True  -> đã xóa.
            False -> workspace không tồn tại.
        """

        workspace = (
                self.workspace_root
                / f"user_{user_id}"
                / f"conversation_{conversation_id}"
        ).resolve()

        if not workspace.is_relative_to(
                self.workspace_root
        ):
            raise ValueError(
                "Invalid workspace path"
            )

        if not workspace.is_dir():
            return False

        shutil.rmtree(workspace)

        return True
