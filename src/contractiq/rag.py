"""Answer a question: route it, retrieve clauses and/or query procurement data, then generate."""

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel

from contractiq.db import connect
from contractiq.llm import generate
from contractiq.search import Hit, retrieve
from contractiq.synthetic import SUPPLIERS

TOP_K = 5
SQL_ROW_LIMIT = 50

SCHEMA_FOR_SQL = """
suppliers(id, name, country, category)
purchase_orders(id, po_number, supplier_id -> suppliers.id, contract_id -> contracts.id,
                order_date DATE, promised_date DATE, delivered_date DATE NULL,
                amount_sar NUMERIC, status TEXT  -- 'open' | 'delivered' | 'cancelled')
contracts(id, title, contract_type, language, supplier, start_date DATE, end_date DATE)
A delivery is late when delivered_date > promised_date.
"""


class Route(BaseModel):
    route: Literal["contracts", "data", "both"]


class SQL(BaseModel):
    sql: str


ROUTER_PROMPT = """Classify the user's question about supplier contracts and procurement.
- "contracts": answered by what a contract SAYS (clauses, terms, penalty rates, renewal, notice,
  liability, governing law, expiry). Most questions are this.
- "data": answered by procurement RECORDS (how many orders, totals, amounts, which orders were late).
- "both": explicitly asks for a contract term AND record figures together.
Examples:
"What is the late delivery penalty for X?" -> contracts
"How many orders from X were late?" -> data
"How much penalty can we claim from X for this year's late orders?" -> both
Question: {q}"""

SQL_PROMPT = """Write one PostgreSQL SELECT query that answers the question.
Tables:
{schema}
Rules: SELECT only. Match supplier names with ILIKE. Today is {today}. Return at most {limit} rows.
Only select values that come from the tables; never add made-up constants (e.g. no `1000 AS penalty`).
If the question asks to change, delete or add data, still only read: select the matching rows.
Supplier names (English / Arabic): {suppliers}
Question: {q}"""

ANSWER_SYSTEM = """You answer questions about supplier contracts for a procurement team.
Use ONLY the numbered sources and the database result provided. After every fact taken from a
source, cite it like [1] or [2]. Facts from the database result need no citation marker; never
write markers like [Database result]. If the sources don't contain the answer, say so plainly
instead of guessing. You can only READ contracts and records: if asked to delete, change, add,
approve or send anything, say you can't do that, and never claim an action was taken.
Reply in the same language as the question. Be concise: 1-4 sentences."""


def cited_numbers(text: str) -> set[int]:
    """Source numbers cited in an answer, whether written [1][2], [1, 2] or [1،2]."""
    return {int(n) for group in re.findall(r"\[([\d\s,،]+)\]", text) for n in re.findall(r"\d+", group)}


def normalize_ar(text: str) -> str:
    """Fold common Arabic spelling variants (أ/إ/آ→ا, ة→ه, ى→ي) and strip diacritics."""
    text = re.sub(r"[ً-ْـ]", "", text)
    return text.translate(str.maketrans("أإآةى", "اااهي"))


_AR_VARIANTS = {"ا": "[اأإآ]", "أ": "[اأإآ]", "إ": "[اأإآ]", "آ": "[اأإآ]", "ة": "[ةه]", "ه": "[ةه]",
                "ى": "[ىي]", "ي": "[ىي]"}


def _name_pattern(s) -> re.Pattern:
    """Matches the supplier's English name, or its Arabic name in any common spelling."""
    ar = "".join(_AR_VARIANTS.get(ch, re.escape(ch)) + "[ً-ْـ]*" for ch in normalize_ar(s.name_ar))
    return re.compile(f"{re.escape(s.name)}|{ar}", re.IGNORECASE)


def detect_contract(conn, question: str) -> int | None:
    """If the question names one of the sample suppliers, scope retrieval to its contract."""
    for s in SUPPLIERS:
        if _name_pattern(s).search(question):
            row = conn.execute("SELECT id FROM contracts WHERE supplier = %s", (s.name,)).fetchone()
            return row[0] if row else None
    return None


def strip_supplier_names(question: str) -> str:
    """Once a supplier name has scoped the search, it only adds noise: contract clauses rarely
    repeat the party's name, and an Arabic name next to an English clause drags the reranker
    score down (0.019 -> 0.043 on the Najd penalty question)."""
    for s in SUPPLIERS:
        question = _name_pattern(s).sub(" ", question)
    return re.sub(r"\s+", " ", question).strip()


def clean_select(sql: str) -> str | None:
    """The query with any trailing semicolon removed, or None unless it is a single SELECT/WITH."""
    sql = sql.strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", sql) or ";" in sql:
        return None
    return sql


def execute_readonly(conn, sql: str) -> dict:
    # Belt and braces: even a SELECT runs inside a read-only transaction with a timeout.
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL statement_timeout = '5s'")
        cur = conn.execute(sql)
        columns = [d.name for d in cur.description]
        rows = [[str(v) if v is not None else None for v in r] for r in cur.fetchmany(SQL_ROW_LIMIT)]
    return {"sql": sql, "columns": columns, "rows": rows}


def run_sql(conn, question: str) -> dict:
    names = ", ".join(f"{s.name} / {s.name_ar}" for s in SUPPLIERS)
    raw = generate(SQL_PROMPT.format(schema=SCHEMA_FOR_SQL, today=date.today(),
                                     limit=SQL_ROW_LIMIT, suppliers=names, q=question), schema=SQL).sql
    sql = clean_select(raw)
    if sql is None:
        return {"sql": raw, "error": "Only single SELECT queries are allowed."}
    return execute_readonly(conn, sql)


def confidence(hits: list[Hit], arabic: bool = False) -> str:
    """Calibrated on the CUAD evaluation. English questions: when the top chunk is right its
    reranker score has a median of 0.55, when wrong 0.07. Arabic questions against English
    contracts score about 4x lower across the board (0.13 vs 0.03), so they get scaled
    thresholds. A top chunk that clearly stands out from the runner-up is also a strong signal."""
    if not hits:
        return "low"
    scale = 0.25 if arabic else 1.0
    top = hits[0].score
    second = hits[1].score if len(hits) > 1 else 0.0
    if top >= 0.5 * scale or (top >= 0.1 * scale and top >= 5 * second):
        return "high"
    return "medium" if top >= 0.1 * scale else "low"


def answer(question: str, contract_id: int | None = None) -> dict:
    with connect() as conn:
        route = generate(ROUTER_PROMPT.format(q=question), fast=True, schema=Route).route
        scope = contract_id or detect_contract(conn, question)

        search_text = strip_supplier_names(question) if scope and not contract_id else question
        hits = retrieve(search_text or question, k=TOP_K, contract_id=scope, conn=conn) if route != "data" else []
        data = None
        if route != "contracts":
            try:
                data = run_sql(conn, question)
            except Exception as e:  # a bad generated query shouldn't sink the whole answer
                data = {"error": str(e)}

    sources = "\n\n".join(f"[{i}] {h.contract_title} — {h.heading}\n{h.text}" for i, h in enumerate(hits, 1))
    db = ""
    if data and "rows" in data:
        db = f"Database result for: {data['sql']}\ncolumns: {data['columns']}\nrows: {data['rows']}"
    # Sources may be in the other language; without this the model tends to answer in theirs.
    reply_in = "Arabic" if re.search(r"[؀-ۿ]", question) else "English"
    prompt = (f"Question: {question}\n\nSources:\n{sources or '(none)'}\n\n{db}\n\n"
              f"Write the answer in {reply_in}.")
    text = generate(prompt, system=ANSWER_SYSTEM)

    cited = cited_numbers(text)
    return {
        "question": question,
        "route": route,
        "scoped_contract_id": scope,
        "answer": text,
        "confidence": confidence(hits, arabic=reply_in == "Arabic") if hits else ("high" if data and "rows" in data else "low"),
        "citations": [
            {"n": i, "chunk_id": h.chunk_id, "contract_id": h.contract_id, "contract_title": h.contract_title,
             "heading": h.heading, "start_char": h.start_char, "end_char": h.end_char,
             "score": round(h.score, 4), "cited": i in cited}
            for i, h in enumerate(hits, 1)
        ],
        "data": data,
    }
