from datetime import date

from src.dom.entities.memory import Memory
from src.dom.entities.skill import Skill


def build_system_prompt(skills: list[Skill], memories: list[Memory] = ()) -> str | None:
    '''
    Dựng system prompt từ các skill đang bật và bộ nhớ dài hạn:
    - Skill always_on: ghép nguyên văn phần instructions.
    - Skill còn lại: chỉ liệt kê tên + mô tả, agent tự gọi load_skill khi yêu cầu khớp.
    - Memory org (đã duyệt) và memory riêng của user: liệt kê kèm id để agent sửa/xoá được.
    Không có skill và memory nào thì trả None để giữ hành vi cũ (không gửi system message).
    '''
    if not skills and not memories:
        return None

    parts = [
        skill.instructions.strip()
        for skill in skills
        if skill.always_on and skill.instructions.strip()
    ]

    parts.append(f"Hôm nay là ngày {date.today().strftime('%d/%m/%Y')}.")

    on_demand = [skill for skill in skills if not skill.always_on]

    if on_demand:
        listing = "\n".join(f"- {skill.name}: {skill.description}" for skill in on_demand)
        parts.append(
            "# Skills\n"
            "Các skill dưới đây là quy trình làm việc chi tiết cho từng loại công việc.\n"
            "Khi yêu cầu của người dùng khớp với mô tả của một skill, PHẢI gọi tool load_skill với tên skill đó "
            "TRƯỚC khi bắt đầu làm, rồi làm theo đúng chỉ dẫn nhận được.\n\n"
            f"{listing}"
        )

    parts.append(build_memory_section(memories))

    return "\n\n".join(parts)


def build_memory_section(memories: list[Memory]) -> str:
    '''Phần bộ nhớ dài hạn, luôn có hướng dẫn dùng tool remember/forget kể cả khi chưa có memory nào'''
    org = [m for m in memories if m.scope == 'org']
    user = [m for m in memories if m.scope == 'user']

    lines = [
        "# Bộ nhớ dài hạn",
        "Đây là những điều đã học được từ các lần trò chuyện và góp ý trước. Áp dụng chúng mà không cần nhắc lại.",
        "Nếu một ghi nhớ mâu thuẫn với yêu cầu hiện tại thì làm theo yêu cầu hiện tại; "
        "nếu người dùng muốn thay đổi lâu dài thì gọi remember với replace_memory_id để cập nhật.",
        "Khi người dùng nêu sở thích, cách làm hoặc sửa lỗi mà họ muốn áp dụng cho những lần sau, gọi tool remember. "
        "Khi họ muốn bỏ một ghi nhớ riêng, gọi tool forget.",
        "Khi người dùng bảo 'ghi nhớ', 'nhớ giúp', 'cập nhật ghi nhớ'... PHẢI gọi tool remember. "
        "KHÔNG ghi vào file trong workspace: file không được đọc lại ở hội thoại khác.",
    ]

    if org:
        lines += ["", "## Quy định chung của công ty (đã duyệt)"]
        lines += [f"- [#{m.id}] {m.content}" for m in org]

    if user:
        lines += ["", "## Ghi nhớ riêng về người dùng này"]
        lines += [f"- [#{m.id}] {m.content}" for m in user]

    return "\n".join(lines)
