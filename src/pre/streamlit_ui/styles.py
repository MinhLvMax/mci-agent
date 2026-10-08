from typing import Callable, Literal

import streamlit as st

from src.pre.streamlit_ui.state_manager import StateManager

# Màu sắc, font, bo góc nằm trong .streamlit/config.toml.
# CSS ở đây chỉ xử lý những thứ theme không chỉnh được.
#
# Các class .st-key-* sinh ra từ tham số key của st.container.
_CSS = """
<style>
.block-container {
    padding-top: 3rem;
    padding-bottom: 1rem;
}

/* Danh sách hội thoại và danh sách file: chữ căn trái, quá dài thì cắt bằng ... */
.st-key-conversation_list button,
.st-key-file_list button,
.st-key-conversation_list button > div,
.st-key-file_list button > div {
    justify-content: flex-start;
}

.st-key-conversation_list button [data-testid="stMarkdownContainer"],
.st-key-file_list button [data-testid="stMarkdownContainer"] {
    min-width: 0;
}

.st-key-conversation_list button p,
.st-key-file_list button p {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Khung xem file hẹp nên thu nhỏ heading của nội dung markdown. */
.st-key-file_preview h1 { font-size: 1.5rem; padding-top: 0.25rem; }
.st-key-file_preview h2 { font-size: 1.25rem; }
.st-key-file_preview h3 { font-size: 1.1rem; }

/* File markdown dài: giới hạn độ dài dòng cho dễ đọc */
.st-key-file_preview [data-testid="stMarkdownContainer"] { max-width: 80ch; }

/* ===== Chiều cao panel theo màn hình =====
   height truyền vào st.container chỉ là giá trị dự phòng, ở đây ghi đè theo viewport.
   Workspace cao hơn chat đúng bằng ô nhập tin nhắn để đáy hai cột bằng nhau.
   Streamlit gán chiều cao cho cả khối có key lẫn stLayoutWrapper bọc ngoài nên ghi đè cả hai. */
.st-key-chat_panel,
[data-testid="stLayoutWrapper"]:has(> .st-key-chat_panel) {
    height: calc(100dvh - 17rem) !important;
    min-height: 360px;
}

.st-key-workspace_panel,
[data-testid="stLayoutWrapper"]:has(> .st-key-workspace_panel) {
    height: calc(100dvh - 12.6rem) !important;
    min-height: 430px;
}

/* Đang mở file: hàng nút (quay lại, tên file) nằm trên khung cuộn, khung cuộn thấp đi đúng bằng hàng đó */
body:has(.st-key-file_preview_header) .st-key-workspace_panel,
body:has(.st-key-file_preview_header) [data-testid="stLayoutWrapper"]:has(> .st-key-workspace_panel) {
    height: calc(100dvh - 15.4rem) !important;
    min-height: 390px;
}

.st-key-file_preview_header {
    padding: 0 0.25rem;
}

.st-key-file_preview_header p {
    margin: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;  /* Tên file dài thì cắt bằng ..., không đẩy nút xuống dòng */
}

/* ===== Nút Góp ý ghim ở góc trên bên phải, cạnh menu ⋮ của Streamlit (xem render_feedback_button) =====
   Ghim cả khối bọc ngoài để nó không chiếm một khoảng trống ở đầu trang. */
.st-key-feedback_corner,
[data-testid="stLayoutWrapper"]:has(> .st-key-feedback_corner) {
    position: fixed;
    top: 0.6rem;
    right: 3.5rem;      /* Chừa chỗ cho menu ⋮ */
    z-index: 999991;    /* Nằm trên thanh header của Streamlit */
    width: auto;
}

/* ===== Tay kéo ranh giới Chat | Workspace (xem _SPLITTER_JS) ===== */
/* Khối chỉ chứa script, không chiếm chỗ */
.st-key-splitter_js,
[data-testid="stLayoutWrapper"]:has(> .st-key-splitter_js) { display: none; }

#mci-splitter {
    position: fixed;
    z-index: 50;
    width: 12px;
    cursor: col-resize;
    touch-action: none;
}

/* Vạch mảnh ở giữa, chỉ hiện rõ khi rê chuột hoặc đang kéo */
#mci-splitter::after {
    content: "";
    position: absolute;
    left: 5px;
    top: 0;
    bottom: 0;
    width: 2px;
    border-radius: 2px;
    background: #E5E7EB;
    transition: background 0.15s ease;
}

#mci-splitter:hover::after,
#mci-splitter.dragging::after {
    background: #4F46E5;
}

/* Đang kéo: không bôi đen chữ, con trỏ giữ dạng kéo trên toàn trang */
body.mci-resizing {
    cursor: col-resize;
    user-select: none;
}

/* ===== Header của panel (xem render_panel_header) ===== */
[class*="st-key-panel_header_"] p {
    font-weight: 600;
    margin: 0;
}

[class*="st-key-panel_header_"] [data-testid="stIconMaterial"] {
    color: #6B7280;
}

/* ===== Tin nhắn chat ===== */
.st-key-chat_panel [data-testid="stChatMessage"] {
    width: 100%;
    max-width: 860px;  /* Panel rộng (phóng to) thì dòng chữ không quá dài */
    margin-inline: auto;
    padding: 0.75rem 1rem;
}

.st-key-chat_panel [data-testid="stChatMessageContent"] {
    line-height: 1.65;
    min-width: 0;
}

/* Tin nhắn của user có nền riêng, phân biệt với Agent (marker key ở chat_layout.py) */
.st-key-chat_panel [data-testid="stChatMessage"]:has([class*="st-key-user_msg_"]) {
    background: #F3F4F6;
}

/* Bảng và code rộng thì cuộn ngang, không làm vỡ khung */
.st-key-chat_panel [data-testid="stMarkdownContainer"] table {
    display: block;
    overflow-x: auto;
}

.st-key-chat_panel pre {
    overflow-x: auto;
}

/* ===== Dialog xem file toàn màn hình ===== */
div[role="dialog"]:has(.st-key-fullscreen_view) {
    width: min(1200px, 92vw);
    max-width: none;
}

.st-key-fullscreen_view {
    max-height: 78dvh;
    overflow-y: auto;
}

/* Màn hình hẹp: hai panel xếp dọc, giảm chiều cao tối thiểu */
@media (max-width: 900px) {
    .st-key-chat_panel { min-height: 300px; }
    .st-key-workspace_panel { min-height: 320px; }
}
""" + "".join(
    # Cây thư mục Workspace: hàng ở cấp d có key "tree_d{d}_..." (xem workspace_layout.py), thụt lề theo cấp
    f'[class*="st-key-tree_d{depth}_"] {{ padding-left: {depth * 1.1:.1f}rem; }}\n'
    for depth in range(1, 11)
) + """</style>
"""

# Streamlit không có thanh kéo đổi độ rộng cột, nên dùng JS chạy trên trang chính.
#
# - Tay kéo gắn vào body (position: fixed), đặt đè lên khe giữa hai cột,
#   không chèn vào cây DOM do React của Streamlit quản lý.
# - Hai cột được nhận ra qua key "chat_panel" / "workspace_panel" bên trong.
# - Tỉ lệ lưu ở localStorage của trình duyệt, nhấp đúp tay kéo để về 60/40.
# - Hai cột xếp dọc (màn hình hẹp) hoặc đang phóng to một panel thì ẩn tay kéo.
_SPLITTER_JS = """
<script>
(() => {
    if (window.__mciSplitter) return;  // Script chạy lại mỗi lần vẽ, chỉ cài một lần
    window.__mciSplitter = true;

    const KEY = "mci_split_ratio";
    const DEFAULT_RATIO = 0.6;
    const MIN_RATIO = 0.25, MAX_RATIO = 0.75;

    let ratio = DEFAULT_RATIO;
    try { ratio = parseFloat(localStorage.getItem(KEY)) || DEFAULT_RATIO; } catch (e) {}

    const handle = document.createElement("div");
    handle.id = "mci-splitter";
    handle.title = "Kéo để đổi độ rộng, nhấp đúp để về mặc định";
    document.body.appendChild(handle);

    function findColumns() {
        const chat = document.querySelector(".st-key-chat_panel");
        const workspace = document.querySelector(".st-key-workspace_panel");
        if (!chat || !workspace) return null;

        const left = chat.closest('[data-testid="stColumn"]');
        const right = workspace.closest('[data-testid="stColumn"]');
        if (!left || !right || left.parentElement !== right.parentElement) return null;

        return { left, right, row: left.parentElement };
    }

    function applyRatio(cols) {
        // Ghi đè flex mà Streamlit tính từ tỉ lệ [3, 2], cột phải lấy phần còn lại
        cols.left.style.setProperty("flex", `0 0 calc(${(ratio * 100).toFixed(2)}% - 0.5rem)`, "important");
        cols.left.style.setProperty("width", "auto", "important");
        cols.left.style.setProperty("min-width", "0", "important");
        cols.right.style.setProperty("flex", "1 1 0", "important");
        cols.right.style.setProperty("width", "auto", "important");
        cols.right.style.setProperty("min-width", "0", "important");
    }

    function sync() {
        const cols = findColumns();
        if (!cols) { handle.style.display = "none"; return; }

        applyRatio(cols);

        const l = cols.left.getBoundingClientRect();
        const r = cols.right.getBoundingClientRect();

        if (Math.abs(l.top - r.top) > 4) {  // Màn hình hẹp, hai cột đã xếp dọc
            handle.style.display = "none";
            return;
        }

        const row = cols.row.getBoundingClientRect();
        handle.style.display = "block";
        handle.style.left = `${(l.right + r.left) / 2 - 6}px`;  // Giữa khe hai cột
        handle.style.top = `${row.top}px`;
        handle.style.height = `${row.height}px`;
    }

    let scheduled = false;
    function scheduleSync() {
        if (scheduled) return;
        scheduled = true;
        requestAnimationFrame(() => { scheduled = false; sync(); });
    }

    // Streamlit vẽ lại DOM sau mỗi lần rerun (phóng to, mở file...) nên theo dõi thay đổi
    new MutationObserver(scheduleSync).observe(document.body, { childList: true, subtree: true });
    window.addEventListener("resize", scheduleSync);
    document.addEventListener("scroll", scheduleSync, true);

    handle.addEventListener("pointerdown", (event) => {
        const cols = findColumns();
        if (!cols) return;

        event.preventDefault();
        handle.setPointerCapture(event.pointerId);
        handle.classList.add("dragging");
        document.body.classList.add("mci-resizing");

        const onMove = (e) => {
            const row = cols.row.getBoundingClientRect();
            ratio = Math.min(MAX_RATIO, Math.max(MIN_RATIO, (e.clientX - row.left) / row.width));
            sync();
        };

        const onUp = () => {
            handle.removeEventListener("pointermove", onMove);
            handle.removeEventListener("pointerup", onUp);
            handle.classList.remove("dragging");
            document.body.classList.remove("mci-resizing");
            try { localStorage.setItem(KEY, String(ratio)); } catch (e) {}
        };

        handle.addEventListener("pointermove", onMove);
        handle.addEventListener("pointerup", onUp);
    });

    handle.addEventListener("dblclick", () => {
        ratio = DEFAULT_RATIO;
        try { localStorage.removeItem(KEY); } catch (e) {}
        sync();
    });

    scheduleSync();
})();
</script>
"""


def inject_styles():
    st.html(_CSS)

    with st.container(key="splitter_js"):  # CSS ẩn khối này, script vẫn chạy
        st.html(
            _SPLITTER_JS,
            unsafe_allow_javascript=True,
        )


def render_panel_header(
        title: str,
        icon: str,
        panel: Literal["chat", "workspace"],
        state: StateManager,
        extra: Callable[[], None] | None = None,
):
    """
    Hàng tiêu đề nằm trên khung có viền của mỗi panel.

    Gồm: [icon tiêu đề] [extra (vd badge)] ........ [phóng to / thu về]
    """

    maximized = state.maximized_panel == panel

    with st.container(
            key=f"panel_header_{panel}",
            horizontal=True,
            vertical_alignment="center",
    ):
        st.markdown(
            f"{icon} {title}",
            width="content",
        )

        if extra is not None:
            extra()

        st.space("stretch")  # Đẩy nút phóng to về sát mép phải

        if st.button(
                ":material/close_fullscreen:" if maximized else ":material/open_in_full:",
                key=f"maximize_{panel}",
                type="tertiary",
                help="Thu về" if maximized else "Phóng to",
        ):
            state.maximized_panel = None if maximized else panel
            st.rerun()


def render_empty_state(
        icon: str,
        title: str,
        hint: str,
):
    """
    Khối thông báo căn giữa dùng khi chưa có dữ liệu để hiển thị.
    """

    st.space("large")

    st.markdown(
        f"## {icon}",
        text_alignment="center",
        anchors=False,
    )

    st.markdown(
        f"**{title}**",
        text_alignment="center",
    )

    st.caption(
        hint,
        text_alignment="center",
    )
