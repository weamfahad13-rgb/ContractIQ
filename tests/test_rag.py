import pytest

from contractiq.rag import cited_numbers, clean_select, confidence, normalize_ar, strip_supplier_names
from contractiq.search import Hit, rrf


def hit(chunk_id: int, score: float = 0.0) -> Hit:
    return Hit(chunk_id, 1, "t", "h", "x", 0, 1, score)


@pytest.mark.parametrize("variant, canonical", [
    ("الرياض للخدمات اللوجستيه", "الرياض للخدمات اللوجستية"),
    ("الشرق للادويه", "الشرق للأدوية"),
    ("مستشفى", "مستشفي"),
    ("إنهاء", "انهاء"),
    ("تَأْمِين", "تأمين"),
])
def test_arabic_spelling_variants_normalize_to_the_same_text(variant, canonical):
    assert normalize_ar(variant) == normalize_ar(canonical)


@pytest.mark.parametrize("question, expected", [
    ("What is the late delivery penalty for Al-Sharq Pharma?", "What is the late delivery penalty for ?"),
    ("ما غرامة التأخير في عقد نجد للتوزيع؟", "ما غرامة التأخير في عقد ؟"),
    ("ما غرامة عقد الرياض للخدمات اللوجستيه", "ما غرامة عقد"),
    ("Is there a cap on liability?", "Is there a cap on liability?"),
])
def test_supplier_names_are_stripped_from_the_search_text(question, expected):
    assert strip_supplier_names(question) == expected


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "select count(*) from purchase_orders;",
    "  WITH x AS (SELECT 1) SELECT * FROM x  ",
])
def test_single_selects_are_allowed(sql):
    assert clean_select(sql) is not None


@pytest.mark.parametrize("sql", [
    "DELETE FROM purchase_orders",
    "DROP TABLE contracts",
    "UPDATE suppliers SET name = 'x'",
    "SELECT 1; DROP TABLE contracts",
    "INSERT INTO suppliers VALUES (1)",
    "selectx from t",
    "",
])
def test_anything_else_is_rejected(sql):
    assert clean_select(sql) is None


@pytest.mark.parametrize("text, expected", [
    ("Penalty is 0.5% [1]. Cap is 10% [1].", {1}),
    ("See [1][3].", {1, 3}),
    ("See [2, 3].", {2, 3}),
    ("انظر [2، 4].", {2, 4}),
    ("No citations, 10% [of value].", set()),
])
def test_cited_numbers_reads_every_citation_style(text, expected):
    assert cited_numbers(text) == expected


def test_confidence_levels():
    assert confidence([]) == "low"
    assert confidence([hit(1, 0.9), hit(2, 0.8)]) == "high"
    assert confidence([hit(1, 0.12), hit(2, 0.01)]) == "high"  # stands out from the runner-up
    assert confidence([hit(1, 0.2), hit(2, 0.15)]) == "medium"
    assert confidence([hit(1, 0.05), hit(2, 0.04)]) == "low"


def test_arabic_questions_use_scaled_thresholds():
    # Arabic questions against English contracts score ~4x lower for the same quality.
    hits = [hit(1, 0.14), hit(2, 0.05)]
    assert confidence(hits) == "medium"
    assert confidence(hits, arabic=True) == "high"
    assert confidence([hit(1, 0.01), hit(2, 0.01)], arabic=True) == "low"


def test_rrf_rewards_chunks_ranked_well_in_both_lists():
    fused = rrf([hit(1), hit(2), hit(3)], [hit(3), hit(4), hit(1)])
    order = [h.chunk_id for h in fused]
    assert order[:2] == [1, 3] or order[:2] == [3, 1]
    assert set(order) == {1, 2, 3, 4}
    assert fused[0].score == pytest.approx(1 / 61 + 1 / 63)


def test_rrf_does_not_mutate_inputs():
    a = [hit(1, 0.5)]
    rrf(a, [hit(1, 0.7)])
    assert a[0].score == 0.5
