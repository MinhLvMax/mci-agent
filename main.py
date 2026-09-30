from src.pre.streamlit_ui.root_layout import root_layout
from src.pre.streamlit_ui.actions import UIActions
from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.composition import build_api_service

root_layout(
    state_manager=StateManager(),
    actions=UIActions(
        state=StateManager(),
        api=build_api_service()
    )
)
# Lệnh chạy: streamlit run main.py --server.runOnSave true
