import hashlib
import json
from .errors import DomainError
from .models import IdempotencyRecord


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def intent(owner, operation, key, body):
    if not key or len(key) > 128:
        raise DomainError("IDEMPOTENCY_KEY_REQUIRED", status=400)
    record, created = IdempotencyRecord.objects.get_or_create(
        owner=owner, operation=operation, key=key, defaults={"request_hash": digest(body)})
    if record.request_hash != digest(body):
        raise DomainError("IDEMPOTENCY_CONFLICT", "This request key was already used for different inputs.")
    return record
