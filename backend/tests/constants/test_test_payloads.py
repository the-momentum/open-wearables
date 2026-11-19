from app.constants.webhooks.test_payloads import EXAMPLE_PAYLOADS, get_test_payload


def test_a_core_event_type_gets_its_example_payload() -> None:
    event_type, example = next(iter(EXAMPLE_PAYLOADS.items()))

    assert get_test_payload(event_type) == example


def test_an_event_type_without_an_example_gets_a_minimal_payload() -> None:
    assert get_test_payload("my_extension.thing.created") == {"type": "my_extension.thing.created", "data": {}}
