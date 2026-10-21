from django.db import transaction
from .tasks import locked_task
from .errors import DomainError

CALL_LIMITS = {"analysis": 8, "planning": 2, "generation": 16, "parse": 0, "export": 0}


@transaction.atomic
def reserve_call(token, input_tokens, output_tokens):
    task = locked_task(token)
    if not (isinstance(input_tokens, int) and isinstance(output_tokens, int)) or not (0 < input_tokens <= 60000 and 0 < output_tokens <= 12000):
        raise DomainError("TOKEN_BUDGET_EXCEEDED")
    if task.call_count >= CALL_LIMITS[task.kind]:
        raise DomainError("CALL_BUDGET_EXCEEDED")
    task.call_count += 1
    task.save(update_fields=["call_count"])
    return task.call_count
