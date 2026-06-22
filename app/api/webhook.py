from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.messaging.base import OutgoingMessage
from app.messaging.factory import get_whatsapp_adapter
from app.parsing.factory import get_message_parser
from app.services.booking_actions import apply_action, find_active_booking
from app.templates.messages import de

router = APIRouter(prefix="/webhook", tags=["webhook"])


class InboundMessage(BaseModel):
    from_phone: str
    body: str


@router.post("/inbound")
async def receive_message(msg: InboundMessage, db: AsyncSession = Depends(get_db)) -> dict:
    """Receive an inbound WhatsApp message, parse it, and apply the action."""
    parser = get_message_parser()
    parsed = parser.parse(msg.body)

    booking = await find_active_booking(db, msg.from_phone)
    if not booking:
        adapter = get_whatsapp_adapter()
        await adapter.send_message(
            OutgoingMessage(to_phone=msg.from_phone, body=de.NO_ACTIVE_BOOKING)
        )
        return {"status": "no_booking", "intent": parsed.intent.value}

    adapter = get_whatsapp_adapter()
    reply = await apply_action(db, booking, parsed, adapter)
    return {"status": "processed", "intent": parsed.intent.value, "reply": reply}
