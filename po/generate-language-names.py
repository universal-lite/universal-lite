#!/usr/bin/env python3
"""Generate po/language-names.json from Unicode CLDR data.

Downloads CLDR JSON locale data for each of our 23 supported languages
and extracts the language display names into a 23×23 matrix.

Usage:
    python po/generate-language-names.py
"""

import json
import sys
import urllib.request
from pathlib import Path

CLDR_BASE = (
    "https://raw.githubusercontent.com/unicode-cldr/"
    "cldr-localenames-full/master/main/{locale}/languages.json"
)

LANGUAGES = [
    "am", "ar", "de", "en", "es", "fa", "fr", "ha", "hi", "it",
    "ja", "ko", "nl", "pl", "pt", "ru", "sv", "sw", "th", "tr",
    "vi", "yo", "zh",
]

NATIVE_NAMES = {
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


def fetch_cldr_languages(locale: str) -> dict[str, str]:
    """Fetch CLDR language display names for a given locale."""
    url = CLDR_BASE.format(locale=locale)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
    except Exception as exc:
        print(f"  WARNING: failed to fetch {locale}: {exc}", file=sys.stderr)
        return {}

    locale_data = data.get("main", {}).get(locale, {})
    names = locale_data.get("localeDisplayNames", {}).get("languages", {})
    return names


def build_matrix() -> dict[str, dict[str, str]]:
    """Build the 23×23 language name matrix."""
    matrix: dict[str, dict[str, str]] = {}

    for source_lang in LANGUAGES:
        print(f"Fetching CLDR data for: {source_lang}")
        cldr_names = fetch_cldr_languages(source_lang)

        translations = {}
        for target_lang in LANGUAGES:
            # For native names (self-reference), always use our curated
            # NATIVE_NAMES which have conventional UI capitalization
            # (CLDR often lowercases language self-names).
            if source_lang == target_lang:
                translations[target_lang] = NATIVE_NAMES[target_lang]
                continue

            name = cldr_names.get(target_lang, "")
            if not name:
                name = NATIVE_NAMES.get(target_lang, target_lang)
                print(
                    f"  Using fallback for {source_lang}->{target_lang}: {name}",
                    file=sys.stderr,
                )
            translations[target_lang] = name

        matrix[source_lang] = translations

    return matrix


def main() -> None:
    matrix = build_matrix()

    missing = []
    for src in LANGUAGES:
        for tgt in LANGUAGES:
            if not matrix.get(src, {}).get(tgt):
                missing.append(f"{src}->{tgt}")
    if missing:
        print(f"WARNING: {len(missing)} missing entries: {missing}", file=sys.stderr)

    out_path = Path(__file__).resolve().parent / "language-names.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(matrix, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"Wrote {out_path} ({sum(len(v) for v in matrix.values())} entries)")


if __name__ == "__main__":
    main()
