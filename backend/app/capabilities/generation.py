"""Current generation adapter; course-selected pack composition can replace this selection."""
from .symbolic import pack


def checker_contract():
    return pack.contract()


def compose_prompts(prompts):
    result = dict(prompts)
    for stage, fragment in pack.prompt_fragments().items():
        result[stage] += "\n\n" + fragment
    return result
