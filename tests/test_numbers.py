from mt_engine.presentation import ascii_digits


def test_thai_digits_are_displayed_as_arabic():
    assert ascii_digits("วันที่ ๗/๑๑/๒๕๖๙ เวลา ๑๒:๓๐") == "วันที่ 7/11/2569 เวลา 12:30"


def test_latin_numbers_unchanged():
    assert ascii_digits("JOB-001 87.5%") == "JOB-001 87.5%"


def test_canonical_text_is_not_mutated():
    source = "เพลง ๑๒๓"
    displayed = ascii_digits(source)
    assert source == "เพลง ๑๒๓"
    assert displayed == "เพลง 123"
