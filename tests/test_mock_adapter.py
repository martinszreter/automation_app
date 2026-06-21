import pytest

from app.messaging.base import OutgoingMessage
from app.messaging.mock_adapter import MockWhatsAppAdapter


@pytest.mark.asyncio
async def test_mock_send_message():
    adapter = MockWhatsAppAdapter()
    msg = OutgoingMessage(to_phone="+491234567890", body="Hallo!")
    result = await adapter.send_message(msg)

    assert result["status"] == "mock_sent"
    assert len(adapter.sent) == 1
    assert adapter.sent[0].body == "Hallo!"


@pytest.mark.asyncio
async def test_mock_verify_webhook():
    adapter = MockWhatsAppAdapter()
    challenge = await adapter.verify_webhook("token123", "challenge456")
    assert challenge == "challenge456"
