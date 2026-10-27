# ContractIQ

ContractIQ is a RAG (Retrieval-Augmented Generation) assistant for procurement teams. You ask
a question about a supplier contract in English or Arabic, and it answers with the exact clause
the answer came from.

## How it works

The contracts are split into clauses and stored as embeddings. When you ask a question, the
system runs a hybrid search, by meaning and by keywords, then a reranker rereads the best
matches to pick the most relevant one. The language model writes the answer using only those
clauses and cites them. Questions about numbers, such as how many orders arrived late, go
through Text-to-SQL on the purchase-order database instead. If the contracts don't contain the
answer, the assistant says so rather than guessing.

## Results

The retrieval was tested on 675 questions over real contracts labeled by lawyers (the CUAD
dataset). It finds the right clause 91.7% of the time in English and 87.1% in Arabic.

## Built with

Python, FastAPI, PostgreSQL with pgvector, BGE-M3 and React.

## Run it

```bash
docker compose up -d
pip install -r requirements.txt -e .
uvicorn contractiq.api:app
```

Full setup, evaluation details and tests: [docs/details.md](docs/details.md).
