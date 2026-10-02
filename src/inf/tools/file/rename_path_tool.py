from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError, safe_move


class RenamePathToolKwargs(ToolKwargs):
    path: str = Field(
        description="File or directory to rename, relative to the workspace root. Example: 'research/draft.md'."
    )

    new_name: str = Field(
        min_length=1,
        description=(
            "New name only, without any folder part. Example: 'final-report.md'. "
            "To move into another folder use move_path instead."
        )
    )


@dataclass
class RenamePathToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class RenamePathTool(Tool):
    tool_name = "rename_path"
    tool_description = (
        "Rename a file or directory, keeping it in the same folder. "
        "It never overwrites: if another item with the new name already exists the rename is refused."
    )

    tool_kwargs = RenamePathToolKwargs

    def __init__(self, workspace_dir: str | Path):
        self.path_guard = WorkspacePathGuard(workspace_dir)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        new_name = args.new_name.strip()

        if any(char in new_name for char in '/\\') or new_name in {'.', '..'}:
            return RenamePathToolResult(
                content="new_name must be a plain name without folders. Use move_path to move into another folder."
            )

        parent = PurePosixPath(args.path.replace('\\', '/').rstrip('/')).parent
        destination = str(parent / new_name) if str(parent) != '.' else new_name

        try:
            source, destination = safe_move(self.path_guard, args.path, destination)
        except WorkspacePathError as e:
            return RenamePathToolResult(content=f"Rename failed: {e}")

        return RenamePathToolResult(
            content=f"Renamed '{source}' -> '{destination}'."
        )
