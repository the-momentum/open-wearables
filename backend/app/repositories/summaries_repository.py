from app.models.summaries import (
    DailyActivitySummary,
    DailyBodySummary,
    DailyRecoverySummary,
)
from app.repositories.repositories import CrudRepository
from app.schemas.taxonomy_summaries import (
    ActivitySummary,
    BodySummary,
    RecoverySummary,
)


class DailyActivitySummaryRepository(CrudRepository[DailyActivitySummary, ActivitySummary, ActivitySummary]):
    def __init__(self):
        super().__init__(DailyActivitySummary)


class DailyBodySummaryRepository(CrudRepository[DailyBodySummary, BodySummary, BodySummary]):
    def __init__(self):
        super().__init__(DailyBodySummary)


class DailyRecoverySummaryRepository(CrudRepository[DailyRecoverySummary, RecoverySummary, RecoverySummary]):
    def __init__(self):
        super().__init__(DailyRecoverySummary)
