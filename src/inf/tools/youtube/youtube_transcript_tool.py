from dataclasses import dataclass
from pathlib import Path

import requests
import yt_dlp
from pydantic import Field
from youtube_transcript_api import YouTubeTranscriptApi, YouTubeTranscriptApiException

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.research.project_store import ResearchProjectStore, ResearchProjectError
from src.inf.tools.research.text_utils import (
    format_timestamp,
    parse_transcript,
    place_terms,
    relevance_filter,
    mentions,
)


class YoutubeTranscriptToolKwargs(ToolKwargs):
    project: str | None = Field(
        default=None,
        description=(
            "Research project slug returned by start_research_project. "
            "Can be omitted when the workspace has only one research project."
        )
    )

    place: str = Field(
        description="The place (địa danh) of the project that this video is about."
    )

    video_id: str = Field(
        description="YouTube video id (e.g. 'xdjTOWBowrA') or full video URL."
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
    lines: list[tuple[float, str]]  # (giây bắt đầu, câu)
    language: str
    is_generated: bool


class YoutubeTranscriptTool(Tool):
    tool_name = 'youtube_transcript'
    tool_description = (
        "Download the subtitles of a YouTube video, convert them into a timestamped transcript and save it "
        "into the research project (research/<project>/raw/youtube/<video_id>.md) as a source of the given place. "
        "Returns only a short summary (not the full transcript) with how many passages mention the place. "
        "Run extract_insights afterwards to filter useful information from the saved transcripts."
    )

    tool_kwargs = YoutubeTranscriptToolKwargs

    def __init__(self, workspace_dir: str | Path):
        self.store = ResearchProjectStore(workspace_dir)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)
        video_id = _parse_video_id(args.video_id)

        try:
            project = self.store.load_project(args.project)
            place = self.store.find_place(project, args.place)
        except ResearchProjectError as e:
            return YoutubeTranscriptToolResult(content=str(e))

        metadata = _fetch_metadata(video_id)

        try:
            transcript = _fetch_with_transcript_api(video_id, args.languages)
        except YouTubeTranscriptApiException as e:
            # Thư viện chính không lấy được (bị chặn, tắt phụ đề...) thì thử phụ đề tự động qua yt-dlp
            transcript = _fetch_with_ytdlp(metadata, args.languages)
            if transcript is None:
                return YoutubeTranscriptToolResult(
                    content=f"No subtitles available for video {video_id}: {type(e).__name__}. Skip this video."
                )

        if not transcript.lines:
            return YoutubeTranscriptToolResult(
                content=f"Subtitles of video {video_id} are empty. Skip this video."
            )

        url = f"https://www.youtube.com/watch?v={video_id}"
        title = metadata.get('title') or video_id
        body = "\n".join(
            f"[{format_timestamp(start)}] {text}"
            for start, text in transcript.lines
        )

        file_path = self.store.write_raw(
            project['slug'],
            kind='youtube',
            name=video_id,
            content=(
                f"# {title}\n"
                f"URL: {url}\n"
                f"Channel: {metadata.get('channel') or '?'} | Views: {metadata.get('view_count') or '?'} | "
                f"Language: {transcript.language}{' (auto)' if transcript.is_generated else ''}\n"
                f"---\n"
                f"{body}\n"
            )
        )

        source_id = self.store.youtube_id(video_id)
        is_new = self.store.upsert_source(project['slug'], {
            'id': source_id,
            'type': 'youtube',
            'place': place,
            'url': url,
            'title': title,
            'channel': metadata.get('channel'),
            'views': metadata.get('view_count'),
            'published': metadata.get('upload_date'),
            'language': transcript.language,
            'file': file_path,
            'extracted': False,  # extract_insights sẽ đánh dấu True sau khi lọc
        })

        passages = parse_transcript(body)
        relevant = relevance_filter(passages, place_terms(place), window=0)
        whole_video = mentions(title, place_terms(place))

        return YoutubeTranscriptToolResult(
            content=(
                f"{'Saved' if is_new else 'Updated'} transcript of '{title}'.\n"
                f"source_id: {source_id}\n"
                f"file: {file_path}\n"
                f"language: {transcript.language}{' (auto-generated)' if transcript.is_generated else ''}\n"
                f"lines: {len(transcript.lines)}, passages: {len(passages)}, "
                f"passages mentioning '{place}': {len(relevant)}"
                + ("" if whole_video else
                   f"\nNote: the video title does not mention '{place}', only passages near a mention will be used.")
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
        lines=[(s.start, s.text.replace('\n', ' ').strip()) for s in fetched.snippets if s.text.strip()],
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
                    lines.append((event.get('tStartMs', 0) / 1000, text))

            return _Transcript(lines=lines, language=language, is_generated=is_generated)

    return None


if __name__ == '__main__':
    import tempfile
    from src.inf.tools.research.start_project_tool import StartResearchProjectTool

    with tempfile.TemporaryDirectory() as workspace:
        StartResearchProjectTool(workspace).execute(title='Test', places=['Vịnh Hạ Long'])
        tool = YoutubeTranscriptTool(workspace_dir=workspace)
        print(tool.execute(project='test', place='Vịnh Hạ Long', video_id='xdjTOWBowrA').to_text())
