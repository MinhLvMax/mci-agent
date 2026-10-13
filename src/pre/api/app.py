from fastapi import FastAPI

from src.pre.api.container import ApiContainer

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
from src.pre.api.routers.files.save_file_router import save_file_router
from src.pre.api.routers.feedback_router import feedback_router
from src.pre.api.routers.memories_router import memories_router
from src.pre.api.routers.admin_users_router import admin_users_router
from src.pre.api.routers.admin_skills_router import admin_skills_router
from src.pre.api.routers.admin_models_router import admin_models_router, models_router


ROUTERS = [
    signin_router,
    signup_router,
    chat_router,
    new_conversation_router,
    delete_conversation_router,
    update_conversation_router,
    list_conversation_router,
    list_message_router,
    delete_file_router,
    get_file_router,
    list_files_router,
    download_file_router,
    upload_file_router,
    save_file_router,
    feedback_router,
    memories_router,
    admin_users_router,
    admin_skills_router,
    admin_models_router,
    models_router,
]


def create_app(container: ApiContainer) -> FastAPI:
    '''
    Tạo FastAPI app. Tầng pre không tự lắp ráp phụ thuộc:
    container (CSDL, agent, JWT...) do entries_point lấy từ bootstrap rồi truyền vào đây.
    '''
    app = FastAPI()
    app.state.container = container  # Router lấy lại qua Depends(get_container)

    # khai báo ra bao nhiêu router thì đưa hết vào ROUTERS
    for router in ROUTERS:
        app.include_router(router)

    return app
