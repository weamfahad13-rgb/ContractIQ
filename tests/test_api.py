"""API and database tests. Need the Postgres container running (docker compose up -d)."""

import psycopg
import pytest
from fastapi.testclient import TestClient

from contractiq.api import app
from contractiq.db import connect
from contractiq.rag import detect_contract, execute_readonly

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"ok": True}


def test_contracts_list_has_cuad_and_sample_contracts():
    rows = client.get("/api/contracts").json()
    sources = {r["source"] for r in rows}
    assert sources == {"cuad", "synthetic"}
    assert sum(r["source"] == "synthetic" for r in rows) == 8
    assert all(r["status"] in {"active", "expiring_soon", "expired", "unknown"} for r in rows)
    assert all(r["chunks"] > 0 for r in rows)


def test_contract_detail_chunks_point_inside_the_text():
    first = client.get("/api/contracts").json()[0]
    c = client.get(f"/api/contracts/{first['id']}").json()
    assert c["full_text"]
    assert all(0 <= ch["start_char"] < ch["end_char"] <= len(c["full_text"]) for ch in c["chunks"])


def test_missing_contract_is_404():
    assert client.get("/api/contracts/999999").status_code == 404


def test_non_numeric_contract_id_is_rejected():
    assert client.get("/api/contracts/abc").status_code == 422


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "x"}, {"question": "a" * 501},
                                  {"question": "ok question", "contract_id": "abc"}])
def test_chat_rejects_invalid_input(body):
    assert client.post("/api/chat", json=body).status_code == 422


def test_evaluation_results_are_served():
    ev = client.get("/api/evaluation").json()
    assert {r["mode"] for r in ev["retrieval"]["runs"]} == {"vector", "hybrid", "rerank"}


@pytest.mark.parametrize("path", ["/chat", "/contracts", "/evaluation", "/some/unknown/page"])
def test_frontend_routes_serve_the_app(path):
    r = client.get(path)
    assert r.status_code == 200 and "<div id=\"root\">" in r.text


@pytest.mark.parametrize("path", ["/../.env", "/..%2F.env", "/%2e%2e/.env", "/assets/../../.env"])
def test_files_outside_the_build_are_never_served(path):
    r = client.get(path)
    assert "POSTGRES_PASSWORD" not in r.text and "GEMINI_API_KEY" not in r.text


def test_readonly_execution_blocks_writes():
    with connect() as conn:
        before = conn.execute("SELECT count(*) FROM purchase_orders").fetchone()[0]
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            execute_readonly(conn, "DELETE FROM purchase_orders")
        assert conn.execute("SELECT count(*) FROM purchase_orders").fetchone()[0] == before


def test_readonly_execution_times_out_slow_queries():
    with connect() as conn, pytest.raises(psycopg.errors.QueryCanceled):
        execute_readonly(conn, "SELECT pg_sleep(10)")


@pytest.mark.parametrize("question, supplier", [
    ("What is the penalty for Al-Sharq Pharma?", "Al-Sharq Pharma"),
    ("ما غرامة عقد الرياض للخدمات اللوجستيه؟", "Riyadh Logistics"),
    ("عقد البحرين لتجارة الادوية", "Bahrain Pharma Trading"),
])
def test_supplier_names_scope_the_question(question, supplier):
    with connect() as conn:
        cid = detect_contract(conn, question)
        assert conn.execute("SELECT supplier FROM contracts WHERE id = %s", (cid,)).fetchone()[0] == supplier


def test_unrelated_question_is_not_scoped():
    with connect() as conn:
        assert detect_contract(conn, "Is there a cap on liability?") is None


def test_sample_data_has_no_deliveries_in_the_future():
    with connect() as conn:
        assert conn.execute(
            "SELECT count(*) FROM purchase_orders WHERE delivered_date > DATE '2026-10-24'"
        ).fetchone()[0] == 0
