'''
Entrypoint của backend API.

Chỗ duy nhất nối tầng giao tiếp (pre) với phần lắp ráp (bootstrap):
bootstrap tạo container chứa CSDL, agent, JWT..., create_app nhận container đó.

Lệnh chạy (từ thư mục gốc dự án):
    uvicorn src.entries_point.api:app --reload
'''
from src.bootstrap import AppContainer
from src.pre.api.app import create_app

app = create_app(container=AppContainer())
