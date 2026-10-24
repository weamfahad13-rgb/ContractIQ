"""Embed every chunk that doesn't have an embedding yet.

    python -m contractiq.embed
"""

from contractiq.db import connect
from contractiq.models import embed

BATCH = 256


def main() -> None:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, heading, text FROM chunks WHERE embedding IS NULL ORDER BY id"
        ).fetchall()
        print(f"{len(rows)} chunks to embed")
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            # The heading carries the clause topic ("9.2 Late delivery penalty"), so embed it too.
            vectors = embed([f"{h}\n{t}" for _, h, t in batch])
            with conn.cursor() as cur:
                cur.executemany("UPDATE chunks SET embedding = %s WHERE id = %s",
                                [(v, cid) for (cid, _, _), v in zip(batch, vectors)])
            print(f"  {min(i + BATCH, len(rows))}/{len(rows)}")


if __name__ == "__main__":
    main()
