from fastapi import FastAPI

from src.pre.api.routers.signin import signin_router

app = FastAPI()

# khai báo ra bao nhiêu router thì đưa hết vào đây
app.include_router(
    signin_router
)
