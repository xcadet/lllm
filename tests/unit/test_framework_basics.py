import uuid
import types

import pytest

from lllm.core.models import PROMPT_REGISTRY, Prompt, Message, FunctionCall, MCP
from lllm.core.const import APITypes, Roles, Invokers
from lllm.core.agent import Prompts, register_prompt, Orchestrator
from lllm.proxies import (
    BaseProxy,
    Proxy,
    PROXY_REGISTRY,
    ProxyRegistrator,
    load_builtin_proxies,
)
import lllm.invokers as invoker_module
from lllm.invokers.litellm import LiteLLMInvoker


@pytest.fixture
def prompt_registry_cleanup():
    before = set(PROMPT_REGISTRY.keys())
    yield
    for key in list(PROMPT_REGISTRY.keys()):
        if key not in before:
            PROMPT_REGISTRY.pop(key, None)


@pytest.fixture
def proxy_registry_cleanup():
    before = set(PROXY_REGISTRY.keys())
    yield
    for key in list(PROXY_REGISTRY.keys()):
        if key not in before:
            PROXY_REGISTRY.pop(key, None)


def test_prompts_helper_and_handlers(prompt_registry_cleanup):
    path = f"test/{uuid.uuid4().hex}"
    prompt = Prompt(path=path, prompt="Hello!")
    register_prompt(prompt)

    helper = Prompts("test")
    resolved = helper(path.split("/", 1)[1])
    assert resolved.path == path
    assert resolved.interrupt_handler.prompt == prompt.interrupt_prompt
    assert resolved.interrupt_handler_final.prompt == prompt.interrupt_final_prompt


def test_proxy_registration_and_dispatch(proxy_registry_cleanup):
    path = f"test/proxy/{uuid.uuid4().hex}"

    @ProxyRegistrator(path=path, name="Test Proxy", description="For tests")
    class _TProxy(BaseProxy):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def echo(self, payload):
            return {"payload": payload, "cutoff": self.cutoff_date is not None}

    proxy = Proxy(activate_proxies=[path])
    assert path in proxy.available()
    response = proxy(f"{path}.echo", payload=123)
    assert response["payload"] == 123


def test_proxy_api_catalog_and_docs(proxy_registry_cleanup):
    path = f"test/proxy/catalog/{uuid.uuid4().hex}"

    @ProxyRegistrator(path=path, name="Doc Proxy", description="Doc friendly proxy")
    class _DocProxy(BaseProxy):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        @BaseProxy.endpoint(
            category="utility",
            endpoint="info",
            name="Info",
            description="Return provided details.",
            params={"value*": (str, "demo")},
            response={"value": "demo"},
            method="POST",
        )
        def info(self, params: dict):
            return params

    proxy = Proxy(activate_proxies=[path])
    catalog = proxy.api_catalog()
    assert path in catalog
    entry = catalog[path]
    assert entry["display_name"] == "Doc Proxy"
    assert entry["endpoints"][0]["endpoint"] == "info"

    docs = proxy.retrieve_api_docs(path)
    assert "Doc Proxy" in docs
    assert "info" in docs

    auto_test_result = proxy.proxies[path].auto_test()
    assert auto_test_result["info"]["status"] == "ok"


def test_mcp_to_tool_and_validation():
    mcp = MCP(server_label="docs", server_url="https://example.com/mcp", require_approval="manual", allowed_tools=["search"])
    tool = mcp.to_tool(Invokers.LITELLM)
    assert tool["type"] == "mcp"
    assert tool["require_approval"] == "manual"
    assert tool["allowed_tools"] == ["search"]

    with pytest.raises(ValueError):
        MCP(server_label="broken", server_url="https://example.com", require_approval="invalid")


def test_litellm_invoker_build_tools_includes_mcp():
    mcp = MCP(server_label="kb", server_url="https://example.com/kb")
    prompt = Prompt(
        path="test/mcp/prompt",
        prompt="Hello",
        mcp_servers_list=[mcp],
    )
    invoker = LiteLLMInvoker.__new__(LiteLLMInvoker)
    tools = invoker._build_tools(prompt)
    assert any(tool.get("type") == "mcp" and tool["server_label"] == "kb" for tool in tools)


def test_load_builtin_proxies_handles_missing_modules():
    loaded, errors = load_builtin_proxies(modules=["lllm.proxies.builtin"])
    assert "lllm.proxies.builtin" in loaded
    _, errors = load_builtin_proxies(modules=["lllm.does.not.exist"])
    assert "lllm.does.not.exist" in errors


def test_proxy_instantiation_runs_auto_discover(monkeypatch, proxy_registry_cleanup):
    call_args = []

    def _fake_auto_discover(flag=None, **_):
        call_args.append(flag)

    monkeypatch.setattr(
        "lllm.core.discovery.auto_discover_if_enabled", _fake_auto_discover, raising=True
    )
    Proxy()
    assert call_args == [None]


def test_agent_base_triggers_auto_discover(monkeypatch, tmp_path, prompt_registry_cleanup):
    calls = []

    def _fake_auto_discover(flag=None, **_):
        calls.append(flag)

    monkeypatch.setattr(
        "lllm.core.agent.auto_discover_if_enabled", _fake_auto_discover, raising=True
    )
    monkeypatch.setattr("lllm.core.agent.build_invoker", lambda config: object())

    prompt = Prompt(path="mini/system", prompt="System prompt")
    register_prompt(prompt)

    class MiniAgent(Orchestrator, register=False):
        agent_type = "mini-agent"
        agent_group = ["mini"]

        def call(self, task: str, **kwargs):
            return task

    config = {
        "name": "mini",
        "log_dir": tmp_path.as_posix(),
        "log_type": "none",
        "agent_configs": {
            "mini": {
                "model_name": "gpt-4o-mini",
                "system_prompt_path": "mini/system",
            }
        },
    }

    MiniAgent(config, ckpt_dir=tmp_path.as_posix(), stream=None)
    assert calls == [None]


def test_agent_base_respects_auto_discover_flag(monkeypatch, tmp_path, prompt_registry_cleanup):
    calls = []

    def _fake_auto_discover(flag=None, **_):
        calls.append(flag)

    monkeypatch.setattr(
        "lllm.core.agent.auto_discover_if_enabled", _fake_auto_discover, raising=True
    )
    monkeypatch.setattr("lllm.core.agent.build_invoker", lambda config: object())

    prompt = Prompt(path="mini/system", prompt="System prompt")
    register_prompt(prompt)

    class MiniAgent(Orchestrator, register=False):
        agent_type = "mini-agent"
        agent_group = ["mini"]

        def call(self, task: str, **kwargs):
            return task

    config = {
        "name": "mini",
        "log_dir": tmp_path.as_posix(),
        "log_type": "none",
        "auto_discover": False,
        "agent_configs": {
            "mini": {
                "model_name": "gpt-4o-mini",
                "system_prompt_path": "mini/system",
            }
        },
    }

    MiniAgent(config, ckpt_dir=tmp_path.as_posix(), stream=None)
    assert calls == [False]


def test_convert_dialog_handles_response_messages(monkeypatch):
    invoker = LiteLLMInvoker.__new__(LiteLLMInvoker)
    tool_call = FunctionCall(id="call-1", name="echo", arguments={"value": "test"})
    dialog = types.SimpleNamespace(
        messages=[
            Message(
                role=Roles.TOOL_CALL,
                content="Calling echo",
                name="assistant",
                function_calls=[tool_call],
                model="gpt-4o-mini",
                api_type=APITypes.RESPONSE,
            ),
            Message(
                role=Roles.TOOL,
                content="ok",
                name="tool",
                extra={"tool_call_id": "call-1"},
                model="gpt-4o-mini",
            ),
        ]
    )

    converted = invoker._convert_dialog(dialog)
    assert converted[0]["role"] == "assistant"
    assert converted[0]["tool_calls"][0]["function"]["name"] == "echo"
    assert converted[1]["role"] == "tool"
    assert converted[1]["tool_call_id"] == "call-1"


def test_prompts_auto_discover_flag(monkeypatch, prompt_registry_cleanup):
    calls = []

    def _fake_auto_discover(flag=None, **_):
        calls.append(flag)

    monkeypatch.setattr("lllm.core.discovery.auto_discover_if_enabled", _fake_auto_discover, raising=True)
    helper = Prompts("test", auto_discover=False)
    with pytest.raises(KeyError):
        helper("missing")
    assert calls == [False]


def test_proxy_respects_auto_discover_flag(monkeypatch, proxy_registry_cleanup):
    calls = []

    def _fake_auto_discover(flag=None, **_):
        calls.append(flag)

    monkeypatch.setattr(
        "lllm.core.discovery.auto_discover_if_enabled", _fake_auto_discover, raising=True
    )
    Proxy(auto_discover=False)
    assert calls == [False]


def test_invoker_registry_custom_builder(monkeypatch):
    class DummyInvoker:
        def __init__(self, cfg):
            self.cfg = cfg

    monkeypatch.setitem(
        invoker_module._PROVIDER_BUILDERS, "dummy", lambda cfg: DummyInvoker(cfg)
    )
    config = {"invoker": "dummy", "invoker_config": {"token": "abc"}}
    invoker = invoker_module.build_invoker(config)
    assert isinstance(invoker, DummyInvoker)
    assert invoker.cfg == {"token": "abc"}


def test_invoker_registry_unknown_name(monkeypatch):
    monkeypatch.setitem(invoker_module._PROVIDER_BUILDERS, "openai", lambda cfg: cfg)
    config = {"invoker": "missing"}
    with pytest.raises(KeyError):
        invoker_module.build_invoker(config)
