from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError, safe_move


class MovePathToolKwargs(ToolKwargs):
    source: str = Field(
        description=(
            "File or directory to move, relative to the workspace root. "
            "Examples: 'notes.md', 'research/sources'."
        )
    )

    destination: str = Field(
        description=(
            "New full path (relative to the workspace root), including the new name. "
            "Examples: 'ha-long/sources/notes.md', 'archive/sources'. "
            "Missing parent directories are created. The destination must not exist yet."
        )
    )


@dataclass
class MovePathToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class MovePathTool(Tool):
    tool_name = "move_path"
    tool_description = (
        "Move a file or a whole directory to another location in the workspace (it can also be renamed at the same time). "
        "Use it to reorganize research files into folders. "
        "It never overwrites: if the destination already exists the move is refused. "
        "There is no delete tool; tell the user if something should be deleted."
    )

    tool_kwargs = MovePathToolKwargs

    def __init__(self, workspace_dir: str | Path):
        self.path_guard = WorkspacePathGuard(workspace_dir)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            source, destination = safe_move(self.path_guard, args.source, args.destination)
        except WorkspacePathError as e:
            return MovePathToolResult(content=f"Move failed: {e}")

        return MovePathToolResult(
            content=f"Moved '{source}' -> '{destination}'."
        )
