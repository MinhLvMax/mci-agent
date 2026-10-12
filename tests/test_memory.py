'''
Chạy: python -m unittest discover tests
Không cần DB hay API key: repository và model đều được giả lập.
'''
import unittest

from src.app.services.memory_service import MemoryPermissionError, MemoryService
from src.app.services.system_prompt_builder import build_system_prompt
from src.app.usecases.extract_lessons_usecase import (
    ExtractLessonsUsecase,
    ExtractLessonsUseCaseCommand,
    parse_lessons,
)
from src.dom.decision.final_decision import FinalDecision
from src.dom.entities.memory import Memory
from src.dom.entities.skill import Skill


class FakeConnection:
    def rollback(self):
        pass


class FakeMemoriesRepository:
    def __init__(self, memories: list[Memory] = ()):
        self.connection = FakeConnection()
        self.memories = {m.id: m for m in memories}
        self.next_id = max(self.memories, default=0) + 1

    def create(self, memory: Memory) -> Memory:
        memory.id = self.next_id
        self.next_id += 1
        self.memories[memory.id] = memory
        return memory

    def get_by_id(self, memory_id):
        return self.memories.get(memory_id)

    def update_content(self, memory_id, content):
        self.memories[memory_id].content = content
        return self.memories[memory_id]

    def set_status(self, memory_id, status, approved_by=None):
        self.memories[memory_id].status = status
        return self.memories[memory_id]

    def list_for_extractor(self, user_id):
        return [m for m in self.memories.values() if m.status in ('active', 'pending')]


class FakeReasoner:
    def __init__(self, output: str):
        self.output = output
        self.contexts = []

    def decide(self, context, tools):
        self.contexts.append(context)
        return FinalDecision(final_content=self.output)


def user_memory(id, user_id, content, status='active'):
    return Memory(id=id, scope='user', user_id=user_id, content=content, status=status, source='tool')


def org_memory(id, content, status='active'):
    return Memory(id=id, scope='org', content=content, status=status, source='admin')


class BuildSystemPromptTest(unittest.TestCase):
    def test_no_skills_no_memories_returns_none(self):
        self.assertIsNone(build_system_prompt([], []))

    def test_memories_are_listed_by_scope_with_ids(self):
        prompt = build_system_prompt(
            [Skill(name='core', description='', instructions='Bạn là trợ lý.', always_on=True)],
            [org_memory(1, 'Giá luôn ghi bằng VNĐ'), user_memory(2, 7, 'Trả lời ngắn gọn')],
        )
        self.assertIn('Bạn là trợ lý.', prompt)
        self.assertIn('## Quy định chung của công ty (đã duyệt)\n- [#1] Giá luôn ghi bằng VNĐ', prompt)
        self.assertIn('## Ghi nhớ riêng về người dùng này\n- [#2] Trả lời ngắn gọn', prompt)

    def test_memory_instructions_present_without_memories(self):
        prompt = build_system_prompt([Skill(name='core', description='', instructions='x', always_on=True)])
        self.assertIn('# Bộ nhớ dài hạn', prompt)
        self.assertNotIn('## Quy định chung', prompt)


class ParseLessonsTest(unittest.TestCase):
    def test_parses_json_inside_code_fence(self):
        text = '```json\n{"lessons": [{"scope": "user", "content": " Dùng bullet ", "replace_memory_id": 3}]}\n```'
        self.assertEqual(parse_lessons(text), [{"scope": "user", "content": "Dùng bullet", "replace_memory_id": 3}])

    def test_empty_and_invalid_outputs(self):
        self.assertEqual(parse_lessons('{"lessons": []}'), [])
        self.assertEqual(parse_lessons('không có'), [])
        self.assertEqual(parse_lessons('{"lessons": [{"scope": "team", "content": "x"}, {"scope": "org"}]}'), [])

    def test_non_int_replace_id_is_dropped(self):
        lessons = parse_lessons('{"lessons": [{"scope": "org", "content": "x", "replace_memory_id": "#2"}]}')
        self.assertIsNone(lessons[0]["replace_memory_id"])


class MemoryServiceTest(unittest.TestCase):
    def test_user_memory_is_active_and_org_memory_is_pending(self):
        service = MemoryService(FakeMemoriesRepository())
        self.assertEqual(service.remember(user_id=1, scope='user', content='a', source='tool').status, 'active')

        org = service.remember(user_id=1, scope='org', content='b', source='tool')
        self.assertEqual((org.status, org.user_id, org.proposed_by), ('pending', None, 1))

    def test_cannot_replace_or_forget_other_users_memory(self):
        repository = FakeMemoriesRepository([user_memory(5, user_id=2, content='của user 2')])
        service = MemoryService(repository)

        with self.assertRaises(MemoryPermissionError):
            service.remember(user_id=1, scope='user', content='x', source='tool', replace_memory_id=5)
        with self.assertRaises(MemoryPermissionError):
            service.forget(user_id=1, memory_id=5)
        self.assertEqual(repository.memories[5].content, 'của user 2')

    def test_replace_own_memory_updates_in_place(self):
        repository = FakeMemoriesRepository([user_memory(5, user_id=1, content='cũ')])
        MemoryService(repository).remember(user_id=1, scope='user', content='mới', source='tool', replace_memory_id=5)
        self.assertEqual(repository.memories[5].content, 'mới')
        self.assertEqual(len(repository.memories), 1)


class ExtractLessonsUsecaseTest(unittest.TestCase):
    def _run(self, output: str, existing=()):
        repository = FakeMemoriesRepository(existing)
        reasoner = FakeReasoner(output)
        saved = ExtractLessonsUsecase(reasoner, MemoryService(repository), repository).execute(
            ExtractLessonsUseCaseCommand(user_id=1, conversation_id=9, user_message='Sai rồi, giá phải là VNĐ')
        )
        return saved, repository, reasoner

    def test_saves_lessons_returned_by_model(self):
        saved, _, _ = self._run(
            '{"lessons": [{"scope": "org", "content": "Giá ghi bằng VNĐ"}, {"scope": "user", "content": "Ngắn gọn"}]}'
        )
        self.assertEqual([(m.scope, m.status, m.source) for m in saved],
                         [('org', 'pending', 'extractor'), ('user', 'active', 'extractor')])

    def test_no_lesson_saves_nothing(self):
        saved, repository, _ = self._run('{"lessons": []}')
        self.assertEqual(saved, [])
        self.assertEqual(repository.memories, {})

    def test_existing_memories_are_sent_to_model(self):
        _, _, reasoner = self._run('{"lessons": []}', existing=[org_memory(3, 'Giá ghi bằng VNĐ', 'pending')])
        self.assertIn('#3 [org, chờ duyệt] Giá ghi bằng VNĐ', reasoner.contexts[0].messages[1].content)

    def test_bad_lesson_is_skipped_but_others_saved(self):
        saved, _, _ = self._run(
            '{"lessons": [{"scope": "user", "content": "x", "replace_memory_id": 99}, {"scope": "user", "content": "y"}]}'
        )
        self.assertEqual([m.content for m in saved], ['y'])


if __name__ == '__main__':
    unittest.main()
