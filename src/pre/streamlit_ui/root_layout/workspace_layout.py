import streamlit as st

from src.pre.streamlit_ui.state_manager import StateManager
from src.pre.streamlit_ui.actions import UIActions
from src.pre.streamlit_ui.styles import render_empty_state
from src.pre.call_api.api_client import UnauthorizedError

FILE_ICONS = {
    "md": ":material/article:",
    "markdown": ":material/article:",
    "txt": ":material/notes:",
    "log": ":material/notes:",
    "json": ":material/data_object:",
    "csv": ":material/table_chart:",
    "py": ":material/code:",
    "sql": ":material/code:",
    "yaml": ":material/settings:",
    "yml": ":material/settings:",
}

DEFAULT_FILE_ICON = ":material/draft:"

# Các loại file backend đọc được qua /get_file/ (khớp FileStorage.SUPPORTED_EXTENSIONS).
# File khác (pdf, ảnh...) vẫn lưu và tải về được nhưng không xem trước.
PREVIEWABLE_TYPES = {
    "txt", "md", "markdown", "py", "js", "ts", "html", "css",
    "xml", "yaml", "yml", "sql", "log", "ini", "cfg", "json", "csv",
}


def render_workspace(
        work_space_items: list[StateManager.WorkSpaceItem],
        opened_file: StateManager.OpenedFile | None,
        action: UIActions,
        height: int,
):
    with st.container(
            height=height,
            border=True,
    ):
        # Đang mở file thì hiện nội dung file,
        # không thì hiện danh sách file.
        if opened_file is not None:
            render_file_preview(
                opened_file,
                action,
            )

        else:
            render_file_list(
                work_space_items,
                action,
            )


def render_file_list(
        work_space_items: list[StateManager.WorkSpaceItem],
        action: UIActions,
):
    # Không hiện folder ra giao diện, chỉ hiện file với đường dẫn tương đối
    files = [
        item
        for item in work_space_items
        if not item.is_directory
    ]

    with st.container(
            horizontal=True,
            vertical_alignment="center",
    ):
        st.markdown(
            "#### :material/folder_open: Workspace",
            anchors=False,
        )

        if files:
            st.badge(
                f"{len(files)} file",
                color="gray",
            )

    render_drop_zone(
        action
    )

    if action.state.upload_errors:  # Lần upload trước có file bị lỗi
        st.warning(
            "Một số file chưa tải lên được:\n\n"
            + "\n".join(f"- {error}" for error in action.state.upload_errors),  # Mỗi lỗi một dòng
            icon=":material/warning:",
        )

    if not files:
        render_empty_state(
            icon=":material/folder_off:",
            title="Chưa có file",
            hint="File do Agent tạo hoặc bạn tải lên sẽ xuất hiện ở đây.",
        )
        return

    with st.container(
            key="file_list",
            gap=None,
    ):
        for item in files:

            # Một hàng gồm:
            #
            # [file name........] [size] [delete] [download]
            #
            file_col, size_col, delete_col, download_col = st.columns(
                [7, 2, 1, 1],
                vertical_alignment="center",
            )

            # -------------------------
            # OPEN FILE
            # -------------------------

            with file_col:

                if st.button(
                        item.path,
                        key=f"open_file_{item.file_id}",
                        icon=FILE_ICONS.get(
                            item.item_type.lower(),
                            DEFAULT_FILE_ICON,
                        ),
                        type="tertiary",
                        width="stretch",
                        help=item.path,
                ):
                    if item.item_type.lower() in PREVIEWABLE_TYPES:  # File text thì lấy nội dung để xem
                        action.open_file(
                            file_id=item.file_id
                        )

                    else:  # File nhị phân: không gọi /get_file/ vì backend không đọc được
                        action.open_file_without_preview(
                            file_id=item.file_id,
                            name=item.name,
                            item_type=item.item_type,
                        )

                    st.rerun()

            with size_col:

                st.caption(
                    format_size(item.size),
                    text_alignment="right",
                )

            # -------------------------
            # DELETE FILE
            # -------------------------

            with delete_col:

                if st.button(
                        ":material/delete:",
                        key=f"delete_file_{item.file_id}",
                        type="tertiary",
                        help="Xóa file",
                ):
                    action.delete_file(
                        file_id=item.file_id
                    )

                    st.rerun()

            # -------------------------
            # DOWNLOAD FILE
            # -------------------------

            with download_col:

                # data là hàm nên chỉ gọi API khi user bấm nút,
                # không tải trước toàn bộ file mỗi lần render.
                # file_id=item.file_id để mỗi lambda giữ đúng file của hàng này.
                st.download_button(
                    ":material/download:",
                    data=lambda file_id=item.file_id: action.download_file(
                        file_id=file_id
                    ),
                    file_name=item.name,
                    mime=item.mime_type or "application/octet-stream",
                    key=f"download_file_{item.file_id}",
                    type="tertiary",
                    help="Tải file",
                    on_click="ignore",
                )


def render_file_preview(
        file: StateManager.OpenedFile,
        action: UIActions,
):
    back_col, name_col = st.columns(
        [1, 9],
        vertical_alignment="center",
    )

    with back_col:

        if st.button(
                ":material/arrow_back:",
                key="close_file",
                type="tertiary",
                help="Quay lại danh sách file",
        ):
            action.close_file()

            st.rerun()

    with name_col:

        icon = FILE_ICONS.get(
            file.item_type.lower(),
            DEFAULT_FILE_ICON,
        )

        st.markdown(
            f"**{icon} {file.name}**"
        )

    st.divider()

    with st.container(
            key="file_preview",
    ):
        render_file_content(
            file,
            action,
        )


def render_drop_zone(
        action: UIActions,
):
    """
    Vùng kéo thả luôn hiện ở đầu Workspace.

    Thả file vào (hoặc bấm để chọn) là tự upload ngay, không cần bấm nút.
    """

    key = f"uploader_{action.state.upload_nonce}"  # Key đổi sau mỗi lần upload để vùng thả trống trở lại

    st.file_uploader(
        "Kéo thả file vào đây để tải lên workspace",
        accept_multiple_files=True,  # Thả nhiều file một lần
        max_upload_size=50,  # Chặn ngay trên giao diện file lớn hơn 50 MB, backend vẫn kiểm tra lại
        key=key,
        on_change=_upload_dropped_files,  # Tự chạy upload ngay khi có file được thả vào
        args=(action, key),  # Truyền action và key để callback lấy được file vừa thả
        label_visibility="collapsed",  # Ẩn nhãn, vùng thả đã tự có hướng dẫn
    )


def _upload_dropped_files(
        action: UIActions,
        key: str,
):
    """
    Callback của vùng kéo thả, Streamlit gọi trước khi vẽ lại trang.

    Không cần st.rerun(): sau callback Streamlit tự chạy lại script.
    """

    uploaded_files = st.session_state.get(key)  # Danh sách file vừa được thả vào

    if not uploaded_files:  # Callback cũng chạy khi user bấm "x" xóa file khỏi vùng thả
        return

    try:
        action.upload_files(  # Gửi từng file lên backend rồi tải lại danh sách file
            uploaded_files
        )

    except UnauthorizedError as e:  # Callback chạy ngoài try của main.py nên phải tự xử lý hết phiên
        action.state.logout()  # Xóa phiên để quay về màn hình đăng nhập
        action.state.auth_notice = str(e)  # Hiện lý do ở form đăng nhập
        return

    action.state.upload_nonce += 1  # Đổi key để lần vẽ sau vùng thả trống, sẵn sàng cho lần thả tiếp


def render_file_content(
        file: StateManager.OpenedFile,
        action: UIActions,
):
    """
    Render content tương ứng với từng loại file.
    """

    file_type = file.item_type.lower()

    # Không xem trước được (pdf, ảnh, file không có đuôi...)
    if file_type not in PREVIEWABLE_TYPES:
        st.info(
            "Không hỗ trợ xem trước loại file này. Hãy tải về để mở trên máy.",
            icon=":material/visibility_off:",
        )

        st.download_button(
            "Tải về",
            data=lambda: action.download_file(  # Chỉ gọi API khi user bấm
                file_id=file.file_id
            ),
            file_name=file.name,
            icon=":material/download:",
            key=f"preview_download_{file.file_id}",
            on_click="ignore",  # Tải xong không cần vẽ lại trang
        )
        return

    # Markdown
    if file_type in {
        "md",
        "markdown",
    }:
        st.markdown(
            file.content
        )

    # JSON
    elif file_type == "json":
        st.json(
            file.content
        )

    # CSV
    elif file_type == "csv":
        st.dataframe(
            file.content,
            width="stretch",
        )

    # Text
    elif file_type in {
        "txt",
        "log",
        "py",
        "sql",
        "yaml",
        "yml",
    }:
        st.code(
            str(file.content),
            language=file_type if file_type in {"py", "sql", "yaml"} else None,
            wrap_lines=True,
        )

    # Fallback
    else:
        st.write(
            file.content
        )


def format_size(
        size: int
) -> str:
    if size < 1024:
        return f"{size} B"

    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"

    return f"{size / (1024 * 1024):.1f} MB"
