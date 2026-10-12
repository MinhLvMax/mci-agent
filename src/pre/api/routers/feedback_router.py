from fastapi import APIRouter, Depends
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, model_validator
from src.app.usecases.extract_lessons_usecase import ExtractLessonsUseCaseCommand
from src.app.usecases.send_feedback_usecase import SendFeedbackUsecase, SendFeedbackUseCaseCommand
from src.pre.api.container import ApiContainer, get_container
from src.pre.api.dependencies import get_current_user_id, get_owned_conversation
from src.pre.api.lesson_runner import extract_lessons_in_background, last_content


class SendFeedbackRequest(BaseModel):
    # Bỏ khoảng trắng hai đầu trước khi kiểm tra
    content: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] = ""
    conversation_id: int | None = None  # Hội thoại đang mở lúc gửi, không có thì để trống
    rating: Literal[1, -1] | None = None  # 👍 = 1, 👎 = -1
    kind: Literal['correction', 'preference', 'bug', 'other'] | None = None

    @model_validator(mode='after')
    def check_not_empty(self):
        # Chỉ bấm 👍/👎 thì được để trống nội dung, còn lại phải có nội dung (422)
        if not self.content and self.rating is None:
            raise ValueError("content or rating is required")
        return self


class SendFeedbackResponse(BaseModel):
    id: int


feedback_router = APIRouter(
    prefix='/send_feedback'
)


@feedback_router.post(
    path='/',
    response_model=SendFeedbackResponse
)
def send_feedback_controller(
        request: SendFeedbackRequest,
        user_id: int = Depends(get_current_user_id),  # User id lấy từ token
        container: ApiContainer = Depends(get_container),
) -> SendFeedbackResponse:
    with container.unit_of_work() as uow:
        history = []
        if request.conversation_id is not None:
            get_owned_conversation(  # Chỉ cho gắn góp ý vào hội thoại của chính mình
                uow.conversations,
                conversation_id=request.conversation_id,
                user_id=user_id,
            )
            history = uow.messages.get_messages(conversation_id=request.conversation_id)

        usecase = SendFeedbackUsecase(uow.feedbacks)
        result = usecase.execute(
            SendFeedbackUseCaseCommand(
                user_id=user_id,
                conversation_id=request.conversation_id,
                content=request.content,
                rating=request.rating,
                kind=request.kind
            )
        )

        # Góp ý nào cũng đưa cho model xem có bài học không (kèm lượt chat gần nhất làm ngữ cảnh)
        extract_lessons_in_background(container, ExtractLessonsUseCaseCommand(
            user_id=user_id,
            conversation_id=request.conversation_id,
            user_message=last_content(history, 'user'),
            assistant_reply=last_content(history, 'assistant'),
            feedback_content=request.content,
            feedback_rating=request.rating,
            feedback_kind=request.kind,
            feedback_id=result.id,
        ))

        return SendFeedbackResponse(
            id=result.id
        )
