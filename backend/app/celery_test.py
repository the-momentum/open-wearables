from app.integrations.celery.tasks import sync_vendor_data

result = sync_vendor_data(
    user_id="3fa85f64-5717-4562-b3fc-2c963f66afa6",
    start_date="2024-01-01T00:00:00Z",
    end_date=None,
)
print(result)
