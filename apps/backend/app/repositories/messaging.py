import uuid
from datetime import datetime

from sqlalchemy import select

from app.models.messaging import MessageTemplate, OutreachMessage, OutreachProfile
from app.repositories.base import BaseRepository


class OutreachProfileRepository(BaseRepository[OutreachProfile]):
    model = OutreachProfile

    def mine(self) -> OutreachProfile | None:
        stmt = select(OutreachProfile).where(OutreachProfile.user_id == self.user_id)
        return self.session.scalars(stmt).first()


class MessageTemplateRepository(BaseRepository[MessageTemplate]):
    model = MessageTemplate

    def all(self) -> list[MessageTemplate]:
        stmt = (
            select(MessageTemplate)
            .where(MessageTemplate.user_id == self.user_id)
            .order_by(MessageTemplate.name, MessageTemplate.id)
        )
        return list(self.session.scalars(stmt))

    def override(self, base_key: str, channel: str) -> MessageTemplate | None:
        stmt = select(MessageTemplate).where(
            MessageTemplate.user_id == self.user_id,
            MessageTemplate.base_key == base_key,
            MessageTemplate.channel == channel,
        )
        return self.session.scalars(stmt).first()


class OutreachMessageRepository(BaseRepository[OutreachMessage]):
    model = OutreachMessage

    def for_opportunity(self, opportunity_id: int) -> list[OutreachMessage]:
        stmt = (
            select(OutreachMessage)
            .where(
                OutreachMessage.user_id == self.user_id,
                OutreachMessage.opportunity_id == opportunity_id,
            )
            .order_by(OutreachMessage.sent_at, OutreachMessage.id)
        )
        return list(self.session.scalars(stmt))

    def by_request(self, request_id: uuid.UUID) -> OutreachMessage | None:
        stmt = select(OutreachMessage).where(
            OutreachMessage.user_id == self.user_id, OutreachMessage.request_id == request_id
        )
        return self.session.scalars(stmt).first()

    def since(self, moment: datetime) -> list[OutreachMessage]:
        stmt = select(OutreachMessage).where(
            OutreachMessage.user_id == self.user_id, OutreachMessage.sent_at >= moment
        )
        return list(self.session.scalars(stmt))
