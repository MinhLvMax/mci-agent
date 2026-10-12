'''
Chạy: python -m unittest discover tests
Kiểm tra luật nghiệp vụ trang quản trị bằng repository giả, không cần DB.
'''
import unittest
from dataclasses import replace

from src.app.usecases.admin_skills_usecase import (
    AdminSkillsUsecase,
    SkillChanges,
    SkillValidationError,
)
from src.app.usecases.admin_users_usecase import AdminRuleError, AdminUsersUsecase, UpdateUserCommand
from src.app.usecases.signup_usecase import EmailAlreadyExistsError, SignupValidationError
from src.dom.entities.skill import Skill
from src.dom.entities.user import User
from src.inf.security.bcrypt_password_hasher import BcryptPasswordHasher


class FakeConnection:
    def rollback(self):
        pass


class FakeUsersRepository:
    def __init__(self, users: list[User]):
        self.connection = FakeConnection()
        self.users = {u.id: u for u in users}

    def get_user_by_id(self, user_id):
        return self.users.get(user_id)

    def get_user_by_email(self, email):
        return next((u for u in self.users.values() if u.email.lower() == email.lower()), None)

    def count_active_admins(self):
        return sum(1 for u in self.users.values() if u.role == 'admin' and u.is_active)

    def update(self, user_id, email=None, role=None, is_active=None):
        user = self.users[user_id]
        self.users[user_id] = replace(
            user,
            email=email if email is not None else user.email,
            role=role if role is not None else user.role,
            is_active=is_active if is_active is not None else user.is_active,
        )
        return self.users[user_id]

    def set_password_hash(self, user_id, password_hash):
        self.users[user_id].password_hash = password_hash


class FakeSkillsRepository:
    def __init__(self, skills: list[Skill] = ()):
        self.connection = FakeConnection()
        self.skills = {s.id: s for s in skills}

    def get_by_id(self, skill_id):
        return self.skills.get(skill_id)

    def create(self, skill):
        skill.id = max(self.skills, default=0) + 1
        self.skills[skill.id] = skill
        return skill

    def update(self, skill):
        self.skills[skill.id] = skill
        return skill


def make_user(id, email, role='user', is_active=True):
    return User(id=id, email=email, password_hash='x', role=role, is_active=is_active)


class AdminUsersUsecaseTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeUsersRepository([
            make_user(1, 'admin@a.com', role='admin'),
            make_user(2, 'b@a.com'),
            make_user(3, 'c@a.com', is_active=False),
        ])
        self.usecase = AdminUsersUsecase(self.repo, BcryptPasswordHasher())

    def test_activate_and_promote_user(self):
        self.usecase.update_user(UpdateUserCommand(actor_id=1, user_id=3, is_active=True))
        self.usecase.update_user(UpdateUserCommand(actor_id=1, user_id=2, role='admin'))
        self.assertTrue(self.repo.users[3].is_active)
        self.assertEqual(self.repo.users[2].role, 'admin')

    def test_admin_cannot_demote_or_disable_self(self):
        with self.assertRaises(AdminRuleError):
            self.usecase.update_user(UpdateUserCommand(actor_id=1, user_id=1, role='user'))
        with self.assertRaises(AdminRuleError):
            self.usecase.update_user(UpdateUserCommand(actor_id=1, user_id=1, is_active=False))
        self.assertEqual(self.repo.users[1].role, 'admin')

    def test_admin_can_demote_another_admin_when_one_remains(self):
        self.repo.users[2].role = 'admin'
        self.usecase.update_user(UpdateUserCommand(actor_id=1, user_id=2, role='user'))
        self.assertEqual(self.repo.users[2].role, 'user')

    def test_cannot_remove_last_active_admin(self):
        # Admin 2 bị khoá -> admin 1 là admin hoạt động cuối cùng, admin 4 (đang khoá) không được tính
        self.repo.users[4] = make_user(4, 'd@a.com', role='admin', is_active=True)
        self.repo.users[1].is_active = False
        with self.assertRaises(AdminRuleError):
            self.usecase.update_user(UpdateUserCommand(actor_id=1, user_id=4, is_active=False))

    def test_email_validation_and_duplicates(self):
        with self.assertRaises(SignupValidationError):
            self.usecase.update_user(UpdateUserCommand(actor_id=1, user_id=2, email='khong-hop-le'))
        with self.assertRaises(EmailAlreadyExistsError):
            self.usecase.update_user(UpdateUserCommand(actor_id=1, user_id=2, email='C@A.com'))

        self.usecase.update_user(UpdateUserCommand(actor_id=1, user_id=2, email=' New@A.com '))
        self.assertEqual(self.repo.users[2].email, 'new@a.com')

    def test_reset_password_validates_and_hashes(self):
        with self.assertRaises(SignupValidationError):
            self.usecase.reset_password(2, 'ngan')

        self.usecase.reset_password(2, 'matkhaumoi123')
        self.assertTrue(self.repo.users[2].password_hash.startswith('$2'))  # bcrypt


class AdminSkillsUsecaseTest(unittest.TestCase):
    def test_new_skill_is_inactive_by_default(self):
        skill = AdminSkillsUsecase(FakeSkillsRepository()).create_skill(
            SkillChanges(name='viet-kich-ban', description='Viết kịch bản video', instructions='...')
        )
        self.assertFalse(skill.is_active)

    def test_invalid_skills_are_rejected(self):
        usecase = AdminSkillsUsecase(FakeSkillsRepository())
        cases = [
            SkillChanges(name='Viết Kịch Bản', description='x'),  # Tên không phải slug
            SkillChanges(name='core-2', always_on=True, instructions='  '),  # Luôn bật mà không có chỉ dẫn
            SkillChanges(name='abc', description=''),  # Theo yêu cầu mà không có mô tả
            SkillChanges(name='abc', description='x', config={"tools": "web_search"}),  # tools không phải list
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(SkillValidationError):
                usecase.create_skill(changes)

    def test_update_only_changes_given_fields(self):
        repo = FakeSkillsRepository([
            Skill(id=1, name='core', description='', instructions='Bạn là trợ lý.', always_on=True, is_active=True)
        ])
        skill = AdminSkillsUsecase(repo).update_skill(1, SkillChanges(is_active=False))
        self.assertEqual((skill.name, skill.instructions, skill.is_active), ('core', 'Bạn là trợ lý.', False))


if __name__ == '__main__':
    unittest.main()
