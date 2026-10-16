import httpx
import pytest

from rental_lookup.sources.http import get_json


def _client(statuses: list[int]) -> tuple[httpx.Client, list]:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        status = statuses[min(len(calls), len(statuses)) - 1]
        return httpx.Response(status, json={"page": len(calls)})

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_get_json_retries_transient_errors():
    client, calls = _client([503, 429, 200])
    assert get_json(client, "https://example.test", {}, backoff=0) == {"page": 3}
    assert len(calls) == 3


def test_get_json_raises_after_last_attempt():
    client, calls = _client([500])
    with pytest.raises(httpx.HTTPStatusError):
        get_json(client, "https://example.test", {}, attempts=2, backoff=0)
    assert len(calls) == 2
