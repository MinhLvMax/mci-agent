from dataclasses import dataclass

from pydantic import Field

from src.dom.entities.skill import Skill
from src.dom.tool import Tool, ToolKwargs, ToolResult


class LoadSkillToolKwargs(ToolKwargs):
    name: str = Field(
        description="Name of the skill to load, exactly as listed in the Skills section of the system prompt."
    )


@dataclass
class LoadSkillToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class LoadSkillTool(Tool):
    tool_name = 'load_skill'
    tool_description = (
        "Load the full instructions of a skill (a detailed workflow for a type of task). "
        "Call it before starting a task that matches a skill listed in the system prompt, "
        "then follow the returned instructions."
    )

    tool_kwargs = LoadSkillToolKwargs

    def __init__(self, skills: list[Skill]):
        # Danh sách skill đọc từ DB ở đầu lượt chat, tool không tự mở kết nối DB
        self._skills = {skill.name: skill for skill in skills}

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        skill = self._skills.get(args.name.strip())

        if skill is None:
            return LoadSkillToolResult(
                content=f"Skill '{args.name}' not found. Available skills: {', '.join(self._skills) or 'none'}"
            )

        output = [f"# Skill: {skill.name}", "", skill.instructions.strip()]

        tools = skill.config.get('tools') if isinstance(skill.config, dict) else None
        if tools:
            output += ["", f"Tools used by this skill: {', '.join(tools)}"]

        return LoadSkillToolResult(
            content="\n".join(output)
        )
