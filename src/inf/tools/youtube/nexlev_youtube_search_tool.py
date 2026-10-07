import re
from dataclasses import dataclass
from typing import Literal

import requests
from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.youtube.nexlev_client import NexlevClient, NexlevError, NexlevFatalError
from src.inf.tools.youtube.youtube_search_tool import _format_count

YOUTUBE_VIDEOS_API = 'https://www.googleapis.com/youtube/v3/videos'


class NexlevYoutubeSearchToolKwargs(ToolKwargs):
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
            "'views' returns the most viewed videos among the search results, "
            "'relevance' keeps YouTube's ranking (usually more on-topic)."
        )
    )

    min_views: int = Field(
        default=0,
        ge=0,
        description="Skip videos with fewer views than this."
    )

    details: bool = Field(
        default=False,
        description="Also get likes, comments, exact upload date and description of each video."
    )


@dataclass
class NexlevYoutubeSearchToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class NexlevYoutubeSearchTool(Tool):
    tool_name = 'nexlev_youtube_search'
    tool_description = (
        "Search YouTube videos (via NexLev, not blocked by YouTube) and return id, title, channel, "
        "view count, duration, upload time and URL. Set details=true to also get likes, comments, "
        "upload date and description. Then use nexlev_youtube_transcript to read what a video says "
        "and nexlev_youtube_comments to see viewers' reactions."
    )

    tool_kwargs = NexlevYoutubeSearchToolKwargs

    PAGE_SIZE = 20  # Mỗi trang kết quả NexLev trả khoảng 20 mục, mỗi trang tốn 1 quota
    DESCRIPTION_CHARS = 500

    def __init__(self, nexlev_api_key: str | None, youtube_api_key: str | None = None):
        self.client = NexlevClient(nexlev_api_key)
        self.youtube_api_key = youtube_api_key

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        try:
            videos = self._search(args)
        except NexlevFatalError as e:
            return NexlevYoutubeSearchToolResult(
                content=f"NexLev unavailable ({e}). Do not retry; continue without it."
            )
        except NexlevError as e:
            return NexlevYoutubeSearchToolResult(content=f"YouTube search failed: {e}")

        if not videos:
            return NexlevYoutubeSearchToolResult(content="No videos found.")

        details = self._fetch_details([video['videoId'] for video in videos]) if args.details else {}

        output = []

        for i, video in enumerate(videos, 1):
            text = (
                f"{i}. {video.get('title', '')}\n"
                f"id: {video['videoId']} | views: {video['views']:,} | "
                f"duration: {video.get('duration') or '?'} | "
                f"channel: {(video.get('channelTitle') or '?').strip()} | "
                f"uploaded: {video.get('publishedTime') or '?'}\n"
                f"URL: https://www.youtube.com/watch?v={video['videoId']}"
            )

            if args.details:
                text += "\n" + details.get(video['videoId'], "likes: ? | comments: ? | uploaded: ?")

            output.append(text)

        return NexlevYoutubeSearchToolResult(content="\n\n".join(output))

    def _search(self, args: NexlevYoutubeSearchToolKwargs) -> list[dict]:
        '''Lấy đủ ứng viên rồi lọc; tham số sortBy của NexLev không có tác dụng nên tự sắp theo lượt xem'''
        # Sắp theo view cần nhiều ứng viên hơn số video trả về để không bỏ sót video nhiều view ở trang sau
        wanted = args.max_results * 2 if args.sort_by == 'views' else args.max_results
        pages = max(1, min(3, -(-wanted // self.PAGE_SIZE)))

        candidates: list[dict] = []
        seen: set[str] = set()
        token = None

        for _ in range(pages):
            data = self.client.get('/youtube/search', query=args.query, type='video', token=token)

            for item in data.get('results') or []:
                video_id = item.get('videoId')
                if item.get('type') != 'video' or not video_id or video_id in seen:
                    continue

                seen.add(video_id)
                candidates.append({**item, 'views': _to_int(item.get('viewCount'))})

            token = data.get('continuation')
            if not token:
                break

        videos = [video for video in candidates if video['views'] >= args.min_views]

        if args.sort_by == 'views':
            videos.sort(key=lambda video: video['views'], reverse=True)

        return videos[:args.max_results]

    def _fetch_details(self, video_ids: list[str]) -> dict[str, str]:
        '''YouTube Data API có đủ like/comment, 1 lần gọi cho 50 video; không có key thì hỏi NexLev từng video'''
        if self.youtube_api_key:
            try:
                return self._details_from_youtube(video_ids)
            except requests.RequestException:
                pass  # Key sai/hết hạn mức thì dùng NexLev

        return {video_id: self._details_from_nexlev(video_id) for video_id in video_ids}

    def _details_from_youtube(self, video_ids: list[str]) -> dict[str, str]:
        response = requests.get(
            YOUTUBE_VIDEOS_API,
            params={'part': 'snippet,statistics', 'id': ','.join(video_ids), 'key': self.youtube_api_key},
            timeout=30,
        )
        response.raise_for_status()

        details = {}
        for item in response.json().get('items') or []:
            statistics = item.get('statistics') or {}
            snippet = item.get('snippet') or {}
            details[item['id']] = self._format_details(
                likes=statistics.get('likeCount'),
                comments=statistics.get('commentCount'),
                published_at=snippet.get('publishedAt'),
                description=snippet.get('description'),
            )
        return details

    def _details_from_nexlev(self, video_id: str) -> str:
        try:
            data = self.client.get('/videos/details', videoId=video_id)
        except NexlevError as e:
            return f"likes: ? | comments: ? | uploaded: ?\n(details failed: {e})"

        return self._format_details(
            likes=data.get('likeCount'),
            comments=None,  # NexLev không trả số bình luận
            published_at=data.get('publishedAt') or data.get('publishDate'),
            description=data.get('description'),
        )

    def _format_details(self, likes, comments, published_at: str | None, description: str | None) -> str:
        # publishedAt dạng ISO 2015-09-24T20:09:44Z -> 24/09/2015
        match = re.match(r'(\d{4})-(\d{2})-(\d{2})', published_at or '')
        uploaded = f"{match[3]}/{match[2]}/{match[1]}" if match else '?'
        description = ' '.join((description or '').split())[:self.DESCRIPTION_CHARS]

        return (
            f"likes: {_format_count(_to_int(likes, None))} | "
            f"comments: {_format_count(_to_int(comments, None))} | "
            f"uploaded: {uploaded}\n"
            f"description: {description or '?'}"
        )


def _to_int(value, default: int | None = 0) -> int | None:
    '''NexLev/YouTube trả số dạng chuỗi ("8826"), thiếu thì trả default'''
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


if __name__ == '__main__':
    from src.config import Config

    tool = NexlevYoutubeSearchTool(nexlev_api_key=Config.NEXLEV_API_KEY, youtube_api_key=Config.YOUTUBE_API_KEY)
    print(tool.execute(query='Just Room Enough Island', max_results=5, details=True).to_text())
