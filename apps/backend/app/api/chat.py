import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import StreamingResponse

from app.api.deps import ChatServiceDep, CheckpointerDep, TurnRunnerDep
from app.models.chat import ChatConversation
from app.schemas.chat import (
    ActionDecision,
    ActionRead,
    ChatConfig,
    ConversationCreate,
    ConversationDetail,
    ConversationRead,
    ConversationUpdate,
    RunRead,
    SendMessageRequest,
)

router = APIRouter(prefix="/chat", tags=["assistant"])

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",  # tell proxies not to buffer the stream
}


@router.get("/config", response_model=ChatConfig)
def chat_config(service: ChatServiceDep) -> ChatConfig:
    return service.config()


@router.get("/conversations", response_model=list[ConversationRead])
def list_conversations(
    service: ChatServiceDep,
    status_filter: Annotated[str | None, Query(alias="status")] = "active",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ChatConversation]:
    return service.list_conversations(status=status_filter, limit=limit, offset=offset)


@router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(data: ConversationCreate, service: ChatServiceDep) -> ChatConversation:
    return service.create(data)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: int,
    service: ChatServiceDep,
    before_seq: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ConversationDetail:
    return service.detail(conversation_id, before_seq=before_seq, limit=limit)


@router.patch("/conversations/{conversation_id}", response_model=ConversationRead)
def update_conversation(
    conversation_id: int, data: ConversationUpdate, service: ChatServiceDep
) -> ChatConversation:
    return service.update(conversation_id, data)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: int, service: ChatServiceDep, checkpointer: CheckpointerDep
) -> Response:
    for run_id in service.delete(conversation_id):
        checkpointer.delete_thread(str(run_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def send_message(
    conversation_id: int,
    data: SendMessageRequest,
    service: ChatServiceDep,
    runner: TurnRunnerDep,
) -> StreamingResponse:
    """Streams the answer as server-sent events: run_started, token, tool_start, tool_end,
    model_switched, notice, error, done."""
    run_id = service.start_turn(conversation_id, data)
    return StreamingResponse(
        runner.stream(run_id), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get("/conversations/{conversation_id}/runs/{run_id}", response_model=RunRead)
def get_run(conversation_id: int, run_id: uuid.UUID, service: ChatServiceDep) -> RunRead:
    return service.get_run(conversation_id, run_id)


@router.post(
    "/conversations/{conversation_id}/runs/{run_id}/resume",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def resume_run(
    conversation_id: int, run_id: uuid.UUID, service: ChatServiceDep, runner: TurnRunnerDep
) -> StreamingResponse:
    """Continue a reply that failed on capacity, from its last completed step."""
    service.prepare_resume(conversation_id, run_id)
    return StreamingResponse(
        runner.stream(run_id, resume=True), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.get("/conversations/{conversation_id}/actions/{action_id}", response_model=ActionRead)
def get_action(conversation_id: int, action_id: uuid.UUID, service: ChatServiceDep) -> ActionRead:
    return service.get_action(conversation_id, action_id)


@router.post(
    "/conversations/{conversation_id}/actions/{action_id}",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
def decide_action(
    conversation_id: int,
    action_id: uuid.UUID,
    data: ActionDecision,
    service: ChatServiceDep,
    runner: TurnRunnerDep,
) -> StreamingResponse:
    """Confirm (optionally with edits) or reject a proposed change; the reply then continues
    as server-sent events (tool_end, token..., done)."""
    run_id = service.decide(conversation_id, action_id, data)
    return StreamingResponse(
        runner.stream(run_id, resume_value={"action_id": str(action_id)}),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post(
    "/conversations/{conversation_id}/runs/{run_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_run(conversation_id: int, run_id: uuid.UUID, service: ChatServiceDep) -> Response:
    service.cancel(conversation_id, run_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
