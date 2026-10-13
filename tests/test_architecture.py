'''
Kiểm tra chiều phụ thuộc giữa các tầng bằng cách đọc câu lệnh import (không chạy code).

    dom  <-  app (ports)  <-  inf (adapter)
                 ^
                pre (giao tiếp)          bootstrap lắp ráp app + inf
                                         entries_point dùng bootstrap + pre

Chạy: python -m unittest discover tests
'''
import ast
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / 'src'

# Thư viện hạ tầng: chỉ adapter ở tầng inf mới được dùng trực tiếp
INFRA_LIBS = ['psycopg', 'jwt', 'bcrypt', 'openai', 'groq', 'ollama', 'anthropic', 'tavily', 'ddgs']

# Tầng -> các module KHÔNG được import
FORBIDDEN = {
    'dom': ['src.app', 'src.inf', 'src.pre', 'src.bootstrap', 'src.entries_point', 'psycopg'],
    'app': ['src.inf', 'src.pre', 'src.bootstrap', 'src.entries_point', *INFRA_LIBS],
    'inf': ['src.pre', 'src.bootstrap', 'src.entries_point'],
    'pre': ['src.inf', 'src.bootstrap', 'src.entries_point', *INFRA_LIBS],
    'bootstrap.py': ['src.pre', 'src.entries_point'],
}

# Vi phạm đã biết, chưa sửa trong đợt này (ghi rõ lý do để không bị quên)
KNOWN_VIOLATIONS: set[tuple[str, str]] = set()


def imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding='utf-8'))
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module)
    return modules


def violations() -> list[str]:
    found = []
    for layer, forbidden in FORBIDDEN.items():
        target = SRC / layer
        files = [target] if target.is_file() else sorted(target.rglob('*.py'))

        for file in files:
            rel = file.relative_to(SRC).as_posix()
            for module in imported_modules(file):
                for bad in forbidden:
                    if (module == bad or module.startswith(bad + '.')) and (rel, bad) not in KNOWN_VIOLATIONS:
                        found.append(f"{rel} imports {module}")
    return found


class ArchitectureTest(unittest.TestCase):
    def test_layers_respect_dependency_direction(self):
        self.assertEqual(violations(), [])

    def test_adapters_live_in_infrastructure(self):
        self.assertFalse((SRC / 'app' / 'services' / 'postgre_db').exists())
        self.assertTrue((SRC / 'inf' / 'persistence' / 'postgres' / 'unit_of_work.py').exists())
        for moved in ['password_hasher.py', 'jwt_service.py', 'file_storage.py', 'workspace_service.py']:
            self.assertFalse((SRC / 'app' / 'services' / moved).exists(), moved)

    def test_workspace_sync_does_not_read_disk(self):
        '''Quét ổ đĩa là việc của WorkspaceScanner (tầng inf), service ở tầng app chỉ đối chiếu với CSDL'''
        path = SRC / 'app' / 'services' / 'workspace_sync_service.py'
        source = path.read_text(encoding='utf-8')

        self.assertNotIn('mimetypes', imported_modules(path))
        for disk_call in ['.rglob(', '.stat(', '.is_dir(', '.exists(']:
            self.assertNotIn(disk_call, source, disk_call)


if __name__ == '__main__':
    unittest.main()
