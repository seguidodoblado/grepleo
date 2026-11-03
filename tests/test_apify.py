import io
import json
import urllib.error

import pytest

from grepleo.sources.apify import ApifyError, account_info, run_actor


class FakeResponse:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self._body


def test_run_actor_posts_the_input_with_a_spend_cap_in_the_url():
    seen = {}

    def opener(request, timeout):
        seen.update(url=request.full_url, method=request.get_method(), auth=request.get_header("Authorization"),
                    body=json.loads(request.data), timeout=timeout)
        return FakeResponse([{"title": "PO"}, "basura", {"title": "Dev"}])

    items = run_actor("TOKEN", "valig/indeed-jobs-scraper", {"title": "po"}, 0.25, opener)
    assert items == [{"title": "PO"}, {"title": "Dev"}]
    assert seen["method"] == "POST" and seen["auth"] == "Bearer TOKEN" and seen["body"] == {"title": "po"}
    assert "/acts/valig~indeed-jobs-scraper/run-sync-get-dataset-items?" in seen["url"]
    assert "maxTotalChargeUsd=0.2500" in seen["url"] and "TOKEN" not in seen["url"]
    assert seen["timeout"] > 300


@pytest.mark.parametrize("status, text", [(401, "token"), (402, "crédito"), (404, "Actor"), (408, "tardó"),
                                          (429, "limita"), (500, "500")])
def test_http_errors_become_readable_messages(status, text):
    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, status, "x", {}, io.BytesIO(
            json.dumps({"error": {"message": "detalle"}}).encode()))

    with pytest.raises(ApifyError) as info:
        run_actor("T", "a/b", {}, 1.0, opener)
    assert text in str(info.value) and info.value.status == status
    assert "detalle" in str(info.value)


def test_network_and_format_errors():
    def offline(request, timeout):
        raise urllib.error.URLError("sin red")

    with pytest.raises(ApifyError, match="sin red"):
        run_actor("T", "a/b", {}, 1.0, offline)
    with pytest.raises(ApifyError, match="no se entiende"):
        run_actor("T", "a/b", {}, 1.0, lambda request, timeout: FakeResponse({"no": "lista"}))

    class Broken(FakeResponse):
        def read(self):
            return b"<html>"

    with pytest.raises(ApifyError, match="no se entiende"):
        run_actor("T", "a/b", {}, 1.0, lambda request, timeout: Broken([]))


def test_account_info_reads_the_user_and_plan():
    info = account_info("T", lambda request, timeout: FakeResponse({"data": {"username": "jose", "plan": {"id": "FREE"}}}))
    assert info == {"username": "jose", "plan": "FREE"}
