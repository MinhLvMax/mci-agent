from dataclasses import dataclass
from pathlib import Path

import requests
import yt_dlp
from pydantic import Field
from youtube_transcript_api import YouTubeTranscriptApi, YouTubeTranscriptApiException

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError, save_text
from src.inf.tools.research.text_utils import to_srt


class YoutubeTranscriptToolKwargs(ToolKwargs):
    video_id: str = Field(
        description="YouTube video id (e.g. 'xdjTOWBowrA') or full video URL."
    )

    save_to: str | None = Field(
        default=None,
        description=(
            "Workspace path of the .srt file to write, e.g. 'ha-long/subtitles/xdjTOWBowrA.srt'. "
            "Defaults to 'transcripts/<video_id>.srt'. Missing folders are created, an existing file is replaced."
        )
    )

    languages: list[str] = Field(
        default_factory=lambda: ['vi', 'en'],
        description="Preferred subtitle languages in priority order. Auto-generated subtitles are accepted."
    )


@dataclass
class YoutubeTranscriptToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


@dataclass
class _Transcript:
    lines: list[tuple[float, float, str]]  # (giây bắt đầu, thời lượng, câu)
    language: str
    is_generated: bool


class YoutubeTranscriptTool(Tool):
    tool_name = 'youtube_transcript'
    tool_description = (
        "Download the subtitles of a YouTube video and save them as a standard .srt file in the workspace. "
        "Returns only a short summary (title, channel, language, number of lines, file path), not the subtitles. "
        "Use extract_insights or read_file on the saved file afterwards. "
        "It may fail on servers whose IP is blocked by YouTube; then ask the user to upload the subtitles instead."
    )

    tool_kwargs = YoutubeTranscriptToolKwargs

    def __init__(self, workspace_dir: str | Path):
        self.path_guard = WorkspacePathGuard(workspace_dir)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        video_id = _parse_video_id(args.video_id)
        metadata = _fetch_metadata(video_id)

        try:
            transcript = _fetch_with_transcript_api(video_id, args.languages)
        except YouTubeTranscriptApiException as e:
            # Thư viện chính không lấy được (bị chặn, tắt phụ đề...) thì thử phụ đề tự động qua yt-dlp
            transcript = _fetch_with_ytdlp(metadata, args.languages)
            if transcript is None:
                return YoutubeTranscriptToolResult(
                    content=(
                        f"No subtitles available for video {video_id}: {type(e).__name__}. "
                        f"Skip this video or ask the user to upload its subtitles."
                    )
                )

        if not transcript.lines:
            return YoutubeTranscriptToolResult(
                content=f"Subtitles of video {video_id} are empty. Skip this video."
            )

        try:
            saved_path = save_text(
                self.path_guard,
                args.save_to or f"transcripts/{video_id}.srt",
                to_srt(transcript.lines),
            )
        except WorkspacePathError as e:
            return YoutubeTranscriptToolResult(content=f"Cannot save to '{args.save_to}': {e}")

        return YoutubeTranscriptToolResult(
            content=(
                f"Saved subtitles of '{metadata.get('title') or video_id}' to {saved_path}\n"
                f"URL: https://www.youtube.com/watch?v={video_id}\n"
                f"channel: {metadata.get('channel') or '?'} | views: {metadata.get('view_count') or '?'}\n"
                f"language: {transcript.language}{' (auto-generated)' if transcript.is_generated else ''}, "
                f"lines: {len(transcript.lines)}"
            )
        )


def _parse_video_id(value: str) -> str:
    value = value.strip()

    if 'youtu.be/' in value:
        return value.split('youtu.be/')[1].split('?')[0].split('&')[0]

    if 'v=' in value:
        return value.split('v=')[1].split('&')[0]

    if '/shorts/' in value:
        return value.split('/shorts/')[1].split('?')[0]

    return value


def _fetch_metadata(video_id: str) -> dict:
    '''Lấy title/channel/views của video, lỗi thì trả dict rỗng (metadata không bắt buộc)'''
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'skip_download': True}) as ydl:
            return ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False) or {}
    except Exception:
        return {}


def _fetch_with_transcript_api(video_id: str, languages: list[str]) -> _Transcript:
    transcript_list = YouTubeTranscriptApi().list(video_id)

    try:
        transcript = transcript_list.find_transcript(languages)
    except YouTubeTranscriptApiException:
        # Không có ngôn ngữ mong muốn thì lấy bản đầu tiên có sẵn
        transcript = next(iter(transcript_list))

    fetched = transcript.fetch()

    return _Transcript(
        lines=[
            (s.start, s.duration, s.text.replace('\n', ' ').strip())
            for s in fetched.snippets if s.text.strip()
        ],
        language=transcript.language_code,
        is_generated=transcript.is_generated,
    )


def _fetch_with_ytdlp(metadata: dict, languages: list[str]) -> _Transcript | None:
    '''Dự phòng: tải phụ đề định dạng json3 từ link mà yt-dlp cung cấp'''
    for is_generated, tracks in ((False, metadata.get('subtitles') or {}),
                                 (True, metadata.get('automatic_captions') or {})):
        for language in languages:
            formats = tracks.get(language) or []
            json3 = next((f for f in formats if f.get('ext') == 'json3'), None)

            if json3 is None:
                continue

            try:
                data = requests.get(json3['url'], timeout=30).json()
            except Exception:
                continue

            lines = []
            for event in data.get('events', []):
                text = ''.join(seg.get('utf8', '') for seg in event.get('segs') or []).replace('\n', ' ').strip()
                if text:
                    lines.append((event.get('tStartMs', 0) / 1000, event.get('dDurationMs', 0) / 1000, text))

            return _Transcript(lines=lines, language=language, is_generated=is_generated)

    return None


if __name__ == '__main__':
    import tempfile

    with tempfile.TemporaryDirectory() as workspace:
        tool = YoutubeTranscriptTool(workspace_dir=workspace)
        print(tool.execute(video_id='xdjTOWBowrA').to_text())
