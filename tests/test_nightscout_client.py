import pytest

from nightscout_skills.utils.client import NightscoutClient
from nightscout_skills.utils.errors import NightscoutConfigError
from nightscout_skills.utils.time import parse_iso


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(self.payload)


def test_client_requires_config():
    with pytest.raises(NightscoutConfigError):
        NightscoutClient("", "token")
    with pytest.raises(NightscoutConfigError):
        NightscoutClient("https://example.test", "")


def test_fetch_sgvs_builds_expected_query_params():
    session = FakeSession([{"type": "sgv", "sgv": 100, "dateString": "2026-02-08T00:00:00+00:00"}])
    client = NightscoutClient("https://nightscout.example", "secret", timeout=7, session=session)

    entries = client.fetch_sgvs(
        parse_iso("2026-02-08T00:00:00+00:00"),
        parse_iso("2026-02-09T00:00:00+00:00"),
        count=5,
    )

    assert entries[0].sgv == 100
    assert session.calls[0]["url"] == "https://nightscout.example/api/v1/entries/sgv.json"
    assert session.calls[0]["params"]["token"] == "secret"
    assert session.calls[0]["params"]["count"] == "5"
    assert session.calls[0]["params"]["find[dateString][$gte]"] == "2026-02-08T00:00"
    assert session.calls[0]["params"]["find[dateString][$lt]"] == "2026-02-09T00:00"
