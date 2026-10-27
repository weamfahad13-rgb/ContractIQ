# ContractIQ: technical details

## How it works

```
question ──► router (Gemini Flash) ──┬──► contracts: hybrid search ──► reranker + rank fusion ──┐
                                     │    (pgvector + Postgres full-text, RRF)                   ├──► answer with [n] citations (Gemini)
                                     └──► data: Text-to-SQL on purchase orders ──────────────────┘
```

- **Chunking by clause.** Contracts are split on their own clause headings (`9.`, `ARTICLE III`),
  falling back to sub-clauses and paragraphs for long or unstructured contracts. Chunks keep
  character offsets, so the UI can highlight the cited clause in the original text.
- **Cross-lingual embeddings.** [BGE-M3](https://huggingface.co/BAAI/bge-m3) puts Arabic and English
  in one vector space, so an Arabic question finds an English clause.
- **Hybrid search.** Vector search catches meaning; keyword search catches names and numbers.
  The two rankings are merged with Reciprocal Rank Fusion.
- **Reranking.** [bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) reads the
  question and each candidate together and reorders the top 20; its ranking is then fused with
  the hybrid ranking, so one bad reranker call can't bury a clause both searches agree on.
- **Text-to-SQL.** Questions about counts and amounts become a single `SELECT`, run in a read-only
  transaction with a timeout.
- **Provider-agnostic LLM layer.** All model calls go through `src/contractiq/llm.py`. On the Gemini
  free tier each model has its own small daily quota (20 requests for 2.5 Flash), so when a model is
  overloaded or out of quota the call falls through to the next model in `GEMINI_FALLBACK_MODELS`.

## Evaluation

Retrieval is measured against [CUAD](https://www.atticusprojectai.org/cuad), 510 commercial contracts
labeled by lawyers. ContractIQ uses the 96 supply-chain contracts (supply, distribution, manufacturing,
transportation, outsourcing) and asks one natural question per labeled clause type, in English and
in Arabic, scoped to the contract. A question counts as answered when the top-5 chunks cover at least
half of the lawyer-labeled span.

675 questions over 92 contracts (RTX 5050 laptop GPU):

| Version | Recall@5 EN | Recall@5 AR | MRR EN | Time / question (EN+AR avg) |
|---|---|---|---|---|
| v1 Vector search | 87.6% | 84.3% | 0.732 | 18 ms |
| v2 Hybrid (vector + keyword, RRF) | 85.5% | 84.3% | 0.678 | 20 ms |
| v3 Hybrid + reranker | 90.5% | 84.9% | **0.803** | 458 ms |
| v4 Reranker fused with hybrid ranking (default) | **91.7%** | **87.1%** | 0.759 | 457 ms |

What the numbers say:
- **The reranker is the biggest single win**: +3 points of recall and a much better first result
  (MRR 0.73 → 0.80).
- **But on its own it sometimes buries the right clause.** Audit-rights questions dropped to 61%
  with the reranker; in 7 of the 21 misses, hybrid search had ranked the right clause first. v4
  combines the reranker's ranking with the hybrid ranking (RRF), which lifts audit rights to 78% EN /
  72% AR and overall recall to 91.7% / 87.1%, at no extra cost. The trade-off: the right clause is
  in the top 5 more often, but slightly less often at #1 (MRR 0.80 → 0.76).
- **Keyword search slightly hurts on this benchmark.** The questions are generic ("Is there a cap on
  liability?") and scoped to one contract, so exact-word matches add noise. It is kept because it is
  what finds supplier names and contract numbers in open questions, which CUAD doesn't test.
- **Arabic questions work against English contracts**, about 5 points behind English (4.6 with v4). Keyword search
  can't help there (different scripts), so only the cross-lingual embeddings and the reranker do.
- Running the reranker in fp16 cut its latency from 3.7 s to about 0.5 s per question with identical recall. Hybrid search adds almost nothing over vector search (18-20 ms); the reranker is where the time goes.

**Answers.** 24 questions (16 CUAD in English and Arabic, 8 about the sample suppliers including two
Text-to-SQL) run through the full pipeline and graded by an LLM judge:

| Faithfulness | Relevance | Said "not found" on a labeled clause | Avg. time per answer |
|---|---|---|---|
| 100% | 100% | 12.5% (2 of 16) | 15.2 s* |

Faithfulness only says nothing was invented. An honest "the sources don't say" also counts as
faithful, which is why the not-found rate is reported next to it: those are retrieval misses,
in line with the ~85-90% recall above. All sample-supplier answers were also checked by hand
against the known contract values. 24 questions is a small sample, limited by the free-tier quota.

\* Mostly waiting on the Gemini free tier (5 requests per minute, then falling back to other models);
retrieval itself takes about 0.5 s.

```bash
python -m contractiq.evaluate          # retrieval: Recall@5 and MRR, per version and language
python -m contractiq.evaluate_answers  # answers: faithfulness and relevance, graded by an LLM judge
```

Results are shown on the app's Evaluation page and saved in `data/eval/`.

## Data

- **CUAD v1** (CC BY 4.0), downloaded from Hugging Face into `data/raw/cuad`.
- **Sample suppliers**: eight fictional GCC suppliers with generated contracts (four in Arabic) and
  purchase orders, in `src/contractiq/synthetic.py`. Every clause value is known, which keeps the
  procurement data consistent with the contracts.

## Run it locally

Requirements: Python 3.12+, Node 20+, Docker Desktop, an NVIDIA GPU (optional, much faster).

```bash
cp .env.example .env                # then set POSTGRES_PASSWORD and GEMINI_API_KEY
docker compose up -d --wait         # Postgres 17 + pgvector

python -m venv .venv
.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cu130
.venv/Scripts/pip install -r requirements.txt -e .

python -c "from huggingface_hub import snapshot_download as s; s('theatticusproject/cuad', repo_type='dataset', local_dir='data/raw/cuad')"
python -m contractiq.ingest         # load + chunk the CUAD supply-chain contracts
python -m contractiq.synthetic      # sample suppliers, contracts, purchase orders
python -m contractiq.embed          # embed all chunks
python -m contractiq.evaluate       # retrieval evaluation

uvicorn contractiq.api:app --port 8000
cd frontend && npm install && npm run dev   # http://localhost:5173
```

`npm run build` puts the frontend in `frontend/dist`, which the API then serves at `http://localhost:8000`.

## Tests

```bash
pytest tests          # 62 tests; the API/database ones need the Postgres container running
```

They cover the clause chunker (offsets, Arabic headings, fallbacks), the SQL guard (only a single
SELECT gets through; writes fail inside the read-only transaction; slow queries time out),
citation parsing, Arabic name matching, every API endpoint and its input validation, and that
files outside the frontend build (like `.env`) can't be fetched through the static file route.

## Project layout

```
src/contractiq/
  chunking.py      clause-aware chunker
  ingest.py        load contracts and chunks into Postgres
  synthetic.py     sample suppliers, Arabic/English contracts, purchase orders
  embed.py         BGE-M3 embeddings into pgvector
  search.py        vector, keyword, RRF, rerank
  rag.py           router, Text-to-SQL, grounded answers
  llm.py           the only Gemini-specific code
  evaluate*.py     retrieval and answer evaluation
  api.py           FastAPI
frontend/          React + Vite + Tailwind
notebooks/         data exploration
```
