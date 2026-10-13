import re
from dataclasses import dataclass, fields, replace

from src.app.ports.errors import DuplicateRecordError
from src.app.ports.repositories import SkillsRepository
from src.dom.entities.skill import Skill

# Tên skill là slug: agent gọi load_skill bằng đúng tên này, vd "nghien-cuu-dia-danh"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


class SkillValidationError(ValueError):
    """Dữ liệu skill không hợp lệ."""


class SkillNameExistsError(Exception):
    """Tên skill đã được dùng."""


class SkillNotFoundError(Exception):
    """Skill không tồn tại."""


@dataclass
class SkillChanges:
    '''Các trường muốn sửa, None thì giữ nguyên'''
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    always_on: bool | None = None
    is_active: bool | None = None
    sort_order: int | None = None
    config: dict | None = None


class AdminSkillsUsecase:
    '''Nghiệp vụ trang quản trị skill: thêm, sửa, bật/tắt (bật = duyệt cho agent dùng)'''

    def __init__(self, skills_repository: SkillsRepository):
        self.skills_repository = skills_repository

    def list_skills(self) -> list[Skill]:
        return self.skills_repository.list_all()

    def create_skill(self, changes: SkillChanges) -> Skill:
        skill = Skill(
            name=changes.name or '',
            description=changes.description or '',
            instructions=changes.instructions or '',
            always_on=bool(changes.always_on),
            config=changes.config or {},
            is_active=bool(changes.is_active),  # Mặc định tắt: tạo xong kiểm tra lại rồi mới bật
            sort_order=changes.sort_order or 0,
        )
        validate_skill(skill)
        return self._save(self.skills_repository.create, skill)

    def update_skill(self, skill_id: int, changes: SkillChanges) -> Skill:
        skill = self.skills_repository.get_by_id(skill_id)
        if skill is None:
            raise SkillNotFoundError(f"Skill {skill_id} not found")

        updated = replace(skill, **{
            f.name: getattr(changes, f.name)
            for f in fields(changes)
            if getattr(changes, f.name) is not None
        })
        validate_skill(updated)
        return self._save(self.skills_repository.update, updated)

    def delete_skill(self, skill_id: int):
        if not self.skills_repository.delete(skill_id):
            raise SkillNotFoundError(f"Skill {skill_id} not found")

    def _save(self, save, skill: Skill) -> Skill:
        try:
            return save(skill)
        except DuplicateRecordError:
            raise SkillNameExistsError(f"Skill name '{skill.name}' already exists")


def validate_skill(skill: Skill):
    skill.name = skill.name.strip()

    if not SKILL_NAME_PATTERN.match(skill.name):
        raise SkillValidationError(
            "Skill name must be lowercase letters, digits and '-', e.g. 'nghien-cuu-dia-danh'"
        )

    if skill.always_on and not skill.instructions.strip():
        raise SkillValidationError("Always-on skill needs instructions")  # Luôn nạp mà không có chỉ dẫn

    if not skill.always_on and not skill.description.strip():
        # Skill theo yêu cầu chỉ hiện tên + mô tả trong prompt, thiếu mô tả thì agent không biết khi nào dùng
        raise SkillValidationError("On-demand skill needs a description")

    if not isinstance(skill.config, dict):
        raise SkillValidationError("config_json must be a JSON object")

    tools = skill.config.get('tools')
    if tools is not None and not (isinstance(tools, list) and all(isinstance(t, str) for t in tools)):
        raise SkillValidationError("config_json.tools must be a list of tool names")
