import difflib
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

from src.inf.tools.file.helper import WorkspacePathGuard
from src.inf.tools.research.text_utils import slugify, strip_accents

CATEGORIES = {
    'data_history': 'Số liệu & lịch sử',
    'visual_description': 'Miêu tả hình ảnh, vật thể',
    'comparison_metaphor': 'So sánh, ẩn dụ',
    'fact_paradox': 'Facts & nghịch lý',
}


class ResearchProjectError(ValueError):
    pass


class ResearchProjectStore:
    """
    Lưu trữ một dự án nghiên cứu trong workspace:

    research/<slug>/
        project.json, sources.json
        raw/youtube/<video_id>.md, raw/articles/<source_id>.md
        insights/<place_slug>.jsonl
        unique_stories.md, report.md

    Dữ liệu thô nằm trong file, tool chỉ trả tóm tắt để không làm đầy context của agent.
    """

    ROOT = 'research'
    SLUG_MAX_CHARS = 40  # Slug ngắn để model chép lại ở các lần gọi tool sau ít bị sai

    def __init__(self, workspace_dir: str | Path):
        self.path_guard = WorkspacePathGuard(workspace_dir)

    # ---------- project ----------

    def project_dir(self, project: str) -> Path:
        return self.path_guard.resolve(f"{self.ROOT}/{slugify(project)}")

    def relative(self, path: Path) -> str:
        return self.path_guard.to_relative(path).replace('\\', '/')

    def create_project(self, title: str, places: list[str], keywords: list[str]) -> tuple[dict, bool]:
        '''Tạo dự án mới, nếu đã có thì gộp thêm địa danh/từ khoá. Trả về (project, is_new)'''
        slug = slugify(title)
        if len(slug) > self.SLUG_MAX_CHARS:
            slug = slug[:self.SLUG_MAX_CHARS].rsplit('-', 1)[0]  # Cắt ở ranh giới từ

        project_dir = self.project_dir(slug)
        project_file = project_dir / 'project.json'

        if project_file.exists():
            project = self._read_json(project_file, {})
            project['places'] = _merge_unique(project.get('places', []), places)
            project['keywords'] = _merge_unique(project.get('keywords', []), keywords)
            is_new = False
        else:
            project = {
                'slug': project_dir.name,
                'title': title,
                'places': _merge_unique([], places),
                'keywords': _merge_unique([], keywords),
                'created_at': datetime.now().isoformat(timespec='seconds'),
            }
            is_new = True

        for sub in ('raw/youtube', 'raw/articles', 'insights'):
            (project_dir / sub).mkdir(parents=True, exist_ok=True)

        self._write_json(project_file, project)
        return project, is_new

    def load_project(self, project: str | None) -> dict:
        slug = self.resolve_project(project)
        return self._read_json(self.project_dir(slug) / 'project.json', {})

    def resolve_project(self, project: str | None) -> str:
        '''
        Tìm slug dự án từ giá trị model truyền vào, chịu được việc model chép thiếu/hỏng
        (vd "ky-quan-thich..."): khớp đúng -> khớp tiền tố duy nhất -> khớp gần đúng duy nhất
        -> workspace chỉ có 1 dự án thì dùng luôn dự án đó.
        '''
        existing = self.list_projects()

        if project and project.strip():
            slug = slugify(_clean(project))

            if slug in existing:
                return slug

            prefixed = [p for p in existing if p.startswith(slug) or slug.startswith(p)]
            if len(prefixed) == 1:
                return prefixed[0]

            close = difflib.get_close_matches(slug, existing, n=2, cutoff=0.75)
            if len(close) == 1:
                return close[0]

            # Model chép đúng phần đầu rồi hỏng phần sau: chọn dự án có phần đầu chung dài nhất (tối thiểu 8 ký tự)
            common = {p: len(os.path.commonprefix([slug, p])) for p in existing}
            best = max(common.values(), default=0)
            winners = [p for p, length in common.items() if length == best]
            if best >= 8 and len(winners) == 1:
                return winners[0]

        if len(existing) == 1:
            return existing[0]

        if not existing:
            raise ResearchProjectError(
                "No research project exists yet. Create it first with start_research_project."
            )

        raise ResearchProjectError(
            f"Research project '{project}' does not exist. Existing projects: {', '.join(existing)}"
        )

    def list_projects(self) -> list[str]:
        root = self.path_guard.resolve(self.ROOT)
        if not root.exists():
            return []
        return sorted(p.parent.name for p in root.glob('*/project.json'))

    def find_place(self, project: dict, place: str) -> str:
        '''Trả về tên địa danh đúng như trong project (so khớp không dấu, chịu được tên bị chép hỏng)'''
        key = strip_accents(_clean(place))
        known_places = {strip_accents(known): known for known in project.get('places', [])}

        if key in known_places:
            return known_places[key]

        close = difflib.get_close_matches(key, list(known_places), n=2, cutoff=0.75)
        if len(close) == 1:
            return known_places[close[0]]

        raise ResearchProjectError(
            f"Place '{place}' is not in project '{project['slug']}'. "
            f"Known places: {', '.join(project.get('places', []))}"
        )

    # ---------- sources ----------

    def load_sources(self, project: str) -> list[dict]:
        return self._read_json(self.project_dir(project) / 'sources.json', [])

    def save_sources(self, project: str, sources: list[dict]):
        self._write_json(self.project_dir(project) / 'sources.json', sources)

    def get_source(self, project: str, source_id: str) -> dict | None:
        return next((s for s in self.load_sources(project) if s['id'] == source_id), None)

    def upsert_source(self, project: str, source: dict) -> bool:
        '''Thêm hoặc cập nhật source theo id. Trả về True nếu là source mới'''
        sources = self.load_sources(project)

        for index, existing in enumerate(sources):
            if existing['id'] == source['id']:
                sources[index] = {**existing, **source}
                self.save_sources(project, sources)
                return False

        sources.append(source)
        self.save_sources(project, sources)
        return True

    @staticmethod
    def article_id(url: str) -> str:
        return 'art_' + hashlib.sha1(url.strip().encode('utf-8')).hexdigest()[:10]

    @staticmethod
    def youtube_id(video_id: str) -> str:
        return f'yt_{video_id}'

    # ---------- raw ----------

    def write_raw(self, project: str, kind: str, name: str, content: str) -> str:
        '''kind: youtube | articles. Trả về relative path của file'''
        path = self.project_dir(project) / 'raw' / kind / f'{name}.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return self.relative(path)

    def read_file(self, relative_path: str) -> str:
        return self.path_guard.resolve(relative_path).read_text(encoding='utf-8')

    # ---------- insights ----------

    def insights_file(self, project: str, place: str) -> Path:
        return self.project_dir(project) / 'insights' / f'{slugify(place)}.jsonl'

    def read_insights(self, project: str, place: str) -> list[dict]:
        path = self.insights_file(project, place)
        if not path.exists():
            return []

        return [
            json.loads(line)
            for line in path.read_text(encoding='utf-8').splitlines()
            if line.strip()
        ]

    def append_insights(self, project: str, place: str, items: list[dict]) -> list[dict]:
        '''Ghi thêm insight, bỏ câu trùng (so khớp không dấu). Trả về các insight thực sự được thêm'''
        existing = self.read_insights(project, place)
        seen = {(strip_accents(i['text']), i['category']) for i in existing}
        next_number = len(existing) + 1
        place_slug = slugify(place)
        added = []

        for item in items:
            key = (strip_accents(item['text']), item['category'])
            if key in seen:
                continue

            seen.add(key)
            added.append({'id': f'{place_slug}-{next_number}', 'place': place, **item})
            next_number += 1

        if added:
            path = self.insights_file(project, place)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('a', encoding='utf-8') as file:
                for item in added:
                    file.write(json.dumps(item, ensure_ascii=False) + '\n')

        return added

    # ---------- outputs ----------

    def write_output(self, project: str, filename: str, content: str) -> str:
        path = self.project_dir(project) / filename
        path.write_text(content, encoding='utf-8')
        return self.relative(path)

    def read_output(self, project: str, filename: str) -> str | None:
        path = self.project_dir(project) / filename
        return path.read_text(encoding='utf-8') if path.exists() else None

    # ---------- helpers ----------

    @staticmethod
    def _read_json(path: Path, default):
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding='utf-8'))

    @staticmethod
    def _write_json(path: Path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _clean(value: str) -> str:
    '''Bỏ dấu ba chấm, khoảng trắng đặc biệt, ký tự lạ mà model đôi khi chèn vào tham số'''
    value = value.replace('\u2026', ' ').replace('?', ' ')  # \u2026 là dấu ba chấm '…'
    value = re.sub(r'\.{2,}', ' ', value)
    return re.sub(r'\s+', ' ', value).strip(' .')  # \s gồm cả khoảng trắng đặc biệt \xa0


def _merge_unique(current: list[str], new: list[str]) -> list[str]:
    '''Gộp danh sách, bỏ trùng theo dạng không dấu nhưng giữ cách viết đầu tiên'''
    result = list(current)
    seen = {strip_accents(x) for x in result}

    for item in new:
        item = item.strip()
        if item and strip_accents(item) not in seen:
            seen.add(strip_accents(item))
            result.append(item)

    return result


def youtube_link(source: dict, start: int | None = None) -> str:
    url = source.get('url', '')
    if start is not None and source.get('type') == 'youtube':
        return f"{url}&t={int(start)}s"
    return url
