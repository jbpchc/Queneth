"""One adapter per external API (psgc.py, cloudinary_client.py, brevo_email.py).

Each adapter: 5s timeout, 2 retries with backoff, structured logging, typed
Pydantic responses, a mock mode (INTEGRATIONS_MODE=mock) and an offline fallback.
"""
