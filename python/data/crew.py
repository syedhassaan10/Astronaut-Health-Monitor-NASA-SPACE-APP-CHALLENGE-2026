"""Demo crew roster (made-up people)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CrewMember:
    id: str
    name: str
    role: str
    mass_kg: float


CREW = [
    CrewMember("c1", "Cmdr. A. Rivera", "Commander", 78),
    CrewMember("c2", "Dr. M. Okafor", "Crew Medical Officer", 70),
    CrewMember("c3", "Eng. K. Tanaka", "Flight Engineer", 66),
]


def crew_by_id(crew_id):
    for c in CREW:
        if c.id == crew_id:
            return c
    return None
