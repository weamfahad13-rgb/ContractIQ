"""Read CUAD: the supply-chain contracts, their text, and the lawyers' labels."""

import json
from dataclasses import dataclass, field
from functools import cache

from contractiq.config import CUAD_DIR, SUPPLY_CHAIN_TYPES


@dataclass
class Label:
    category: str
    spans: list[tuple[int, int]]  # character offsets into the contract text; empty = clause absent


@dataclass
class CuadContract:
    title: str
    contract_type: str
    text: str
    labels: list[Label] = field(default_factory=list)


def _contract_type(folder: str) -> str | None:
    for t in SUPPLY_CHAIN_TYPES:
        if t.lower() in folder.lower():
            return t
    return None


@cache
def load_supply_chain_contracts() -> list[CuadContract]:
    data = json.loads((CUAD_DIR / "CUAD_v1.json").read_text(encoding="utf-8"))["data"]
    # The folder each PDF sits in is the only place CUAD records the contract type.
    folder = {p.stem.lower(): p.parent.name
              for p in (CUAD_DIR / "full_contract_pdf").rglob("*") if p.suffix.lower() == ".pdf"}

    contracts = []
    for c in data:
        ctype = _contract_type(folder.get(c["title"].lower(), ""))
        if not ctype:
            continue
        para = c["paragraphs"][0]
        labels = [
            Label(category=q["id"].split("__")[-1],
                  spans=[(a["answer_start"], a["answer_start"] + len(a["text"])) for a in q["answers"]])
            for q in para["qas"]
        ]
        contracts.append(CuadContract(title=c["title"], contract_type=ctype,
                                      text=para["context"], labels=labels))
    return contracts
