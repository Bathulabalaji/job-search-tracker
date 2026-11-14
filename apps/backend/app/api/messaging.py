"""Outreach: templates, the sender's profile, drafts for an opportunity, and what was sent."""

from fastapi import APIRouter, Response, status

from app.api.deps import MessagingServiceDep
from app.schemas.messaging import (
    MarkSentRequest,
    OutreachMessageRead,
    OutreachProfileRead,
    OutreachProfileUpdate,
    PolishRead,
    PolishRequest,
    PreviewRead,
    PreviewRequest,
    SentListItem,
    SentRead,
    StatsRead,
    SuggestionsRead,
    TemplateCreate,
    TemplateRead,
    TemplateUpdate,
)

router = APIRouter(tags=["messages"])


@router.get("/messages/templates", response_model=list[TemplateRead])
def list_templates(service: MessagingServiceDep) -> list[TemplateRead]:
    return service.list_templates()


@router.post(
    "/messages/templates", response_model=TemplateRead, status_code=status.HTTP_201_CREATED
)
def create_template(data: TemplateCreate, service: MessagingServiceDep) -> TemplateRead:
    return service.create_template(data)


@router.patch("/messages/templates/{template_id}", response_model=TemplateRead)
def update_template(
    template_id: int, data: TemplateUpdate, service: MessagingServiceDep
) -> TemplateRead:
    return service.update_template(template_id, data)


@router.delete("/messages/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: int, service: MessagingServiceDep) -> Response:
    service.delete_template(template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/messages/profile", response_model=OutreachProfileRead)
def get_profile(service: MessagingServiceDep) -> OutreachProfileRead:
    return service.get_profile()


@router.put("/messages/profile", response_model=OutreachProfileRead)
def update_profile(
    data: OutreachProfileUpdate, service: MessagingServiceDep
) -> OutreachProfileRead:
    return service.update_profile(data)


@router.get("/messages/stats", response_model=StatsRead)
def get_stats(service: MessagingServiceDep) -> StatsRead:
    return service.stats()


@router.post("/messages/{message_id}/replied", response_model=OutreachMessageRead)
def mark_replied(message_id: int, service: MessagingServiceDep) -> OutreachMessageRead:
    return service.mark_replied(message_id)


@router.get("/opportunities/{opportunity_id}/messages", response_model=list[SentListItem])
def list_sent(opportunity_id: int, service: MessagingServiceDep) -> list[SentListItem]:
    return service.sent_for(opportunity_id)


@router.get("/opportunities/{opportunity_id}/messages/suggestions", response_model=SuggestionsRead)
def suggestions(opportunity_id: int, service: MessagingServiceDep) -> SuggestionsRead:
    return service.suggestions(opportunity_id)


@router.post("/opportunities/{opportunity_id}/messages/preview", response_model=PreviewRead)
def preview(opportunity_id: int, data: PreviewRequest, service: MessagingServiceDep) -> PreviewRead:
    return service.preview(opportunity_id, data)


@router.post("/opportunities/{opportunity_id}/messages/polish", response_model=PolishRead)
def polish(opportunity_id: int, data: PolishRequest, service: MessagingServiceDep) -> PolishRead:
    return service.polish(opportunity_id, data)


@router.post(
    "/opportunities/{opportunity_id}/messages/sent",
    response_model=SentRead,
    status_code=status.HTTP_201_CREATED,
)
def mark_sent(opportunity_id: int, data: MarkSentRequest, service: MessagingServiceDep) -> SentRead:
    return service.mark_sent(opportunity_id, data)
