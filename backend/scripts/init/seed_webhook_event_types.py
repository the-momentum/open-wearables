#!/usr/bin/env python3
"""Register all webhook event types with the Svix server (idempotent)."""

from app.services.outgoing_webhooks import svix as svix_service


def seed_webhook_event_types() -> None:
    svix_service.register_event_types()
    print("✓ Webhook event types registered with Svix.")


if __name__ == "__main__":
    seed_webhook_event_types()
