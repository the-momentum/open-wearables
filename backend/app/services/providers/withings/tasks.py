"""Wire name of the per-user webhook registration task.

The task module imports ProviderFactory, so the strategy and notify service it
reaches cannot import the task back; both send it by name instead.
"""

REGISTER_USER_WEBHOOKS_TASK = "app.integrations.celery.tasks.register_provider_webhooks_task.register_user_webhooks"
