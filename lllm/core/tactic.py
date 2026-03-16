"""
Tactics — the top-level abstraction in LLLM.

A Tactic is a local, functional unit of agentic behavior that defines HOW
a group of agents solve a task.  It is the "program" that wires callers
(agents) to functions (prompts).

Core capabilities:
    1. Agent initialization from declarative config (agent_group → AgentSpec → Agent).
    2. Standardized I/O — ``call()`` accepts and returns ``str | BaseModel``.
    3. Sub-tactic composition — nest tactics like ``nn.Module`` child modules.
    4. Transparent session tracking — all ``agent.respond()`` calls are
       automatically recorded via ``_TrackedAgent`` proxy.
    5. Per-call agent isolation — each execution gets fresh agents, making
       concurrent calls thread-safe.
    6. Sync batch / async / concurrent execution via thread pool (I/O-bound).
    7. Quick constructor — single-agent usage without config or discovery.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import copy
import hashlib
import datetime as dt
import asyncio
import concurrent.futures
from dataclasses import dataclass, field
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
import logging

from lllm.core.agent import Agent, AgentCallSession
from lllm.core.prompt import Prompt, InvokeCost
from lllm.core.dialog import Message
from lllm.core.runtime import Runtime, get_default_runtime
from lllm.core.config import auto_discover_if_enabled
from lllm.core.const import APITypes
from lllm.core.log import build_log_base
from lllm.invokers import build_invoker
import lllm.utils as U

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AgentSpec — config → agent intermediate representation
# ---------------------------------------------------------------------------


@dataclass
class AgentSpec:
    """
    Parsed, validated description of one agent from config.

    Intermediate representation between raw YAML and live Agent instances.
    Config parsing fails here with clear errors; Agent construction is trivial.
    """

    name: str
    model: str
    system_prompt_path: str
    api_type: APITypes = APITypes.COMPLETION
    model_args: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, name: str, raw: Dict[str, Any]) -> AgentSpec:
        raw = raw.copy()
        model = raw.pop("model_name", None)
        if model is None:
            raise ValueError(f"Agent '{name}' missing required 'model_name'")
        system_prompt_path = raw.pop("system_prompt_path", None)
        if system_prompt_path is None:
            raise ValueError(
                f"Agent '{name}' missing required 'system_prompt_path'"
            )
        api_type_raw = raw.pop("api_type", APITypes.COMPLETION.value)
        api_type = (
            api_type_raw
            if isinstance(api_type_raw, APITypes)
            else APITypes(api_type_raw)
        )
        return cls(
            name=name,
            model=model,
            system_prompt_path=system_prompt_path,
            api_type=api_type,
            model_args=raw,
        )

    def build(self, runtime: Runtime, invoker, log_base=None, **defaults) -> Agent:
        return Agent(
            name=self.name,
            system_prompt=runtime.get_prompt(self.system_prompt_path),
            model=self.model,
            llm_invoker=invoker,
            api_type=self.api_type,
            model_args=self.model_args,
            log_base=log_base,
            **defaults,
        )


# ---------------------------------------------------------------------------
# _TrackedAgent — transparent session recording proxy
# ---------------------------------------------------------------------------


class _TrackedAgent:
    """
    Thin proxy around Agent that intercepts ``respond()`` to record
    the ``AgentCallSession`` into the tactic's session.

    All other Agent methods (``open``, ``receive``, ``switch``, ``fork``,
    ``close``, etc.) delegate transparently via ``__getattr__``.

    The developer writes normal Agent API code — tracking is invisible::

        self.agents["analyzer"].open("work", prompt_args={...})
        result = self.agents["analyzer"].respond()  # auto-recorded
    """

    __slots__ = ("_agent", "_session", "_name")

    def __init__(self, agent: Agent, session: TacticCallSession, name: str):
        object.__setattr__(self, "_agent", agent)
        object.__setattr__(self, "_session", session)
        object.__setattr__(self, "_name", name)

    def respond(
        self,
        alias: str = None,
        metadata: Optional[Dict[str, Any]] = None,
        args: Optional[Dict[str, Any]] = None,
        parser_args: Optional[Dict[str, Any]] = None,
        return_session: bool = False,
    ) -> Union[Message, AgentCallSession]:
        """Intercept respond() to record into tactic session, then return normally."""
        agent_session = self._agent.respond(
            alias=alias,
            metadata=metadata,
            args=args,
            parser_args=parser_args,
            return_session=True,
        )
        self._session.record_agent_call(self._name, agent_session)

        if return_session:
            return agent_session
        return agent_session.delivery

    def __getattr__(self, name: str) -> Any:
        return getattr(self._agent, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _TrackedAgent.__slots__:
            object.__setattr__(self, name, value)
        else:
            setattr(self._agent, name, value)

    def __repr__(self) -> str:
        return f"_TrackedAgent({self._name!r}, agent={self._agent!r})"


# ---------------------------------------------------------------------------
# TacticCallSession — per-call diagnostics (mirrors AgentCallSession)
# ---------------------------------------------------------------------------


class TacticCallSession(BaseModel):
    """
    Tracks one invocation of a tactic — every agent call, every sub-tactic
    call, total cost, and the final result.

    Forms a tree mirroring the tactic composition: each sub-tactic call
    produces its own nested ``TacticCallSession``.

    The tactic is stateless; all per-call data lives here.
    """

    tactic_name: str
    state: str = "initial"  # "initial" | "running" | "success" | "failure"

    # Per-agent tracking
    agent_sessions: Dict[str, List[AgentCallSession]] = Field(
        default_factory=dict
    )

    # Per-sub-tactic tracking
    sub_tactic_sessions: Dict[str, List["TacticCallSession"]] = Field(
        default_factory=dict
    )

    # Result and error
    delivery: Optional[Any] = None
    error: Optional[str] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # -- Recording --------------------------------------------------------

    def record_agent_call(
        self, agent_name: str, session: AgentCallSession
    ) -> None:
        if agent_name not in self.agent_sessions:
            self.agent_sessions[agent_name] = []
        self.agent_sessions[agent_name].append(session)

    def record_sub_tactic_call(
        self, tactic_name: str, session: "TacticCallSession"
    ) -> None:
        if tactic_name not in self.sub_tactic_sessions:
            self.sub_tactic_sessions[tactic_name] = []
        self.sub_tactic_sessions[tactic_name].append(session)

    def success(self, result: Any) -> None:
        self.state = "success"
        self.delivery = result

    def failure(self, error: Optional[Exception] = None) -> None:
        self.state = "failure"
        if error is not None:
            self.error = f"{type(error).__name__}: {error}"

    # -- Cost aggregation -------------------------------------------------

    @property
    def agent_cost(self) -> InvokeCost:
        total = InvokeCost()
        for sessions in self.agent_sessions.values():
            for s in sessions:
                total = total + s.cost
        return total

    @property
    def sub_tactic_cost(self) -> InvokeCost:
        total = InvokeCost()
        for sessions in self.sub_tactic_sessions.values():
            for s in sessions:
                total = total + s.total_cost
        return total

    @property
    def total_cost(self) -> InvokeCost:
        return self.agent_cost + self.sub_tactic_cost

    @property
    def agent_call_count(self) -> int:
        return sum(len(ss) for ss in self.agent_sessions.values())

    @property
    def sub_tactic_call_count(self) -> int:
        return sum(len(ss) for ss in self.sub_tactic_sessions.values())

    def summary(self) -> Dict[str, Any]:
        return {
            "tactic": self.tactic_name,
            "state": self.state,
            "agent_calls": self.agent_call_count,
            "sub_tactic_calls": self.sub_tactic_call_count,
            "total_cost": str(self.total_cost),
        }


# ---------------------------------------------------------------------------
# Registration helpers
# ---------------------------------------------------------------------------


def _normalize_name(name: Any) -> str:
    if isinstance(name, Enum) or (
        isinstance(name, type) and issubclass(name, Enum)
    ):
        return name.value
    elif isinstance(name, str):
        return name
    else:
        raise ValueError(f"Invalid tactic name: {name}")


def register_tactic_class(
    tactic_cls: Type["Tactic"], runtime: Runtime = None
) -> Type["Tactic"]:
    runtime = runtime or get_default_runtime()
    name = _normalize_name(getattr(tactic_cls, "name", None))
    assert name not in (None, ""), (
        f"Tactic class {tactic_cls.__name__} must define `name`"
    )
    if name in runtime.tactics and runtime.tactics[name] is not tactic_cls:
        raise ValueError(
            f"Tactic '{name}' already registered "
            f"with {runtime.tactics[name].__name__}"
        )
    runtime.register_tactic(name, tactic_cls)
    return tactic_cls


def get_tactic_class(name: str, runtime: Runtime = None) -> Type["Tactic"]:
    runtime = runtime or get_default_runtime()
    if name not in runtime.tactics:
        raise KeyError(
            f"Tactic '{name}' not found. "
            f"Registered: {list(runtime.tactics.keys())}"
        )
    return runtime.tactics[name]


def build_tactic(
    config: Dict[str, Any],
    ckpt_dir: str,
    stream=None,
    name: str = None,
    runtime: Runtime = None,
    **kwargs,
) -> "Tactic":
    if name is None:
        name = config.get("tactic_type")
    name = _normalize_name(name)
    tactic_cls = get_tactic_class(name, runtime)
    return tactic_cls(config, ckpt_dir, stream, runtime=runtime, **kwargs)


# ---------------------------------------------------------------------------
# Tactic
# ---------------------------------------------------------------------------


class Tactic(ABC):
    """
    A Tactic is a local, functional unit of agentic behavior.

    It defines HOW a group of agents solve a task — the "program" that wires
    callers (agents) to functions (prompts).

    **Stateless by design:**  Each ``__call__`` creates a shallow copy of the
    tactic with fresh agents and a fresh session.  ``call()`` runs on the copy,
    so concurrent invocations never share mutable state.

    **Transparent tracking:**  Agents are wrapped in ``_TrackedAgent`` proxies
    that intercept ``respond()`` and record every ``AgentCallSession`` into
    the tactic's ``TacticCallSession``.  The developer writes normal Agent
    API code — tracking is invisible.

    **Concurrency and Batch:**  ``acall()``, ``bcall()``, and ``ccall()`` use a thread
    pool because LLM calls are I/O-bound (GIL released during network waits).

    I/O contract:
        ``call()`` accepts ``str | BaseModel`` and returns ``str | BaseModel``.
        Subclasses narrow these types for their specific interface.

    Example::

        class Analytica(Tactic):
            name = "analytica"
            agent_group = ["analyzer", "synthesizer"]

            def call(self, task: str, **kwargs) -> str:
                analyzer = self.agents["analyzer"]
                synthesizer = self.agents["synthesizer"]

                analyzer.open("work", prompt_args={"task": task})
                analysis = analyzer.respond()  # auto-tracked

                synthesizer.open("work", prompt_args={"analysis": analysis.content})
                return synthesizer.respond().content  # auto-tracked
    """

    name: str = None
    agent_group: List[str] = None

    # -- Auto-registration ------------------------------------------------

    def __init_subclass__(
        cls,
        register: bool = True,
        runtime: Optional[Runtime] = None,
        **kwargs,
    ):
        super().__init_subclass__(**kwargs)
        if register and getattr(cls, "name", None):
            register_tactic_class(cls, runtime=runtime or get_default_runtime())

    # -- Construction -----------------------------------------------------

    def __init__(
        self,
        config: Dict[str, Any],
        ckpt_dir: str,
        stream=None,
        runtime: Optional[Runtime] = None,
    ):
        self._runtime = runtime or get_default_runtime()
        self._sub_tactics: Dict[str, Tactic] = {}

        auto_discover_if_enabled(
            config.get("auto_discover"), runtime=self._runtime
        )

        self.config = config
        self.ckpt_dir = ckpt_dir
        self._stream = stream or U.PrintSystem()
        self._stream_backup = self._stream
        self.st = None
        self._log_base = build_log_base(config)
        self.llm_invoker = build_invoker(config)

        # Parse agent specs — agents are built per-call, not here
        assert self.agent_group is not None, (
            f"agent_group not set for tactic '{self.name}'"
        )
        raw_configs = config.get("agent_group_configs", {})
        self._agent_specs: Dict[str, AgentSpec] = {}
        for agent_name in self.agent_group:
            if agent_name not in raw_configs:
                raise ValueError(
                    f"Agent '{agent_name}' in agent_group of '{self.name}' "
                    f"not found in agent_group_configs. "
                    f"Available: {sorted(raw_configs.keys())}"
                )
            self._agent_specs[agent_name] = AgentSpec.from_config(
                agent_name, raw_configs[agent_name]
            )

        # Thread pool size for batch/concurrent execution
        self._max_workers: int = config.get("max_workers", 4)

        # Per-call state — set by _execute on the copy, not used on the original
        self.agents: Dict[str, Union[Agent, _TrackedAgent]] = {}
        self._session: Optional[TacticCallSession] = None

    # -- Sub-tactic composition -------------------------------------------

    def __setattr__(self, name: str, value: Any) -> None:
        if isinstance(value, Tactic) and name not in ("_sub_tactics",):
            if hasattr(self, "_sub_tactics"):
                self._sub_tactics[name] = value
        super().__setattr__(name, value)

    @property
    def sub_tactics(self) -> Dict[str, "Tactic"]:
        return dict(self._sub_tactics)

    # -- Fresh agent creation (per-call) ----------------------------------

    def _create_fresh_agents(self) -> Dict[str, Agent]:
        """
        Build fresh agents from specs.

        Shares expensive objects (invoker, runtime, prompts).
        Only the mutable Agent shell (with empty _dialogs) is new.
        """
        defaults = dict(
            max_exception_retry=self.config.get("max_exception_retry", 3),
            max_interrupt_steps=self.config.get("max_interrupt_steps", 5),
            max_llm_recall=self.config.get("max_llm_recall", 3),
        )
        return {
            agent_name: spec.build(
                self._runtime, self.llm_invoker, self._log_base, **defaults
            )
            for agent_name, spec in self._agent_specs.items()
        }

    # -- Core execution ---------------------------------------------------

    @abstractmethod
    def call(self, task: Union[str, BaseModel], **kwargs) -> Union[str, BaseModel]:
        """
        Override in subclasses.

        ``self.agents`` contains fresh, tracked agents for this call.
        Every ``agent.respond()`` is automatically recorded into the
        tactic's session — no manual tracking needed.
        """
        pass # user-defined call method

    def _execute(
        self,
        task: Union[str, BaseModel],
        session_name: str = None,
        return_session: bool = False,
        **kwargs,
    ) -> Union[str, BaseModel, TacticCallSession]:
        """
        Create an isolated copy with fresh agents, run call(), capture session.

        Thread-safe: each invocation operates on its own shallow copy.
        """
        if session_name is None:
            task_str = task if isinstance(task, str) else task.model_dump_json()
            task_hash = hashlib.md5(task_str.encode()).hexdigest()[:8]
            session_name = (
                f"{self.name}_{task_hash}"
                f"_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

        # Shallow copy shares immutable state (config, runtime, invoker, specs)
        ctx = copy.copy(self)
        ctx._sub_tactics = dict(self._sub_tactics)  # isolate sub-tactic dict
        session = TacticCallSession(tactic_name=self.name)
        session.state = "running"
        ctx._session = session

        # Fresh agents wrapped in tracking proxies
        raw_agents = ctx._create_fresh_agents()
        ctx.agents = {
            agent_name: _TrackedAgent(agent, session, agent_name)
            for agent_name, agent in raw_agents.items()
        }

        ctx.set_st(session_name)
        try:
            result = ctx.call(task, **kwargs)
            session.success(result)
        except Exception as e:
            session.failure(e)
            raise
        finally:
            ctx.restore_st()

        if return_session:
            return session
        return result

    def __call__(
        self,
        task: Union[str, BaseModel],
        session_name: str = None,
        return_session: bool = False,
        **kwargs,
    ) -> Union[str, BaseModel, TacticCallSession]:
        """
        Execute with per-call isolation and transparent session tracking.

        Args:
            task: Input (``str`` or typed ``BaseModel``).
            session_name: Optional name for logging.
            return_session: If True, return ``TacticCallSession``
                (result at ``session.delivery``).
            **kwargs: Passed to ``call()``.
        """
        return self._execute(task, session_name, return_session, **kwargs)

    async def acall(
        self,
        task: Union[str, BaseModel],
        return_session: bool = False,
        **kwargs,
    ) -> Union[str, BaseModel, TacticCallSession]:
        """
        Async single-task execution.

        Runs ``_execute`` in the default thread executor so it doesn't
        block the event loop.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._execute(
                task, return_session=return_session, **kwargs
            ),
        )

    def bcall(
        self,
        tasks: List[Union[str, BaseModel]],
        return_sessions: bool = False,
        max_workers: int = None,
        **kwargs,
    ) -> List[Union[str, BaseModel, TacticCallSession]]:
        """
        Run multiple tasks concurrently using threads. Returns results in order.

        Thread-safe: each task gets its own fresh agents via ``_execute``.
        Uses threads because LLM API calls are I/O-bound.

        Args:
            tasks: List of inputs.
            return_sessions: If True, return ``TacticCallSession`` per task.
            max_workers: Max concurrent threads (default: config ``max_workers``).
            **kwargs: Passed to ``call()`` for every task.
        """
        workers = max_workers or self._max_workers
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    self._execute, task, None, return_sessions, **kwargs
                )
                for task in tasks
            ]
            return [f.result() for f in futures]

    async def ccall(
        self,
        tasks: List[Union[str, BaseModel]],
        return_sessions: bool = False,
        max_workers: int = None,
        **kwargs,
    ) -> AsyncGenerator[
        Tuple[int, Union[str, BaseModel, TacticCallSession]], None
    ]:
        """
        Concurrent execution — yield ``(index, result)`` as tasks complete.

        Unlike ``bcall``, results arrive fastest-first.  The index matches
        the position in the input list.

        Usage::

            async for idx, result in tactic.ccall(tasks):
                print(f"Task {idx}: {result}")
        """
        workers = max_workers or self._max_workers
        loop = asyncio.get_running_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            # Wrap each task to carry its index through the executor
            def _run_indexed(
                idx: int, t: Union[str, BaseModel]
            ) -> Tuple[int, Any]:
                result = self._execute(
                    t, return_session=return_sessions, **kwargs
                )
                return idx, result

            futures = [
                loop.run_in_executor(pool, _run_indexed, idx, task)
                for idx, task in enumerate(tasks)
            ]

            for coro in asyncio.as_completed(futures):
                idx, result = await coro
                yield idx, result

    # -- Session management (WIP: refactor with logging system) -----------

    def set_st(self, session_name: str) -> None:
        self.st = U.StreamWrapper(self._stream, self._log_base, session_name)

    def restore_st(self) -> None:
        self.st = None

    def silent(self) -> None:
        self._stream = U.PrintSystem(silent=True)

    def restore(self) -> None:
        self._stream = self._stream_backup

    # -- Quick constructor ------------------------------------------------

    @classmethod
    def quick(
        cls,
        system_prompt: Union[str, Prompt],
        model: str = "gpt-4o",
        **model_args,
    ) -> Agent:
        """
        Create a single agent without config or discovery::

            agent = Tactic.quick("You are a helpful assistant.")
            agent.open("chat")
            agent.receive("Hello!")
            print(agent.respond().content)
        """
        if isinstance(system_prompt, str):
            prompt = Prompt(path="_quick/system", prompt=system_prompt)
        else:
            prompt = system_prompt
        invoker = build_invoker({"invoker": "litellm"})
        return Agent(
            name="assistant",
            system_prompt=prompt,
            model=model,
            llm_invoker=invoker,
            model_args=model_args,
        )

    # -- Representation ---------------------------------------------------

    def __repr__(self) -> str:
        parts = [f"Tactic(name={self.name!r}"]
        parts.append(f"agents={list(self._agent_specs.keys())}")
        if self._sub_tactics:
            parts.append(f"sub_tactics={list(self._sub_tactics.keys())}")
        return ", ".join(parts) + ")"