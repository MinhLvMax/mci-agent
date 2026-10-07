from dataclasses import dataclass
from pathlib import Path

from pydantic import Field

from src.dom.tool import Tool, ToolKwargs, ToolResult
from src.inf.tools.file.helper import WorkspacePathGuard, WorkspacePathError, save_text
from src.inf.tools.youtube.nexlev_client import NexlevClient, NexlevError, NexlevFatalError
from src.inf.tools.youtube.youtube_transcript_tool import _parse_video_id, _to_srt


class NexlevYoutubeTranscriptToolKwargs(ToolKwargs):
    video_id: str | None = Field(
        default=None,
        description="YouTube video id (e.g. 'xdjTOWBowrA') or full video URL. Use video_ids for several videos."
    )

    video_ids: list[str] | None = Field(
        default=None,
        max_length=10,
        description="Up to 10 video ids or URLs fetched in one cheaper call. Use instead of video_id."
    )

    save_to: str | None = Field(
        default=None,
        description=(
            "Workspace path to write to. For one video: the .srt file, e.g. 'ha-long/subtitles/xdjTOWBowrA.srt'. "
            "For video_ids: a folder, each video saved as '<folder>/<video_id>.srt'. "
            "Defaults to 'transcripts/<video_id>.srt'. Missing folders are created, an existing file is replaced."
        )
    )


@dataclass
class NexlevYoutubeTranscriptToolResult(ToolResult):
    content: str

    def to_text(self) -> str:
        return self.content


class NexlevYoutubeTranscriptTool(Tool):
    tool_name = 'nexlev_youtube_transcript'
    tool_description = (
        "Get the transcript (what is said) of YouTube videos via NexLev and save it as .srt files in the workspace. "
        "Pass video_id for one video or video_ids for up to 10 videos at once (cheaper). "
        "Returns only a short summary per video (file path, language, lines, first sentences), not the full text. "
        "Use read_file or search_files on the saved files afterwards."
    )

    tool_kwargs = NexlevYoutubeTranscriptToolKwargs

    PREVIEW_CHARS = 300

    def __init__(self, workspace_dir: str | Path, api_key: str | None):
        self.path_guard = WorkspacePathGuard(workspace_dir)
        self.client = NexlevClient(api_key)

    def execute(self, **kwargs) -> ToolResult:
        args = self.tool_kwargs(**kwargs)

        ids = [_parse_video_id(value) for value in (args.video_ids or ([args.video_id] if args.video_id else []))]
        ids = list(dict.fromkeys(video_id for video_id in ids if video_id))  # Bỏ trùng, giữ thứ tự

        if not ids:
            return NexlevYoutubeTranscriptToolResult(content="Provide video_id or video_ids.")

        try:
            transcripts = self._fetch(ids)
        except NexlevFatalError as e:
            return NexlevYoutubeTranscriptToolResult(
                content=f"NexLev unavailable ({e}). Do not retry; continue without transcripts."
            )

        is_bulk = args.video_ids is not None
        reports = []

        for video_id in ids:
            data = transcripts.get(video_id)

            if isinstance(data, str):  # Lỗi riêng của video này
                reports.append(f"{video_id}: no transcript ({data}). Skip this video.")
                continue

            lines = _to_lines(data.get('transcript') or [])
            if not lines:
                reports.append(f"{video_id}: transcript is empty. Skip this video.")
                continue

            if is_bulk:
                path = f"{args.save_to.rstrip('/')}/{video_id}.srt" if args.save_to else f"transcripts/{video_id}.srt"
            else:
                path = args.save_to or f"transcripts/{video_id}.srt"

            try:
                saved_path = save_text(self.path_guard, path, _to_srt(lines))
            except WorkspacePathError as e:
                reports.append(f"{video_id}: cannot save to '{path}': {e}")
                continue

            language = (data.get('selected') or {}).get('title') or '?'
            preview = ' '.join(text for _, _, text in lines)[:self.PREVIEW_CHARS]

            reports.append(
                f"Saved transcript of {video_id} to {saved_path}\n"
                f"URL: https://www.youtube.com/watch?v={video_id}\n"
                f"language: {language}, lines: {len(lines)}\n"
                f"preview: {preview}..."
            )

        return NexlevYoutubeTranscriptToolResult(content="\n\n".join(reports))

    def _fetch(self, ids: list[str]) -> dict[str, dict | str]:
        '''Trả {video_id: dữ liệu transcript hoặc chuỗi lỗi}; nhiều video thì gọi bulk (5 quota cho tối đa 10 video)'''
        if len(ids) == 1:
            try:
                return {ids[0]: self.client.get('/videos/transcript', videoId=ids[0])}
            except NexlevFatalError:
                raise
            except NexlevError as e:
                return {ids[0]: str(e)}

        try:
            data = self.client.post('/videos/bulk-transcript', json={'videoIds': ids})
        except NexlevFatalError:
            raise
        except NexlevError as e:
            return {video_id: str(e) for video_id in ids}

        results = {}
        for item in data.get('results') or []:
            video_id = item.get('videoId')
            if item.get('success') and isinstance(item.get('data'), dict):
                results[video_id] = item['data']
            else:
                results[video_id] = str(item.get('error') or item.get('message') or 'failed')
        return results


def _to_lines(segments: list[dict]) -> list[tuple[float, float, str]]:
    '''Đoạn NexLev (startMs/endMs dạng chuỗi) -> (giây bắt đầu, thời lượng, chữ) cho _to_srt'''
    lines = []

    for segment in segments:
        text = ' '.join(str(segment.get('text') or '').split())
        if not text:
            continue

        try:
            start = int(segment.get('startMs') or 0) / 1000
            end = int(segment.get('endMs') or 0) / 1000
        except (TypeError, ValueError):
            continue

        lines.append((start, max(end - start, 0), text))

    return lines


if __name__ == '__main__':
    import tempfile
    from src.config import Config

    with tempfile.TemporaryDirectory() as workspace:
        tool = NexlevYoutubeTranscriptTool(workspace_dir=workspace, api_key=Config.NEXLEV_API_KEY)
        print(tool.execute(video_id='https://www.youtube.com/watch?v=aRtPD3QEkyg').to_text())
        print(tool.execute(video_ids=['aRtPD3QEkyg', 'OASbSc3W3m4'], save_to='videos/transcripts').to_text())
        print(sorted(str(p.relative_to(workspace)) for p in Path(workspace).rglob('*.srt')))
