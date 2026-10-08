"""HTTP adapter for the notification-service SMS and email endpoints."""

from collections.abc import Mapping

import httpx


class NotificationClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def send_sms(self, recipient: str, template: str, values: Mapping[str, str]) -> None:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=3.0) as client:
            response = await client.post("/notify/sms", json={
                "recipient": recipient,
                "template": template,
                "values": dict(values),
            })
            response.raise_for_status()

    async def send_email(self, recipient: str, template: str, values: Mapping[str, str]) -> None:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=3.0) as client:
            response = await client.post("/notify/email", json={
                "recipient": recipient,
                "template": template,
                "values": dict(values),
            })
            response.raise_for_status()

    async def login_alert(self, email: str, occurred_at: str) -> None:
        await self.send_email(email, "login_alert", {"occurred_at": occurred_at})
