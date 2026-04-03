import json
from pathlib import Path

LANGUAGES = [
    "am", "ar", "de", "en", "es", "fa", "fr", "ha", "hi", "it",
    "ja", "ko", "nl", "pl", "pt", "ru", "sv", "sw", "th", "tr",
    "vi", "yo", "zh",
]

def _load():
    path = Path(__file__).resolve().parents[1] / "po" / "language-names.json"
    with open(path) as f:
        return json.load(f)


def test_all_languages_present():
    data = _load()
    assert set(data.keys()) == set(LANGUAGES)


def test_each_language_has_all_translations():
    data = _load()
    for lang_code, names in data.items():
        for target in LANGUAGES:
            assert target in names, f"{lang_code} missing translation for {target}"
            assert isinstance(names[target], str)
            assert len(names[target]) > 0, f"{lang_code}[{target}] is empty"


def test_native_names_are_correct():
    """Spot-check that each language's self-name matches known values."""
    data = _load()
    expected_native = {
        "am": "አማርኛ",
        "ar": "العربية",
        "de": "Deutsch",
        "en": "English",
        "es": "Español",
        "fa": "فارسی",
        "fr": "Français",
        "ha": "Hausa",
        "hi": "हिन्दी",
        "it": "Italiano",
        "ja": "日本語",
        "ko": "한국어",
        "nl": "Nederlands",
        "pl": "Polski",
        "pt": "Português",
        "ru": "Русский",
        "sv": "Svenska",
        "sw": "Kiswahili",
        "th": "ไทย",
        "tr": "Türkçe",
        "vi": "Tiếng Việt",
        "yo": "Yorùbá",
        "zh": "中文",
    }
    for code, native in expected_native.items():
        assert data[code][code] == native, (
            f"{code} native name: expected {native!r}, got {data[code][code]!r}"
        )


def test_matrix_is_complete():
    """23 languages × 23 translations = 529 entries."""
    data = _load()
    total = sum(len(v) for v in data.values())
    assert total == 23 * 23
