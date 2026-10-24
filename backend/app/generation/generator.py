from app.core.tasks import checkpoint
from app.core.errors import DomainError


def run_generation(token):
    checkpoint(token, "Checking generation inputs")
    raise DomainError("GENERATION_PIPELINE_IN_PROGRESS", "The generation entry is ready; content generation is being implemented.", retryable=False)
