"""Brevo Transactional Email API adapter (free plan: 300 emails/day).

Calls `POST /v3/smtp/email`, the same endpoint the official `brevo-python` SDK
wraps. We use httpx directly because the SDK is synchronous (it would block
the event loop) and this keeps timeouts, retries and status tracking
identical across all three adapters.
"""

from pydantic import BaseModel

from app.integrations.base import HttpAdapter, IntegrationError, IntegrationName


class OutgoingEmail(BaseModel):
    to_email: str
    to_name: str | None = None
    subject: str
    html: str
    text: str
    tags: list[str] = []


class BrevoSendResponse(BaseModel):
    messageId: str


class BrevoAdapter(HttpAdapter):
    name = IntegrationName.BREVO

    @property
    def configured(self) -> bool:
        return bool(self.settings.brevo_api_key)

    def _client(self):  # type: ignore[no-untyped-def]
        return self.client(
            base_url=self.settings.brevo_base_url,
            headers={"api-key": self.settings.brevo_api_key or "", "accept": "application/json"},
        )

    async def send(self, email: OutgoingEmail) -> str:
        """Send one email; returns Brevo's message id."""
        if not self.configured:
            raise IntegrationError(self.name, "BREVO_API_KEY is not set")

        async def post() -> str:
            async with self._client() as client:
                res = await client.post(
                    "/smtp/email",
                    json={
                        "sender": {
                            "name": self.settings.brevo_sender_name,
                            "email": self.settings.brevo_sender_email,
                        },
                        "to": [
                            {
                                "email": email.to_email,
                                **({"name": email.to_name} if email.to_name else {}),
                            }
                        ],
                        "subject": email.subject,
                        "htmlContent": email.html,
                        "textContent": email.text,
                        "tags": email.tags,
                    },
                )
                res.raise_for_status()
                return BrevoSendResponse.model_validate(res.json()).messageId

        return await self.call("POST /smtp/email", post)

    async def ping(self) -> None:
        if not self.configured:
            raise IntegrationError(self.name, "BREVO_API_KEY is not set")

        async def get() -> None:
            async with self._client() as client:
                res = await client.get("/account")
                res.raise_for_status()

        await self.call("GET /account", get)
