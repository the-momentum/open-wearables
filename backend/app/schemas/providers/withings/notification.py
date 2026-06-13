from pydantic import BaseModel


class WithingsNotification(BaseModel):
    """Inbound Withings notify payload (form-urlencoded, notify-only).

    Data applis (1, 4, 16, 44) carry a ``startdate``/``enddate`` range; the
    profile-change appli (46) instead carries an ``action`` and no date range,
    so the dates are optional here and enforced per-domain in the handler.
    """

    userid: str
    appli: int
    startdate: int | None = None
    enddate: int | None = None
    action: str | None = None
