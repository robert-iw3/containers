"""
Deterministic synthetic corpus + embeddings for UAT and demos.

No model downloads: embed() hashes tokens into a 384-dim unit vector
(each token contributes a seeded random unit vector). Deterministic across
runs, and texts sharing tokens land closer in cosine space, which is enough
to validate indexing, search, filtering and recall.
"""

import hashlib

import numpy as np

DIM = 384

CATEGORIES = ["billing", "shipping", "returns", "hardware", "account"]

_TEMPLATES = {
    "billing": "Invoice {n} was charged twice on the corporate card and finance needs a credit memo",
    "shipping": "Order {n} left the warehouse but the carrier tracking shows no movement for days",
    "returns": "Customer wants to return item {n} because the packaging arrived damaged in transit",
    "hardware": "Device {n} overheats under sustained load and throttles the sensor readings",
    "account": "User {n} cannot reset the password because the recovery email bounces",
}


def _token_vec(token: str) -> np.ndarray:
    seed = int.from_bytes(hashlib.sha256(token.encode()).digest()[:8], "big") % (2**32)
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(DIM)
    return v / np.linalg.norm(v)


def embed(text: str) -> list[float]:
    tokens = text.lower().split()
    v = np.sum([_token_vec(t) for t in tokens], axis=0)
    v = v / np.linalg.norm(v)
    return v.astype(np.float32).tolist()


def generate_corpus(n: int = 2000) -> list[dict]:
    rng = np.random.default_rng(42)
    docs = []
    for i in range(n):
        category = CATEGORIES[i % len(CATEGORIES)]
        text = f"ticket doc{i:05d} {_TEMPLATES[category].format(n=i)}"
        docs.append(
            {
                "id": i,
                "text": text,
                "category": category,
                "year": int(rng.integers(2020, 2027)),
                "vector": embed(text),
            }
        )
    return docs
