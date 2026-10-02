from dataclasses import dataclass, field


@dataclass
class Skill:
    '''
    Bộ chỉ dẫn hành vi cho agent, admin quản lý trong bảng skills.

    always_on = True: luôn ghép nguyên văn vào system prompt (đóng vai trò system prompt).
    always_on = False: system prompt chỉ có tên + mô tả, agent gọi load_skill khi cần chỉ dẫn đầy đủ.
    '''
    name: str
    description: str
    instructions: str
    always_on: bool = False
    config: dict = field(default_factory=dict)  # config_json, vd {"tools": [...]}
    id: int | None = None
