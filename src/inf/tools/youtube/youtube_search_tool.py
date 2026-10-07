from dataclasses import dataclass
from typing import Literal
from urllib.parse import quote

import yt_dlp
from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult


class YoutubeSearchToolKwargs(ToolKwargs):
    query: str = Field(
        min_length=1,
        description="Search query, usually the place name plus a topic, e.g. 'Vịnh Hạ Long lịch sử'."
    )

    max_results: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of videos to return."
    )

    sort_by: Literal['views', 'relevance'] = Field(
        default='views',
        description=(
            "'views' returns the most viewed videos for the query (may include entertainment vlogs), "
            "'relevance' uses YouTube's default ranking (usually more on-topic)."
        )
    )

    min_views: int = Field(
        default=0,
        ge=0,
        description="Skip videos with fewer views than this."
    )

    details: bool = Field(
        default=False,
        description=(
            "Also open each video to get likes, comments, upload date and description (slower). "
            "Fields that cannot be read are shown as '?'."
        )
    )


@dataclass
class YoutubeSearchToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class YoutubeSearchTool(Tool):
    tool_name = 'youtube_search'
    tool_description = (
        "Search YouTube videos and return id, title, channel, view count, duration and URL. "
        "Set details=true to also get likes, comments, upload date and description of each video."
    )

    tool_kwargs = YoutubeSearchToolKwargs

    YDL_OPTIONS = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'extract_flat': 'in_playlist',  # Chỉ lấy metadata từ trang kết quả, không mở từng video
    }

    DESCRIPTION_CHARS = 500

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        if args.sort_by == 'views':
            # sp=CAM= là bộ lọc "sắp xếp theo lượt xem" của YouTube
            target = f"https://www.youtube.com/results?search_query={quote(args.query)}&sp=CAM%253D"
        else:
            target = f"ytsearch{args.max_results}:{args.query}"

        try:
            with yt_dlp.YoutubeDL({**self.YDL_OPTIONS, 'playlistend': args.max_results}) as ydl:
                info = ydl.extract_info(target, download=False)

        except Exception as e:
            return YoutubeSearchToolResult(
                content=f"YouTube search failed: {e}"
            )

        videos = [
            entry for entry in (info or {}).get('entries') or []
            if entry and entry.get('id') and (entry.get('view_count') or 0) >= args.min_views
        ][:args.max_results]

        if not videos:
            return YoutubeSearchToolResult(
                content="No videos found."
            )

        output = []

        for i, video in enumerate(videos, 1):
            duration = video.get('duration')
            output.append(
                f"{i}. {video.get('title', '')}\n"
                f"id: {video['id']} | views: {video.get('view_count') or 0:,} | "
                f"duration: {_format_duration(duration) if duration else '?'} | "
                f"channel: {video.get('channel') or video.get('uploader') or '?'}\n"
                f"URL: https://www.youtube.com/watch?v={video['id']}"
                + (f"\n{self._fetch_details(video['id'])}" if args.details else "")
            )

        return YoutubeSearchToolResult(
            content="\n\n".join(output)
        )

    def _fetch_details(self, video_id: str) -> str:
        '''Like, comment, ngày đăng, mô tả chỉ có trên trang từng video nên phải mở riêng; lỗi thì để '?' '''
        options = {key: value for key, value in self.YDL_OPTIONS.items() if key != 'extract_flat'}

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False) or {}
        except Exception as e:
            return f"likes: ? | comments: ? | uploaded: ?\n(details failed: {str(e)[:150]})"

        upload_date = info.get('upload_date')  # Dạng YYYYMMDD
        uploaded = f"{upload_date[6:]}/{upload_date[4:6]}/{upload_date[:4]}" if upload_date else '?'
        description = ' '.join((info.get('description') or '').split())[:self.DESCRIPTION_CHARS]

        return (
            f"likes: {_format_count(info.get('like_count'))} | "
            f"comments: {_format_count(info.get('comment_count'))} | "
            f"uploaded: {uploaded}\n"
            f"description: {description or '?'}"
        )


def _format_count(value: int | None) -> str:
    return f"{value:,}" if value is not None else '?'


def _format_duration(seconds: int) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


if __name__ == '__main__':
    tool = YoutubeSearchTool()
    print(tool.execute(query='Just Room Enough Island', max_results=3, details=True).to_text())
