import core

def test_roi_math():
    r = core.roi(10, 400, 0.5, 0.5, 10, 20, 0.5, 100)
    assert round(r["jobs_recovered"], 2) == round(10 * 4.33 * 0.25, 2)
    assert r["net"] == r["gain"] - 100

def test_roi_zero_cost():
    assert core.roi(1, 1, 1, 1, 0, 0, 0, 0)["roi_pct"] is None

def test_score_bounds():
    low = core.score_assessment({q["key"]: 1 for q in core.QUESTIONS})
    high = core.score_assessment({q["key"]: 4 for q in core.QUESTIONS})
    assert low[0] == 25 and low[2]
    assert high[0] == 100 and high[2] == []

def test_validation():
    assert core.validate_lead({"name": "", "phone": "123"})
    assert not core.validate_lead({"name": "Sam", "phone": "(555) 123-4567", "email": "a@b.com"})

def test_save_and_load(tmp_path):
    p = tmp_path / "l.csv"
    core.save_lead({"name": "Sam", "phone": "5551234567"}, path=p)
    assert core.load_leads(path=p)[0]["name"] == "Sam"

def test_prompt_templates_fill():
    for t in core.TEMPLATES:
        assert "{" not in core.build_prompt(t, "Acme HVAC", "A/C tune-up", "Spring", "Friendly")
