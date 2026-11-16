from jobalerts.companies import company_id, normalize_slug


def test_greenhouse_and_ashby_ignore_case():
    assert company_id("greenhouse", "Affirm") == "greenhouse:affirm"
    assert normalize_slug("ashby", " Ramp ") == "ramp"


def test_lever_keeps_case():
    assert normalize_slug("lever", "Palantir") == "Palantir"