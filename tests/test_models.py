'''
Chọn model khi chat và quản lý bảng models: repository giả, không cần DB hay gọi API thật.
'''
import unittest
from dataclasses import replace

from ollama import ResponseError

from src.app.ports.model_reasoner import ModelUnavailableError
from src.app.services.chat_model_selector import select_chat_model
from src.app.usecases.admin_models_usecase import (
    AdminModelsUsecase,
    ModelChanges,
    ModelNotFoundError,
    ModelValidationError,
)
from src.dom.entities.ai_model import AIModel
from src.inf.model_reasoner.errors import translate_api_error
from src.inf.model_reasoner.ollama_model_reasoner import OllamaModelReasoner

PROVIDERS = ["openai", "groq", "ollama"]


class FakeModelsRepository:
    def __init__(self, models: list[AIModel] = ()):
        self.models = {m.id: m for m in models}

    def list_all(self):
        return list(self.models.values())

    def list_active(self):
        return [m for m in self.models.values() if m.is_active]

    def get_by_id(self, model_id):
        return self.models.get(model_id)

    def get_default(self):
        return next((m for m in self.models.values() if m.is_default and m.is_active), None)

    def create(self, model):
        model.id = max(self.models, default=0) + 1
        return self.update(model)

    def update(self, model):
        if model.is_default:  # Như ràng buộc trong DB: chỉ một model mặc định
            for other in self.models.values():
                other.is_default = False
        self.models[model.id] = replace(model)
        return self.models[model.id]

    def delete(self, model_id):
        return self.models.pop(model_id, None) is not None


def make_model(id, modes=("low", "medium", "high"), is_active=True, is_default=False):
    return AIModel(
        id=id, display_name=f"Model {id}", model_name=f"model-{id}", provider="openai",
        reasoning_modes=list(modes), is_active=is_active, is_default=is_default,
    )


class SelectChatModelTest(unittest.TestCase):
    def setUp(self):
        self.repo = FakeModelsRepository([
            make_model(1, is_default=True),
            make_model(2, modes=()),
            make_model(3, is_active=False),
        ])

    def test_no_choice_uses_default_model_and_first_mode(self):
        model, mode = select_chat_model(self.repo, None, None)
        self.assertEqual((model.id, mode), (1, "low"))

    def test_chosen_mode_is_kept(self):
        model, mode = select_chat_model(self.repo, 1, "high")
        self.assertEqual((model.id, mode), (1, "high"))

    def test_model_without_reasoning_ignores_mode(self):
        model, mode = select_chat_model(self.repo, 2, "high")
        self.assertEqual((model.id, mode), (2, None))

    def test_invalid_choices_are_rejected(self):
        cases = [
            (3, None),  # Model đã bị tắt
            (99, None),  # Model không tồn tại
            (1, "ultra"),  # Chế độ không có trong danh sách admin nhập
        ]
        for model_id, mode in cases:
            with self.subTest(model_id=model_id, mode=mode), self.assertRaises(ModelUnavailableError):
                select_chat_model(self.repo, model_id, mode)

    def test_no_default_model(self):
        with self.assertRaises(ModelUnavailableError):
            select_chat_model(FakeModelsRepository([make_model(1)]), None, None)


class AdminModelsUsecaseTest(unittest.TestCase):
    def test_create_cleans_input_and_is_inactive_by_default(self):
        model = AdminModelsUsecase(FakeModelsRepository(), PROVIDERS).create_model(ModelChanges(
            display_name=" GPT ", model_name=" gpt-5 ", provider="OpenAI",
            reasoning_modes=["low", " ", "high", "low"],
        ))
        self.assertEqual(
            (model.display_name, model.model_name, model.provider, model.reasoning_modes, model.is_active),
            ("GPT", "gpt-5", "openai", ["low", "high"], False),
        )

    def test_invalid_models_are_rejected(self):
        usecase = AdminModelsUsecase(FakeModelsRepository(), PROVIDERS)
        cases = [
            ModelChanges(display_name="", model_name="x", provider="openai"),
            ModelChanges(display_name="X", model_name=" ", provider="openai"),
            ModelChanges(display_name="X", model_name="x", provider="openia"),  # Sai chính tả nhà cung cấp
            ModelChanges(display_name="X", model_name="x", provider="openai", is_default=True),  # Mặc định mà tắt
        ]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ModelValidationError):
                usecase.create_model(changes)

    def test_only_one_default(self):
        repo = FakeModelsRepository([make_model(1, is_default=True), make_model(2)])
        AdminModelsUsecase(repo, PROVIDERS).update_model(2, ModelChanges(is_default=True))
        self.assertEqual([m.id for m in repo.list_all() if m.is_default], [2])

    def test_delete(self):
        repo = FakeModelsRepository([make_model(1)])
        usecase = AdminModelsUsecase(repo, PROVIDERS)
        usecase.delete_model(1)
        with self.assertRaises(ModelNotFoundError):
            usecase.delete_model(1)


class FakeAPIError(Exception):
    '''Giống APIStatusError của SDK openai/groq: có status_code, param, message'''

    def __init__(self, status_code, message, param=None):
        super().__init__(message)
        self.status_code, self.message, self.param = status_code, message, param


class ProviderErrorTranslationTest(unittest.TestCase):
    def translate(self, error):
        return translate_api_error(error, "OpenAI", "gpt-x", "high")

    def test_wrong_model_name(self):
        for error in (
                FakeAPIError(404, "The model `gpt-x` does not exist or you do not have access to it."),
                FakeAPIError(400, "invalid model ID", param="model"),
        ):
            with self.subTest(error=error):
                self.assertIn("không tồn tại", str(self.translate(error)))

    def test_wrong_reasoning_mode(self):
        error = FakeAPIError(400, "Unsupported value: 'ultra' is not supported with this model.", param="reasoning.effort")
        self.assertIn("chế độ suy luận", str(self.translate(error)))

    def test_bad_api_key(self):
        self.assertIn("API key", str(self.translate(FakeAPIError(401, "Incorrect API key"))))

    def test_tools_not_supported(self):
        error = FakeAPIError(400, "This model does not support tools")
        self.assertIn("không hỗ trợ gọi tool", str(self.translate(error)))

    def test_other_errors_are_kept(self):
        error = FakeAPIError(500, "Internal server error")
        self.assertIs(self.translate(error), error)

    def test_ollama_errors(self):
        reasoner = OllamaModelReasoner(host="http://localhost:1", model="qwen-x", think=True)
        self.assertIn("không tồn tại", str(reasoner._config_error(ResponseError("model 'qwen-x' not found", 404))))
        self.assertIn("chế độ suy luận", str(reasoner._config_error(ResponseError('"qwen-x" does not support thinking', 400))))
        self.assertIn("không hỗ trợ gọi tool", str(reasoner._config_error(ResponseError("qwen-x does not support tools", 400))))
        self.assertIsNone(reasoner._config_error(ResponseError("server overloaded", 503)))

    def test_ollama_rejects_invalid_think_before_sending(self):
        from src.dom.context import Context
        from src.dom.message.text_message import TextMessage

        reasoner = OllamaModelReasoner(host="http://127.0.0.1:9", model="qwen-x", think="hgih")
        with self.assertRaises(ModelUnavailableError) as raised:
            reasoner.decide(Context(messages=[TextMessage(role="user", content="hi")]), [])
        self.assertIn("hgih", str(raised.exception))


class FailingAgent:
    def invoke_stream(self, context):
        raise ModelUnavailableError("Model 'gpt-x' không tồn tại")
        yield


class FakeMessagesRepository:
    def __init__(self):
        self.saved = []

    def get_messages(self, conversation_id):
        return []

    def add_message(self, conversation_id, message):
        self.saved.append(message)


class ChatWithWrongModelTest(unittest.TestCase):
    def test_nothing_is_saved_when_model_fails_immediately(self):
        from src.app.usecases.chat_usecase import ChatUseCase, ChatUseCaseCommand
        from src.dom.entities.message import Message

        repo = FakeMessagesRepository()
        usecase = ChatUseCase(agent=FailingAgent(), conversation_repository=repo)

        with self.assertRaises(ModelUnavailableError):
            list(usecase.execute_stream(ChatUseCaseCommand(conversation_id=1, messages=Message(role="user", content="hi"))))

        self.assertEqual(repo.saved, [])  # Người dùng đổi model rồi gửi lại, lịch sử không có tin nhắn rác


class FakeReasoner:
    '''Giả lập nhà cung cấp: chế độ "hgih" bị từ chối, chế độ "boom" lỗi lạ'''

    def __init__(self, model, mode, calls):
        self.model, self.mode = model, mode
        calls.append(mode)

    def decide(self, context, tools):
        assert [tool.tool_name for tool in tools] == ["ping"]  # Luôn gửi kèm tool như khi chat
        if self.mode == "hgih":
            raise ModelUnavailableError("Model không hỗ trợ chế độ suy luận 'hgih'")
        if self.mode == "boom":
            raise RuntimeError("x" * 1000)
        return "OK"


class TestModelUsecaseTest(unittest.TestCase):
    def run_test(self, modes, provider="openai"):
        from src.app.usecases.test_model_usecase import TestModelUsecase

        calls = []
        usecase = TestModelUsecase(lambda model, mode: FakeReasoner(model, mode, calls), PROVIDERS)
        results = usecase.execute(AIModel(display_name="", model_name="gpt-x", provider=provider, reasoning_modes=modes))
        return results, calls

    def test_each_mode_is_called_once(self):
        results, calls = self.run_test(["low", "hgih", "boom"])

        self.assertEqual(calls, ["low", "hgih", "boom"])
        self.assertEqual([r.ok for r in results], [True, False, False])
        self.assertIn("hgih", results[1].message)
        self.assertTrue(results[2].message.startswith("Lỗi khác từ nhà cung cấp"))
        self.assertLessEqual(len(results[2].message), 400)  # Lỗi dài bị cắt bớt

    def test_model_without_reasoning_is_called_once_without_mode(self):
        results, calls = self.run_test([])
        self.assertEqual((calls, results[0].ok), ([None], True))

    def test_invalid_provider_is_rejected_before_calling(self):
        with self.assertRaises(ModelValidationError):
            self.run_test(["low"], provider="openia")


class ProviderRegistryTest(unittest.TestCase):
    '''Mã + tên hiển thị nhà cung cấp chỉ khai báo trên adapter, mọi nơi khác lấy từ đó'''

    def test_providers_come_from_adapters(self):
        from src import bootstrap
        from src.inf.model_reasoner.anthropic_model_reasoner import AnthropicModelReasoner
        from src.inf.model_reasoner.groq_model_reasoner import GroqModelReasoner
        from src.inf.model_reasoner.openai_model_reasoner import OpenAIModelReasoner

        providers = bootstrap.AppContainer().supported_providers()
        names = [p.name for p in providers]

        self.assertEqual(len(names), len(set(names)))  # Hai adapter không được trùng mã
        self.assertEqual(names, list(bootstrap.REASONER_FACTORIES))
        for adapter in (OpenAIModelReasoner, GroqModelReasoner, OllamaModelReasoner, AnthropicModelReasoner):
            self.assertIn((adapter.PROVIDER, adapter.PROVIDER_LABEL), [(p.name, p.label) for p in providers])

    def test_api_sends_labels(self):
        from fastapi.testclient import TestClient
        from src import bootstrap
        from src.pre.api.app import create_app
        from src.pre.api.dependencies import get_current_user_id, require_admin

        repo = FakeModelsRepository([
            replace(make_model(1, is_default=True), provider="groq"),
            replace(make_model(2), provider="da-bo-adapter"),  # Mã trong CSDL không còn adapter nào khai báo
        ])

        class UoW:
            def __enter__(self):
                self.models = repo
                return self

            def __exit__(self, *args):
                pass

        class Container(bootstrap.AppContainer):
            def unit_of_work(self):
                return UoW()

        app = create_app(Container())
        app.dependency_overrides[require_admin] = lambda: 1
        app.dependency_overrides[get_current_user_id] = lambda: 1
        client = TestClient(app)

        self.assertIn({"name": "groq", "label": "Groq"}, client.get("/admin/models/providers").json())
        labels = {m["id"]: m["provider_label"] for m in client.get("/models/").json()}
        self.assertEqual(labels, {1: "Groq", 2: "da-bo-adapter"})


class ChatReasonerFactoryTest(unittest.TestCase):
    def test_unknown_provider(self):
        from src.bootstrap import build_chat_reasoner

        with self.assertRaises(ModelUnavailableError):
            build_chat_reasoner(replace(make_model(1), provider="anthropicc"), None)


if __name__ == '__main__':
    unittest.main()
