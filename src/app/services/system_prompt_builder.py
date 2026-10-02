from datetime import date

from src.dom.entities.skill import Skill


def build_system_prompt(skills: list[Skill]) -> str | None:
    '''
    Dựng system prompt từ các skill đang bật:
    - Skill always_on: ghép nguyên văn phần instructions.
    - Skill còn lại: chỉ liệt kê tên + mô tả, agent tự gọi load_skill khi yêu cầu khớp.
    Không có skill nào thì trả None để giữ hành vi cũ (không gửi system message).
    '''
    if not skills:
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

    return "\n\n".join(parts)
