"""
Entrypoint của giao diện web (Streamlit). Giao diện chỉ gọi backend qua HTTP nên không cần bootstrap.

Lệnh chạy (từ thư mục gốc dự án):
    streamlit run src/entries_point/web_ui.py --server.runOnSave true
"""
import sys
from pathlib import Path

# Streamlit chạy file này như một script nên thư mục gốc dự án chưa nằm trong sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st  # noqa: E402

from src.pre.streamlit_ui.root_layout import root_layout
from src.pre.streamlit_ui.actions import UIActions
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.composition import build_api_service
from src.pre.call_api.api_client import UnauthorizedError
from src.config import Config

state = StateManager()

try:
    root_layout(
        state_manager=state,
        actions=UIActions(
            state=state,
            api=build_api_service(
                base_url=Config.API_BASE_URL,
                access_token=state.access_token  # Mỗi lần rerun tạo client kèm token đang lưu trong phiên
            )
        )
    )

except UnauthorizedError as e:  # Bất kỳ API nào báo token hết hạn hoặc không hợp lệ
    state.logout()  # Xóa phiên cũ để quay về màn hình đăng nhập
    state.auth_notice = str(e)  # Giữ lại lý do để hiện cho user biết
    st.rerun()  # Vẽ lại trang, lúc này sẽ là form đăng nhập
