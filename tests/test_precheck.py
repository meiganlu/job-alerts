from jobalerts.precheck import obvious_years_required


def test_plain_requirement_is_caught():
    found = obvious_years_required("Requirements\n- 5+ years of professional software experience")
    assert found[0] == 5


def test_ambiguous_wording_is_left_to_the_llm():
    assert obvious_years_required("- 2-5 years of experience") is None               # starts at 2
    assert obvious_years_required("- 5+ years of experience preferred") is None       # preferred
    assert obvious_years_required("- 3 years of coursework in CS") is None            # not experience
    assert obvious_years_required(
        "- BS and 3 years of experience, or MS and 1 year of experience") is None     # 1-year option


def test_preferred_section_is_skipped():
    text = "Minimum Qualifications\n- BS in CS\nPreferred Qualifications\n- 5+ years of experience"
    assert obvious_years_required(text) is None


def test_minimum_wording_counts_inside_soft_section():
    text = "Ideal Candidate\n- Minimum 5 years of experience"
    assert obvious_years_required(text)[0] == 5


def test_number_words_and_parentheses():
    assert obvious_years_required("- five (5) years of experience")[0] == 5
    assert obvious_years_required("- three-plus years of experience")[0] == 3