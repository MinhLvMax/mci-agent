from dataclasses import dataclass
from src.app.ports.repositories import ConversationsRepository
from src.app.ports.storage import WorkspaceService


@dataclass
class DeleteConversationUseCaseCommand:
    '''Tách ra có thêm class đầu vào đầu ra như thế này dễ đọc code hơn'''
    conversation_id: int


@dataclass
class DeleteConversationUseCaseResult:
    status: bool


class DeleteConversationUsecase:
    def __init__(
            self,
            conversation_repository: ConversationsRepository,
            workspace_service: WorkspaceService,
    ):
        self.conversation_repository = conversation_repository
        self.workspace_service = workspace_service

    def execute(self, command: DeleteConversationUseCaseCommand) -> DeleteConversationUseCaseResult:
        # Phải lấy conversation trước khi xóa để biết user_id,
        # vì workspace vật lý nằm theo user_{id}/conversation_{id}.
        conversation = self.conversation_repository.get_by_id(
            conversation_id=command.conversation_id,
        )

        if conversation is None:
            return DeleteConversationUseCaseResult(
                status=False
            )

        # messages và files trong DB tự xóa theo nhờ ON DELETE CASCADE.
        status = self.conversation_repository.delete(
            conversation_id=command.conversation_id,
        )

        if status:
            self.workspace_service.delete_conversation_workspace(
                user_id=conversation.user_id,
                conversation_id=conversation.id,
            )

        return DeleteConversationUseCaseResult(
            status=status
        )
