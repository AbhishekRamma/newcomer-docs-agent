from src.textnorm import fact_present, normalize, numbers_in


def test_normalize_folds_punctuation_and_thousands():
    assert normalize("You’ll pay $1,358.00 — now!") == "youll pay 1358 00 now"


def test_fact_alternatives_and_number_boundaries():
    text = normalize("The fee is $40 and the wait is 12 months.")
    assert fact_present("40", text, normalized=True)
    assert not fact_present("4", text, normalized=True)
    assert fact_present("one year|12 months", text, normalized=True)
    assert not fact_present("8 months|eight months", text, normalized=True)


def test_numbers_in_canonicalises():
    assert numbers_in("$1,358.00 on April 30, 2027 or 0.50") == {"1358", "30", "2027", "0.5"}
