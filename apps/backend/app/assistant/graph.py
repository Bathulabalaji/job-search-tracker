"""The LangGraph agent: guardrail -> (decline | agent <-> tools).

State holds only the *current* turn (the user's message, the model's tool calls and the tool
results). Earlier turns come from `Context`. Because LangGraph checkpoints after every node,
a run that fails on capacity can be resumed: the failed node runs again, completed tool calls
are not repeated.

Changes go through `interrupt()`: the tools node records a pending action, pauses the graph
and the user sees a card. A decision resumes the graph; the node runs again from the top,
finds the action in the ledger and executes (or skips) it. Everything before the interrupt in
that node must therefore be safe to repeat: reads are, and actions are looked up before they
are proposed.

Events for the client are written with `get_stream_writer()` and surface as
`stream_mode="custom"` items: token, tool_start, tool_end, confirmation_required,
model_switched, notice.
"""

import logging
import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    message_chunk_to_message,
)
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import interrupt
from pydantic import BaseModel, ValidationError

from app.assistant.actions import ActionStore, action_payload
from app.assistant.context import Context
from app.assistant.prompts import DECLINE_MESSAGE, GUARDRAIL_PROMPT
from app.assistant.tools import AssistantTool, ToolTimeout, compact, toolset_for
from app.assistant.write_tools import WriteTool
from app.core.errors import DomainError, NotFoundError
from app.llm.errors import LLMError
from app.llm.gateway import LLMGateway, RunBudget
from app.llm.policy import Task
from app.llm.providers.base import message_content_text
from app.models.chat_action import ChatPendingAction

logger = logging.getLogger("app.assistant")

MAX_TOOL_CALLS = 6
Intent = Literal[
    "today",
    "pipeline",
    "followups",
    "analytics",
    "contacts",
    "prep",
    "resumes",
    "write",
    "smalltalk",
    "other_in_scope",
    "out_of_scope",
]
SMALLTALK = {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "cool", "great", "bye"}
DECLINED_NOTE = (
    '{"declined":true,"note":"The user declined this change. Do not retry it; '
    'acknowledge in one line."}'
)


class GuardrailVerdict(BaseModel):
    in_scope: bool
    intent: Intent


class Cancelled(Exception):
    """The user pressed Stop (or the client went away)."""


class ChatState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    intent: str
    in_scope: bool
    tool_calls_made: int
    tool_log: Annotated[list[dict[str, Any]], operator.add]
    model: str
    prompt_tokens: Annotated[int, operator.add]
    completion_tokens: Annotated[int, operator.add]


@dataclass
class AgentDeps:
    gateway: LLMGateway
    tools: dict[str, AssistantTool]
    write_tools: dict[str, WriteTool]
    actions: ActionStore
    system_prompt: str
    context: Context
    run_id: str
    is_cancelled: Callable[[], bool]
    budget: RunBudget = field(init=False)

    def __post_init__(self) -> None:
        self.budget = self.gateway.new_budget()


def _quick_intent(text: str) -> GuardrailVerdict | None:
    cleaned = text.strip().lower().strip("!.? ")
    if cleaned in SMALLTALK:
        return GuardrailVerdict(in_scope=True, intent="smalltalk")
    return None


def build_graph(deps: AgentDeps) -> StateGraph[ChatState]:
    def check_cancel() -> None:
        if deps.is_cancelled():
            raise Cancelled()

    def guardrail(state: ChatState) -> dict[str, Any]:
        question = message_content_text(state["messages"][-1])
        verdict = _quick_intent(question)
        if verdict is None:
            prompt: list[BaseMessage] = [SystemMessage(content=GUARDRAIL_PROMPT)]
            prompt += deps.context.history[-2:]  # "and the next one?" needs the last exchange
            prompt.append(HumanMessage(content=question))
            try:
                result = deps.gateway.chat(
                    Task.guardrail,
                    prompt,
                    schema=GuardrailVerdict,
                    run_id=deps.run_id,
                    max_tokens=300,
                )
                verdict = result.parsed if isinstance(result.parsed, GuardrailVerdict) else None
            except LLMError as exc:
                # Degraded mode: let the agent's own instructions enforce the scope.
                logger.warning("assistant_guardrail_degraded", extra={"code": exc.code})
                get_stream_writer()({"event": "notice", "code": "guardrail_degraded"})
        if verdict is None:
            return {"in_scope": True, "intent": "other_in_scope"}
        in_scope = verdict.in_scope and verdict.intent != "out_of_scope"
        return {"in_scope": in_scope, "intent": verdict.intent}

    def decline(state: ChatState) -> dict[str, Any]:
        write = get_stream_writer()
        for word in DECLINE_MESSAGE.split(" "):
            write({"event": "token", "delta": word + " "})
        return {"messages": [AIMessage(content=DECLINE_MESSAGE)], "model": "none"}

    def agent(state: ChatState) -> dict[str, Any]:
        check_cancel()
        write = get_stream_writer()
        made = state.get("tool_calls_made", 0)
        names = toolset_for(state.get("intent")) if made < MAX_TOOL_CALLS else ()
        tools = [
            (
                deps.tools[n].as_langchain()
                if n in deps.tools
                else deps.write_tools[n].as_langchain()
            )
            for n in names
            if n in deps.tools or n in deps.write_tools
        ]
        prompt: list[BaseMessage] = [SystemMessage(content=deps.system_prompt)]
        prompt += deps.context.history
        prompt += state["messages"]
        before = deps.budget.switches
        result = deps.gateway.chat(
            Task.chat_agent,
            prompt,
            tools=tools or None,
            stream=True,
            budget=deps.budget,
            run_id=deps.run_id,
            max_tokens=900,
        )
        if deps.budget.switches > before or (state.get("model") and state["model"] != result.model):
            write({"event": "model_switched", "model": result.model})
        merged: AIMessageChunk | None = None
        for chunk in result.chunks or ():
            delta = message_content_text(chunk)
            if delta:
                write({"event": "token", "delta": delta})
            merged = chunk if merged is None else merged + chunk
            if deps.is_cancelled():
                raise Cancelled()
        message = message_chunk_to_message(merged) if merged is not None else AIMessage(content="")
        usage = result.usage
        return {
            "messages": [message],
            "model": result.model,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
        }

    def tools_node(state: ChatState) -> dict[str, Any]:
        check_cancel()
        write = get_stream_writer()
        last = state["messages"][-1]
        assert isinstance(last, AIMessage)
        made = state.get("tool_calls_made", 0)
        outputs: list[ToolMessage] = []
        log: list[dict[str, Any]] = []
        for call in last.tool_calls:
            call_id = call.get("id") or f"call_{made}"
            name = call["name"]
            args = call.get("args") or {}
            made += 1
            if name in deps.write_tools:
                entry, content = _handle_write(deps, call_id, name, args, write)
            else:
                write({"event": "tool_start", "id": call_id, "name": name})
                ok, summary, content = _run_tool(deps.tools.get(name), name, args, made)
                write(
                    {"event": "tool_end", "id": call_id, "name": name, "ok": ok, "summary": summary}
                )
                entry = {"name": name, "args": args, "ok": ok, "summary": summary}
            outputs.append(ToolMessage(content=content, tool_call_id=call_id, name=name))
            log.append(entry)
        return {"messages": outputs, "tool_calls_made": made, "tool_log": log}

    def after_guardrail(state: ChatState) -> str:
        return "agent" if state.get("in_scope", True) else "decline"

    def after_agent(state: ChatState) -> str:
        last = state["messages"][-1]
        return "tools" if isinstance(last, AIMessage) and last.tool_calls else END

    graph: StateGraph[ChatState] = StateGraph(ChatState)
    graph.add_node("guardrail", guardrail)
    graph.add_node("decline", decline)
    graph.add_node("agent", agent)
    graph.add_node("tools", tools_node)
    graph.add_edge(START, "guardrail")
    graph.add_conditional_edges("guardrail", after_guardrail, ["agent", "decline"])
    graph.add_edge("decline", END)
    graph.add_conditional_edges("agent", after_agent, ["tools", END])
    graph.add_edge("tools", "agent")
    return graph


def _run_tool(
    tool: AssistantTool | None, name: str, args: dict[str, Any], made: int
) -> tuple[bool, str, str]:
    """(ok, short summary for the UI, content for the model). Never raises."""
    if made > MAX_TOOL_CALLS:
        return (
            False,
            "tool limit reached",
            ('{"error":"Tool limit reached for this answer. Answer with what you have."}'),
        )
    if tool is None:
        return False, "unknown tool", f'{{"error":"There is no tool named {name}."}}'
    try:
        parsed = tool.args.model_validate(args)
        result = tool.run(parsed)
        return True, tool.summarize(result), compact(result)
    except ValidationError as exc:
        problems = "; ".join(e["msg"] for e in exc.errors()[:3])
        return False, "invalid arguments", compact({"error": f"Invalid arguments: {problems}"})
    except NotFoundError as exc:
        return False, "not found", compact({"error": str(exc)})
    except ToolTimeout:
        return (
            False,
            "timed out",
            ('{"error":"That lookup took too long. Try a narrower question or fewer rows."}'),
        )
    except DomainError as exc:
        return False, "failed", compact({"error": str(exc)})
    except Exception:
        logger.exception("assistant_tool_failed", extra={"tool": name})
        return False, "failed", '{"error":"That lookup failed. Tell the user it did not work."}'


def _handle_write(
    deps: AgentDeps,
    call_id: str,
    name: str,
    args: dict[str, Any],
    write: Callable[[dict[str, Any]], None],
) -> tuple[dict[str, Any], str]:
    """Propose a change, pause for the decision, then carry it out. Safe to re-run."""
    tool = deps.write_tools[name]
    action = deps.actions.get(call_id)
    if action is None:
        write({"event": "tool_start", "id": call_id, "name": name})
        try:
            parsed = tool.args.model_validate(args)
            preview = tool.preview(parsed)
        except ValidationError as exc:
            problems = "; ".join(e["msg"] for e in exc.errors()[:3])
            return _write_failed(
                write,
                call_id,
                name,
                args,
                "invalid arguments",
                compact({"error": f"Invalid arguments: {problems}"}),
            )
        except NotFoundError as exc:
            return _write_failed(
                write, call_id, name, args, "not found", compact({"error": str(exc)})
            )
        except DomainError as exc:
            return _write_failed(
                write, call_id, name, args, "not possible", compact({"error": str(exc)})
            )
        action = deps.actions.create(call_id, name, parsed.model_dump(mode="json"), preview)
        write({"event": "confirmation_required", **action_payload(action)})
    # Pauses here until the user decides. On resume the value is the action id; the decision
    # itself is read from the ledger so the checkpoint never carries client-supplied data.
    interrupt({"action_id": str(action.id)})
    refreshed = deps.actions.get(call_id)
    assert refreshed is not None
    action = refreshed
    if action.status == "confirmed":
        try:
            result = tool.execute(tool.args.model_validate(action.args))
            deps.actions.executed(action, result)
        except (ValidationError, DomainError) as exc:
            deps.actions.failed(action, str(exc))
        except Exception:
            logger.exception("assistant_action_failed", extra={"tool": name})
            deps.actions.failed(action, "The change failed unexpectedly.")
    return _write_outcome(write, call_id, name, action)


def _write_failed(
    write: Callable[[dict[str, Any]], None],
    call_id: str,
    name: str,
    args: dict[str, Any],
    summary: str,
    content: str,
) -> tuple[dict[str, Any], str]:
    write({"event": "tool_end", "id": call_id, "name": name, "ok": False, "summary": summary})
    return {"name": name, "args": args, "ok": False, "summary": summary}, content


def _write_outcome(
    write: Callable[[dict[str, Any]], None], call_id: str, name: str, action: ChatPendingAction
) -> tuple[dict[str, Any], str]:
    result = action.result or {}
    if action.status == "executed":
        ok, summary = True, str(result.get("summary", "done"))
        content = compact({"done": True, "summary": summary, **(result.get("data") or {})})
        changed = list(result.get("changed") or [])
    elif action.status == "failed":
        ok, summary, changed = False, "failed", []
        content = compact({"error": action.error or "The change failed."})
    elif action.status == "expired":
        ok, summary, changed = False, "expired", []
        content = '{"declined":true,"note":"The change expired before it was confirmed."}'
    else:  # rejected (or pending after a cancel)
        ok, summary, changed = False, "declined", []
        content = DECLINED_NOTE
    write(
        {
            "event": "tool_end",
            "id": call_id,
            "name": name,
            "ok": ok,
            "summary": summary,
            "changed": changed,
            "action_id": str(action.id),
        }
    )
    return {"name": name, "args": action.args, "ok": ok, "summary": summary}, content
