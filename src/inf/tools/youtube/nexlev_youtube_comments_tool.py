from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError, save_text
from src.inf.tools.youtube.nexlev_client import NexlevClient, NexlevError, NexlevFatalError
from src.inf.tools.youtube.youtube_transcript_tool import _parse_video_id


class NexlevYoutubeCommentsToolKwargs(ToolKwargs):
    video_id: str = Field(
        description="YouTube video id (e.g. 'xdjTOWBowrA') or full video URL."
    )

    max_comments: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of top-level comments to collect (each page of ~20 costs 1 quota)."
    )

    save_to: str | None = Field(
        default=None,
        description=(
            "Optional workspace path to save all collected comments, e.g. 'ha-long/comments/xdjTOWBowrA.md'. "
            "Then only the top 5 are returned."
        )
    )


@dataclass
class NexlevYoutubeCommentsToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class NexlevYoutubeCommentsTool(Tool):
    tool_name = 'nexlev_youtube_comments'
    tool_description = (
        "Get comments of a YouTube video via NexLev, sorted by likes (most liked first). "
        "Useful to see what viewers react to, their questions, and stories or facts they add. "
        "With save_to the comments are saved to a workspace file and only the top 5 are returned."
    )

    tool_kwargs = NexlevYoutubeCommentsToolKwargs

    PREVIEW_COMMENTS = 5
    MAX_PAGES = 10

    def __init__(self, workspace_dir: str | Path, api_key: str | None):
        self.path_guard = WorkspacePathGuard(workspace_dir)
        self.client = NexlevClient(api_key)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        video_id = _parse_video_id(args.video_id)

        comments: list[dict] = []
        total = None
        token = None

        try:
            for _ in range(self.MAX_PAGES):
                data = self.client.get('/videos/comments', videoId=video_id, token=token)
                total = total or data.get('commentsCount')
                comments += data.get('data') or []

                token = data.get('continuation')
                if not token or len(comments) >= args.max_comments:
                    break

        except NexlevFatalError as e:
            return NexlevYoutubeCommentsToolResult(
                content=f"NexLev unavailable ({e}). Do not retry; continue without comments."
            )
        except NexlevError as e:
            if not comments:
                return NexlevYoutubeCommentsToolResult(content=f"Cannot get comments of {video_id}: {e}")
            # Đã có vài trang thì dùng luôn phần lấy được

        if not comments:
            return NexlevYoutubeCommentsToolResult(content=f"Video {video_id} has no comments.")

        comments = sorted(comments[:args.max_comments], key=lambda c: _to_int(c.get('likesCount')), reverse=True)
        lines = [_format_comment(comment) for comment in comments]

        header = (
            f"Comments of https://www.youtube.com/watch?v={video_id} "
            f"(collected {len(comments)} of {total or '?'}, sorted by likes)"
        )

        if not args.save_to:
            return NexlevYoutubeCommentsToolResult(content=header + "\n\n" + "\n".join(lines))

        try:
            saved_path = save_text(self.path_guard, args.save_to, f"# {header}\n\n" + "\n".join(lines) + "\n")
        except WorkspacePathError as e:
            return NexlevYoutubeCommentsToolResult(content=f"Cannot save to '{args.save_to}': {e}")

        return NexlevYoutubeCommentsToolResult(
            content=(
                f"Saved {len(comments)} comments to {saved_path}\n{header}\n\n"
                + "\n".join(lines[:self.PREVIEW_COMMENTS])
            )
        )


def _format_comment(comment: dict) -> str:
    text = ' '.join(str(comment.get('textDisplay') or '').split())
    owner = ' [channel owner]' if comment.get('authorIsChannelOwner') else ''
    # publishedAt của NexLev chỉ suy ra từ "7 years ago" nên dùng nguyên chuỗi tương đối, tránh ngày giả chính xác
    date = comment.get('publishedTimeText') or '?'

    return (
        f"- likes: {_to_int(comment.get('likesCount'))} | replies: {_to_int(comment.get('replyCount'))} | "
        f"{date}{owner} | {text}"
    )


def _to_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


if __name__ == '__main__':
    import tempfile
    from src.config import Config

    with tempfile.TemporaryDirectory() as workspace:
        tool = NexlevYoutubeCommentsTool(workspace_dir=workspace, api_key=Config.NEXLEV_API_KEY)
        print(tool.execute(video_id='OASbSc3W3m4', max_comments=30, save_to='videos/comments/OASbSc3W3m4.md').to_text())
