from fastapi import APIRouter
from pydantic import BaseModel
from src.app.services.postgre_db import create_postgres_connection
from src.app.services.postgre_db.postgre_messages_repository import PostgreMessegesRepository
from src.app.usecases.chat_usecase import ChatUseCase, ChatUseCaseCommand
from src.dom.entities.message import Message
from src.bootstrap import build_agent_service


class ChatRequest(BaseModel):
    conversation_id: int
    new_message: str


class ChatResponse(BaseModel):
    message: str


chat_router = APIRouter(
    prefix='/chat'
)


@chat_router.post(
    path='/',
    response_model=ChatResponse
)
def chat(request: ChatRequest) -> ChatResponse:
    connection = create_postgres_connection()
    try:
        repository = PostgreMessegesRepository(connection)
        usecase = ChatUseCase(
            agent=build_agent_service(),
            conversation_repository=repository
        )
        result = usecase.execute(
            ChatUseCaseCommand(
                conversation_id=request.conversation_id,
                messages=Message(
                    role='user',
                    content=request.new_message,
                )
            )
        )
        return ChatResponse(
            message=result.message.content
        )
    finally:
        connection.close()
