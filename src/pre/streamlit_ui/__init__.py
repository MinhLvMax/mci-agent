from dataclasses import dataclass, field


@dataclass
class WorkspaceItem:
    name: str

    item_type: str
    # markdown
    # table
    # text
    # json

    content: object

    collapsed: bool = True


@dataclass
class UIState:
    messages: list = field(
        default_factory=list
    )

    workspace: list[WorkspaceItem] = field(
        default_factory=list
    )
    conversation: list = field(
        default_factory=list
    )
