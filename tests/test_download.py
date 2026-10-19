import json
from types import SimpleNamespace

import pytest
import requests

from conftest import load_script

download = load_script("01_download_counts.py")


def fake_response(status_code, body=None):
    """A stand-in for a requests response."""
    return SimpleNamespace(status_code=status_code, json=lambda: body, text=json.dumps(body))


def test_dental_filter_uses_specialty_field():
    assert download.DENTAL_FILTER == 'device.openfda.medical_specialty_description.exact:"Dental"'
    assert 'NOT device.device_report_product_code.exact:"DZE"' in download.NOT_IMPLANT_FILTER


def test_no_matches_is_an_empty_result_not_an_error(monkeypatch):
    body = {"error": {"code": "NOT_FOUND", "message": "No matches found!"}}
    monkeypatch.setattr(download.requests, "get", lambda url, params, timeout: fake_response(404, body))
    assert download.get_openfda({"search": "x"}, wait_seconds=0) == {"meta": {}, "results": []}


def test_rate_limit_is_retried(monkeypatch):
    replies = [fake_response(429), fake_response(200, {"results": [{"term": "Injury", "count": 1}]})]
    monkeypatch.setattr(download.requests, "get", lambda url, params, timeout: replies.pop(0))
    assert download.get_openfda({"search": "x"}, wait_seconds=0)["results"][0]["count"] == 1


def test_bad_query_stops_immediately(monkeypatch):
    calls = []

    def fake_get(url, params, timeout):
        calls.append(1)
        return fake_response(400, {"error": "bad"})

    monkeypatch.setattr(download.requests, "get", fake_get)
    with pytest.raises(RuntimeError, match="HTTP 400"):
        download.get_openfda({"search": "x"}, wait_seconds=0)
    assert len(calls) == 1


def test_network_failure_gives_clear_error(monkeypatch):
    def fake_get(url, params, timeout):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(download.requests, "get", fake_get)
    with pytest.raises(RuntimeError, match="after 3 attempts.*timed out"):
        download.get_openfda({"search": "x"}, wait_seconds=0)


def test_api_key_is_added_when_set(monkeypatch):
    seen = {}

    def fake_get(url, params, timeout):
        seen.update(params)
        return fake_response(200, {"results": []})

    monkeypatch.setenv("OPENFDA_API_KEY", "abc")
    monkeypatch.setattr(download.requests, "get", fake_get)
    download.get_openfda({"search": "x"}, wait_seconds=0)
    assert seen["api_key"] == "abc"


def test_save_result_for_total_keeps_only_meta(tmp_path):
    body = {"meta": {"results": {"total": 5}}, "results": [{"report_number": "123"}]}
    path = download.save_result("total", {"search": "x", "limit": 1}, body, tmp_path)
    payload = json.loads(path.read_text())
    assert payload["results"] == []
    assert download.total_reports(payload["meta"]) == 5


def test_save_result_for_counts_keeps_rows(tmp_path):
    body = {"meta": {}, "results": [{"term": "Injury", "count": 3}]}
    path = download.save_result("event_types", {"search": "x", "count": "event_type.exact"}, body, tmp_path)
    assert json.loads(path.read_text())["results"] == [{"term": "Injury", "count": 3}]


def test_main_stops_when_no_dental_reports(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(download, "RAW_DIR", tmp_path)
    monkeypatch.setattr(download, "get_openfda", lambda params: {"meta": {}, "results": []})
    with pytest.raises(SystemExit):
        download.main()
    assert "found no dental device reports" in capsys.readouterr().out
