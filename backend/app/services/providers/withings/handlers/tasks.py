"""Wire name of the per-connection Notify sync task.

The task module imports ProviderFactory, so the strategy and notify service it
reaches cannot import the task back; both send it by name instead.
"""

SYNC_USER_SUBSCRIPTIONS_TASK = "app.integrations.celery.tasks.withings.notify_sync_task.sync_user_subscriptions"
