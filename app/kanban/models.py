from dataclasses import dataclass


@dataclass(frozen=True)
class KanbanItem:
    number: object
    title: str
    status: str
    assignees: tuple
    labels: tuple
