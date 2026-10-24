"""Versioned generation contracts; expanded with paired content in implementation step 2."""
from app.core.idempotency import digest


def schema_hashes():
    return {"pipeline": digest({"version": "generation-entry-v1"})}
