import logging

from app.utils.log_filters import UvicornAccess2xxFilter


def _make_record(args: tuple | None) -> logging.LogRecord:
    record = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=args,
        exc_info=None,
    )
    return record


def test_drops_200() -> None:
    f = UvicornAccess2xxFilter()
    assert f.filter(_make_record(("169.254.169.126:48108", "GET", "/api/v1/x", "1.1", 200))) is False


def test_drops_204() -> None:
    f = UvicornAccess2xxFilter()
    assert f.filter(_make_record(("169.254.169.126:48108", "GET", "/api/v1/x", "1.1", 204))) is False


def test_keeps_400() -> None:
    f = UvicornAccess2xxFilter()
    assert f.filter(_make_record(("169.254.169.126:48108", "GET", "/api/v1/x", "1.1", 400))) is True


def test_keeps_500() -> None:
    f = UvicornAccess2xxFilter()
    assert f.filter(_make_record(("169.254.169.126:48108", "POST", "/api/v1/x", "1.1", 500))) is True


def test_keeps_record_with_unexpected_args_shape() -> None:
    f = UvicornAccess2xxFilter()
    assert f.filter(_make_record(None)) is True
    assert f.filter(_make_record(("only", "three", "args"))) is True
    assert f.filter(_make_record(("a", "b", "c", "d", "not-int"))) is True
