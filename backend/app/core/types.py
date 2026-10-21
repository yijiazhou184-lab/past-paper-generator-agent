from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class ExecutionToken:
    task_id: UUID
    epoch: int
