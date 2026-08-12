from pathlib import Path


def test_privacy_tests_declare_synthetic_data_and_no_production_domains():
    root = Path(__file__).resolve().parents[2]
    content = (root / "tests/comunicaciones/test_privacy_pipeline.py").read_text(encoding="utf-8")
    assert "SYNTHETIC_CHAT" in content
    assert "example.test" in content
    for forbidden in ("gmail.com", "hotmail.com", "yahoo.com", "outlook.com"):
        assert forbidden not in content.casefold()
