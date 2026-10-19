import pandas as pd
import pytest

from conftest import load_script

charts = load_script("03_make_charts.py")


def test_shorten_long_labels():
    assert charts.shorten("a" * 60, 20) == "a" * 17 + "..."
    assert charts.shorten("short") == "short"


def test_device_chart_saves_file_without_implant_row(tmp_path):
    df = pd.DataFrame({
        "device_type": ["Implant, Endosseous, Root-Form", "Scaler, Ultrasonic"],
        "reports": [90, 6],
        "pct_of_dental_reports": [90.0, 6.0],
    })
    path = tmp_path / "devices.png"
    charts.chart_device_types(df, path)
    assert path.exists() and path.stat().st_size > 1000


def test_log_scale_chart(tmp_path):
    path = tmp_path / "events.png"
    charts.horizontal_bar_chart(["Injury", "Death"], [1000000, 3], "t", "x", path, log_scale=True)
    assert path.exists()


def test_main_exits_when_tables_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(charts, "TABLES_DIR", tmp_path)
    with pytest.raises(SystemExit):
        charts.main()
    assert "run  python src/02_build_tables.py  first" in capsys.readouterr().out
