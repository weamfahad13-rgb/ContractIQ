"""Load contracts into Postgres and split them into chunks.

    python -m contractiq.ingest
"""

from contractiq.chunking import chunk_contract
from contractiq.cuad import load_supply_chain_contracts
from contractiq.db import apply_schema, connect


def upsert_contract(conn, *, title, source, contract_type, language, text, supplier=None,
                    start_date=None, end_date=None) -> int:
    old = conn.execute("SELECT full_text FROM contracts WHERE title = %s", (title,)).fetchone()
    unchanged = old is not None and old[0] == text
    contract_id = conn.execute(
        """
        INSERT INTO contracts (title, source, contract_type, language, supplier, start_date, end_date, full_text)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (title) DO UPDATE SET
            source = EXCLUDED.source, contract_type = EXCLUDED.contract_type,
            language = EXCLUDED.language, full_text = EXCLUDED.full_text,
            supplier = COALESCE(EXCLUDED.supplier, contracts.supplier),
            start_date = COALESCE(EXCLUDED.start_date, contracts.start_date),
            end_date = COALESCE(EXCLUDED.end_date, contracts.end_date)
        RETURNING id
        """,
        (title, source, contract_type, language, supplier, start_date, end_date, text),
    ).fetchone()[0]

    if unchanged:  # keep existing chunks and their embeddings
        return contract_id
    # Re-chunking invalidates old chunks (and their embeddings).
    conn.execute("DELETE FROM chunks WHERE contract_id = %s", (contract_id,))
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO chunks (contract_id, ord, heading, text, start_char, end_char, language)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            [(contract_id, i, c.heading, c.text, c.start, c.end, language)
             for i, c in enumerate(chunk_contract(text))],
        )
    return contract_id


def main() -> None:
    with connect() as conn:
        apply_schema(conn)
        contracts = load_supply_chain_contracts()
        for c in contracts:
            upsert_contract(conn, title=c.title, source="cuad", contract_type=c.contract_type,
                            language="en", text=c.text)
        n_chunks = conn.execute("SELECT count(*) FROM chunks").fetchone()[0]
        print(f"{len(contracts)} CUAD contracts, {n_chunks} chunks in the database")


if __name__ == "__main__":
    main()
