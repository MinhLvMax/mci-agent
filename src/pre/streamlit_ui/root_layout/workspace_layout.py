import re
from dataclasses import dataclass, field

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


@dataclass
class TreeNode:
    '''Một thư mục trong cây Workspace, dựng từ đường dẫn của các file'''
    name: str
    path: str  # Đường dẫn tương đối, "" là thư mục gốc
    folders: dict[str, "TreeNode"] = field(default_factory=dict)
    files: list[StateManager.WorkSpaceItem] = field(default_factory=list)
    file_count: int = 0  # Tổng số file bên trong, kể cả thư mục con
    item: StateManager.WorkSpaceItem | None = None  # Bản ghi thư mục trong DB, cần file_id để xóa/tải zip


def build_tree(
        work_space_items: list[StateManager.WorkSpaceItem],
) -> TreeNode:
    """
    Dựng cây thư mục từ đường dẫn tương đối.

    Thư mục cha được tạo từ chính đường dẫn file nên không phụ thuộc việc DB
    có bản ghi thư mục hay không. Bản ghi thư mục rỗng vẫn hiện thành thư mục trống.
    """

    root = TreeNode(name="", path="")

    for item in work_space_items:
        parts = [part for part in item.path.replace("\\", "/").split("/") if part]
        if not parts:
            continue

        folder_parts = parts if item.is_directory else parts[:-1]
        node = root

        for part in folder_parts:
            child_path = f"{node.path}/{part}" if node.path else part
            node = node.folders.setdefault(part, TreeNode(name=part, path=child_path))

        if item.is_directory:
            node.item = item
        else:
            node.files.append(item)

    _sort_and_count(root)
    return root


def _sort_and_count(node: TreeNode) -> int:
    '''Thư mục trước, file sau, mỗi nhóm theo tên; đồng thời đếm file trong mỗi thư mục'''
    node.folders = dict(sorted(node.folders.items(), key=lambda kv: kv[0].lower()))
    node.files.sort(key=lambda item: item.name.lower())
    node.file_count = len(node.files) + sum(_sort_and_count(child) for child in node.folders.values())
    return node.file_count


def all_folder_paths(node: TreeNode) -> set[str]:
    paths = set()
    for child in node.folders.values():
        paths.add(child.path)
        paths |= all_folder_paths(child)
    return paths


def render_file_list(
        work_space_items: list[StateManager.WorkSpaceItem],
        action: UIActions,
):
    tree = build_tree(work_space_items)

    with st.container(
            horizontal=True,
            vertical_alignment="center",
    ):
        st.markdown(
            "#### :material/folder_open: Workspace",
            anchors=False,
        )

        if tree.file_count:
            st.badge(
                f"{tree.file_count} file",
                color="gray",
            )

        if tree.folders:
            # Mở/thu gọn toàn bộ cây
            if st.button(
                    ":material/unfold_more:",
                    key="expand_all_folders",
                    type="tertiary",
                    help="Mở tất cả thư mục",
            ):
                action.state.expanded_folders = all_folder_paths(tree)
                st.rerun()

            if st.button(
                    ":material/unfold_less:",
                    key="collapse_all_folders",
                    type="tertiary",
                    help="Thu gọn tất cả thư mục",
            ):
                action.state.expanded_folders = set()
                st.rerun()

    render_drop_zone(
        action
    )

    if action.state.upload_errors:  # Lần upload trước có file bị lỗi
        st.warning(
            "Một số file chưa tải lên được:\n\n"
            + "\n".join(f"- {error}" for error in action.state.upload_errors),  # Mỗi lỗi một dòng
            icon=":material/warning:",
        )

    if not tree.folders and not tree.files:
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
        render_tree(
            tree,
            depth=0,
            action=action,
        )


def render_tree(
        node: TreeNode,
        depth: int,
        action: UIActions,
):
    """
    Vẽ đệ quy một thư mục: các thư mục con trước, file sau.
    Thư mục con chỉ vẽ tiếp khi đang mở.
    """

    expanded = action.state.expanded_folders

    for folder in node.folders.values():
        is_open = folder.path in expanded

        # Key chứa độ sâu để CSS thụt lề theo cấp (xem styles.py)
        with st.container(key=f"tree_d{depth}_folder_{_key_safe(folder.path)}"):
            # Một hàng gồm: [tên thư mục (n)........] [delete] [download zip]
            name_col, delete_col, download_col = st.columns(
                [9, 1, 1],
                vertical_alignment="center",
            )

            with name_col:
                if st.button(
                        f"{folder.name} ({folder.file_count})",
                        key=f"toggle_folder_{folder.path}",
                        icon=":material/folder_open:" if is_open else ":material/folder:",
                        type="tertiary",
                        width="stretch",
                        help=folder.path,
                ):
                    if is_open:
                        # Đóng thư mục thì đóng luôn các thư mục con bên trong
                        action.state.expanded_folders = _without_folder(expanded, folder.path)
                    else:
                        expanded.add(folder.path)

                    st.rerun()

            # Thư mục chưa có bản ghi trong DB thì không có file_id để xóa/tải
            if folder.item is not None:
                with delete_col:
                    render_delete_folder(folder, action)

                with download_col:
                    # Chỉ nén và tải khi user bấm, giống nút tải file
                    st.download_button(
                        ":material/download:",
                        data=lambda file_id=folder.item.file_id: action.download_file(
                            file_id=file_id
                        ),
                        file_name=f"{folder.name}.zip",
                        mime="application/zip",
                        key=f"download_folder_{folder.item.file_id}",
                        type="tertiary",
                        help="Tải thư mục (.zip)",
                        on_click="ignore",
                    )

        if is_open:
            render_tree(
                folder,
                depth=depth + 1,
                action=action,
            )

    for item in node.files:
        with st.container(key=f"tree_d{depth}_file_{item.file_id}"):
            render_file_row(
                item,
                action,
            )


def render_file_row(
        item: StateManager.WorkSpaceItem,
        action: UIActions,
):
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
                item.name,  # Trong cây chỉ cần tên, đường dẫn đầy đủ nằm ở tooltip
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


def render_delete_folder(
        folder: TreeNode,
        action: UIActions,
):
    """
    Nút xóa thư mục. Xóa cả cây file bên trong nên phải xác nhận trong popover trước.
    """

    with st.popover(
            ":material/delete:",
            type="tertiary",
            help="Xóa thư mục",
    ):
        st.markdown(
            f"Xóa thư mục **{folder.name}** và **{folder.file_count}** file bên trong?  \n"
            "Thao tác này không hoàn tác được."
        )

        if st.button(
                "Xóa",
                key=f"confirm_delete_folder_{folder.item.file_id}",
                type="primary",
                icon=":material/delete:",
        ):
            action.delete_file(
                file_id=folder.item.file_id
            )

            # Thư mục đã mất thì bỏ khỏi danh sách đang mở
            action.state.expanded_folders = _without_folder(
                action.state.expanded_folders,
                folder.path,
            )

            st.rerun()


def _without_folder(
        expanded: set[str],
        folder_path: str,
) -> set[str]:
    '''Bỏ một thư mục và mọi thư mục con của nó khỏi tập đang mở'''
    return {
        path for path in expanded
        if path != folder_path and not path.startswith(folder_path + "/")
    }


def _key_safe(path: str) -> str:
    '''Key của container thành tên class CSS, chỉ giữ ký tự an toàn'''
    return re.sub(r"[^A-Za-z0-9_-]", "_", path)


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
