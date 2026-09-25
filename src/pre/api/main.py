from fastapi import FastAPI

from src.pre.api.routers.signin_router import signin_router
from src.pre.api.routers.chat_router import chat_router
from src.pre.api.routers.conversation.new_conversation_router import new_conversation_router
from src.pre.api.routers.conversation.delete_conversation_router import delete_conversation_router
from src.pre.api.routers.conversation.update_conversation_router import update_conversation_router

app = FastAPI()

# khai báo ra bao nhiêu router thì đưa hết vào đây
app.include_router(signin_router)
app.include_router(chat_router)
app.include_router(new_conversation_router)
app.include_router(delete_conversation_router)
app.include_router(update_conversation_router)

# Lệnh chạy
# uvicorn src.pre.api.main:app --reload
