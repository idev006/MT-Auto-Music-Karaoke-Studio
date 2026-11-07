"""Normalize displayed numerals without changing canonical source text."""

import unicodedata


def ascii_digits(value: object) -> str:
    """Return a display string using ASCII decimal numerals where possible."""
    result = []
    for char in str(value):
        if char.isdecimal():
            digit = unicodedata.decimal(char)
            result.append(str(digit))
        else:
            result.append(char)
    return "".join(result)
