#!/usr/bin/env python3
"""Register all webhook event types with the Svix server (idempotent)."""

import logging

from app.services.outgoing_webhooks import svix as svix_service

logger = logging.getLogger(__name__)


def seed_webhook_event_types() -> None:
    if not svix_service.is_enabled():
        logger.info("Outgoing webhooks disabled — skipping webhook event type registration.")
        return
    if svix_service.register_event_types():
        logger.info("Webhook event types registered with Svix.")
    else:
        logger.warning("Webhook event type registration did not complete — will retry on next startup.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s - %(name)s] (%(levelname)s) %(message)s")
    seed_webhook_event_types()
