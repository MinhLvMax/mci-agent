from fastapi import FastAPI

from src.pre.api.routers.signin_router import signin_router
from src.pre.api.routers.signup_router import signup_router
from src.pre.api.routers.chat_router import chat_router
from src.pre.api.routers.conversation.new_conversation_router import new_conversation_router
from src.pre.api.routers.conversation.delete_conversation_router import delete_conversation_router
from src.pre.api.routers.conversation.update_conversation_router import update_conversation_router
from src.pre.api.routers.conversation.list_conversation_router import list_conversation_router
from src.pre.api.routers.list_message_router import list_message_router
from src.pre.api.routers.files.delete_file_router import delete_file_router
from src.pre.api.routers.files.get_file_router import get_file_router
from src.pre.api.routers.files.list_files_router import list_files_router
from src.pre.api.routers.files.download_file_router import download_file_router
from src.pre.api.routers.files.upload_file_router import upload_file_router

app = FastAPI()

# khai báo ra bao nhiêu router thì đưa hết vào đây
app.include_router(signin_router)
app.include_router(signup_router)
app.include_router(chat_router)
app.include_router(new_conversation_router)
app.include_router(delete_conversation_router)
app.include_router(update_conversation_router)
app.include_router(list_conversation_router)
app.include_router(list_message_router)
app.include_router(delete_file_router)
app.include_router(get_file_router)
app.include_router(list_files_router)
app.include_router(download_file_router)
app.include_router(upload_file_router)

# Lệnh chạy
# uvicorn src.pre.call_api.main:app --reload
