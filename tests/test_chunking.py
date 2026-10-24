from contractiq.chunking import MAX_CHARS, chunk_contract, clean
from contractiq.synthetic import SUPPLIERS, contract_ar, contract_en

SAMPLE_EN = contract_en(SUPPLIERS[0])
SAMPLE_AR = contract_ar(SUPPLIERS[1])


def test_chunk_offsets_point_back_to_the_original_text():
    for text in (SAMPLE_EN, SAMPLE_AR):
        for c in chunk_contract(text):
            assert clean(text[c.start:c.end]) == c.text


def test_chunks_are_contiguous_and_cover_the_contract():
    for text in (SAMPLE_EN, SAMPLE_AR):
        chunks = chunk_contract(text)
        assert chunks[0].start == 0
        assert chunks[-1].end == len(text)
        for a, b in zip(chunks, chunks[1:]):
            assert a.end == b.start


def test_splits_on_top_level_clauses_in_english():
    headings = [c.heading for c in chunk_contract(SAMPLE_EN)]
    assert "9. DELIVERY AND PERFORMANCE" in headings
    # Short neighbouring clauses are merged, and the label names every clause in the chunk.
    assert any("3. TERM" in h and "4. RENEWAL" in h for h in headings)


def test_splits_on_top_level_clauses_in_arabic():
    headings = [c.heading for c in chunk_contract(SAMPLE_AR)]
    assert "9. التسليم والأداء" in headings


def test_penalty_clause_stays_in_one_chunk():
    penalty = SAMPLE_EN.index("9.2 Late delivery penalty")
    end = SAMPLE_EN.index("9.3")
    assert any(c.start <= penalty and end <= c.end for c in chunk_contract(SAMPLE_EN))


def test_unstructured_text_falls_back_to_paragraphs_within_size_limit():
    text = "\n\n".join(f"Paragraph {i} " + "word " * 120 for i in range(30))
    chunks = chunk_contract(text)
    assert len(chunks) > 1
    assert all(len(c.text) <= MAX_CHARS for c in chunks)


def test_one_huge_paragraph_is_hard_split():
    text = "This is a sentence about delivery terms. " * 400
    assert all(c.end - c.start <= MAX_CHARS for c in chunk_contract(text))


def test_no_empty_chunks():
    for text in (SAMPLE_EN, SAMPLE_AR, "  \n\n  1. A\n\n\n\n"):
        assert all(c.text for c in chunk_contract(text))
