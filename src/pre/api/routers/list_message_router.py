from fastapi import APIRouter
from pydantic import BaseModel
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.app.usecases.list_messege_usecase import ListMessegeUsecase, ListMessegeUseCaseCommand

from src.dom.entities.message import Message


class ListMessageRequest(BaseModel):
    conversation_id: int


class ListMessageResponse(BaseModel):
    messages: list[Message]


list_message_router = APIRouter(
    prefix='/list_message'
)


@list_message_router.post(
    path='/',
    response_model=ListMessageResponse
)
def list_messages(request: ListMessageRequest) -> ListMessageResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreMessegesRepository(connection)
        usecase = ListMessegeUsecase(
            message_repository=repository
        )
        result = usecase.execute(
            ListMessegeUseCaseCommand(
                conversation_id=request.conversation_id,
            )
        )
        return ListMessageResponse(
            messages=result.messages
        )
    finally:
        connection.close()
