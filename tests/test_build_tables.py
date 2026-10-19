import pytest

from conftest import load_script

build = load_script("02_build_tables.py")


def test_daily_to_yearly_adds_up_days():
    results = [{"time": "20250103", "count": 30}, {"time": "20251220", "count": 20}, {"time": "20260105", "count": 50}]
    table = build.daily_to_yearly(results).set_index("year")
    assert table.at[2025, "reports"] == 50
    assert table.at[2026, "reports"] == 50


def test_daily_to_yearly_empty():
    assert build.daily_to_yearly([]).empty


def test_yearly_table(fixtures_dir):
    all_days = build.load_raw(fixtures_dir, "by_day")["results"]
    other_days = build.load_raw(fixtures_dir, "by_day_without_implants")["results"]
    table = build.yearly_table(all_days, other_days, 2026).set_index("year")
    assert table.at[2025, "implant_reports"] == 45
    assert table.at[2026, "is_partial_year"] == 1
    assert table.at[2025, "is_partial_year"] == 0


def test_yearly_table_fills_years_with_no_other_reports():
    table = build.yearly_table([{"time": "20240101", "count": 7}], [], 2026)
    assert table.at[0, "reports_without_implants"] == 0
    assert table.at[0, "implant_reports"] == 7


def test_counts_table_labels_blank_and_percent(fixtures_dir):
    results = build.load_raw(fixtures_dir, "event_types")["results"]
    table = build.counts_table(results, "event_type", 100).set_index("event_type")
    assert "Not recorded" in table.index
    assert table.at["Injury", "pct_of_dental_reports"] == 85.0


def test_counts_table_top_n():
    results = [{"term": "a", "count": 1}, {"term": "b", "count": 5}, {"term": "c", "count": 3}]
    table = build.counts_table(results, "label", 9, top_n=2)
    assert table["label"].tolist() == ["b", "c"]


def test_counts_table_empty_results():
    table = build.counts_table([], "label", 100)
    assert table.empty and "pct_of_dental_reports" in table.columns


def test_regulation_check(fixtures_dir):
    results = build.load_raw(fixtures_dir, "regulation_numbers")["results"]
    row = build.regulation_check(results).iloc[0]
    assert row["device_rows_in_part_872"] == 99
    assert row["device_rows_outside_part_872"] == 1
    assert row["pct_in_part_872"] == 99.0


def test_total_reports(fixtures_dir):
    assert build.total_reports(build.load_raw(fixtures_dir, "total")) == 100


def test_main_writes_tables_and_summary(fixtures_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(build, "RAW_DIR", fixtures_dir)
    monkeypatch.setattr(build, "TABLES_DIR", tmp_path / "tables")
    monkeypatch.setattr(build, "SUMMARY_PATH", tmp_path / "summary.md")
    build.main()
    text = (tmp_path / "summary.md").read_text()
    assert "openFDA holds 100 adverse event reports" in text
    assert "not how often devices fail" in text
    assert (tmp_path / "tables" / "reports_per_year.csv").exists()


def test_main_exits_when_downloads_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(build, "RAW_DIR", tmp_path)
    with pytest.raises(SystemExit):
        build.main()
    assert "run  python src/01_download_counts.py  first" in capsys.readouterr().out
