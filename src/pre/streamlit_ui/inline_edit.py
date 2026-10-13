from typing import Callable

import streamlit as st

# Streamlit không có sự kiện "click vào markdown" hay "rời ô soạn thảo mà không đổi gì",
# nên dùng một đoạn JS nhỏ bấm hộ các nút ẩn. Key của các phần tử theo mẫu
# ie_<vai trò>__<key> để CSS ẩn nút (xem styles.py) và JS tìm ra đúng nhóm.
_SCRIPT = """
<script>
(() => {
    const doc = window.parent?.document || document;

    const clickHidden = (role, key) => {
        doc.querySelector(`.st-key-ie_${role}__${key} button`)?.click();
    };

    const keyOf = (element, role) => {
        const match = element?.className?.match?.(new RegExp(`st-key-ie_${role}__(\\\\S+)`));
        return match ? match[1] : null;
    };

    // Gắn listener cho cả trang đúng một lần, mọi khung click-để-sửa dùng chung
    if (!doc.__inlineEditInstalled) {
        doc.__inlineEditInstalled = true;

        let exiting = null;  // Key của ô đang chờ thoát sửa

        doc.addEventListener("click", (event) => {
            const view = event.target.closest?.('[class*="st-key-ie_view__"]');
            if (!view) return;
            if (event.target.closest("a, button")) return;  // Vẫn bấm được link, nút trong nội dung
            if (doc.getSelection()?.toString()) return;  // Đang bôi đen để copy thì không vào sửa
            const key = keyOf(view, "view");

            // Đang sửa ô khác mà click sang đây: hai lần bấm nút ẩn liền nhau thì Streamlit
            // có thể bỏ mất lần sau, nên đợi ô cũ thoát xong (ô soạn thảo biến mất) rồi mới vào sửa
            let waited = 0;
            const enter = () => {
                const stillEditing = exiting && doc.querySelector(`.st-key-ie_editor__${exiting}`);
                if (stillEditing && waited < 5000) {
                    waited += 100;
                    return setTimeout(enter, 100);
                }
                exiting = null;
                clickHidden("enter", key);
            };
            setTimeout(enter, 150);  // Sau mốc 100ms của focusout để biết có ô nào đang thoát không
        });

        doc.addEventListener("focusout", (event) => {
            const editor = event.target.closest?.('[class*="st-key-ie_editor__"]');
            if (!editor || event.target.tagName !== "TEXTAREA") return;
            const key = keyOf(editor, "editor");

            // Đợi focus chuyển xong: vẫn ở trong ô, hoặc chỉ chuyển cửa sổ/tab thì chưa thoát
            setTimeout(() => {
                if (!doc.hasFocus() || editor.contains(doc.activeElement)) return;
                exiting = key;
                clickHidden("exit", key);
            }, 100);
        });
    }

    // Vừa vào chế độ sửa thì đặt sẵn con trỏ ở cuối ô
    const focusKey = "__FOCUS_KEY__";
    if (focusKey) {
        let tries = 0;
        const focus = () => {
            const textarea = doc.querySelector(`.st-key-ie_editor__${focusKey} textarea`);
            if (!textarea) {
                if (tries++ < 20) requestAnimationFrame(focus);
                return;
            }
            if (doc.activeElement === textarea) return;
            textarea.focus();
            textarea.setSelectionRange(textarea.value.length, textarea.value.length);
        };
        focus();
    }
})();
</script>
"""


def render_click_to_edit(
        *,
        key: str,
        editing: bool,
        text: str,
        render_view: Callable[[], None],
        on_save: Callable[[str], bool],
        set_editing: Callable[[bool], None],
        max_chars: int | None = None,
):
    """
    Khung nội dung click-để-sửa.

    - Chế độ đọc: render_view() vẽ nội dung (markdown, json...), click vào là chuyển sang sửa.
    - Chế độ sửa: ô text_area, click ra ngoài hoặc bấm lưu thì on_save(text mới)
      rồi quay về đọc. on_save trả False (lưu lỗi) thì ở lại chế độ sửa để không mất chữ.

    key chỉ gồm chữ, số, "_" và "-" vì được dùng làm class CSS.
    """

    if not editing:
        with st.container(key=f"ie_view__{key}"):
            render_view()

        st.button(
            "Sửa",
            key=f"ie_enter__{key}",
            on_click=set_editing,
            args=(True,),
        )

        st.html(_SCRIPT.replace("__FOCUS_KEY__", ""), unsafe_allow_javascript=True)
        return

    editor_key = f"ie_editor__{key}"

    # Luôn nạp lại từ text (nguồn chính) để các ô cùng sửa một nội dung không lệch nhau.
    # Không truyền value= vì đã đặt giá trị qua session state.
    st.session_state[editor_key] = text

    st.text_area(
        "Nội dung",
        key=editor_key,
        on_change=lambda: on_save(st.session_state[editor_key]),
        label_visibility="collapsed",
        max_chars=max_chars,
    )

    st.button(
        "Xong",
        key=f"ie_exit__{key}",
        on_click=_save_and_exit,
        args=(editor_key, on_save, set_editing),
    )

    st.html(_SCRIPT.replace("__FOCUS_KEY__", key), unsafe_allow_javascript=True)


def _save_and_exit(
        editor_key: str,
        on_save: Callable[[str], bool],
        set_editing: Callable[[bool], None],
):
    '''Lưu chữ đang có trong ô (phòng on_change chưa kịp chạy) rồi về chế độ đọc'''
    if on_save(st.session_state[editor_key]):
        set_editing(False)
