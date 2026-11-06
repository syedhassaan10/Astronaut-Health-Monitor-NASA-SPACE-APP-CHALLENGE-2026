"""Where the crew is. Gravity is a fraction of Earth's g.

`environment` picks the right emergency steps:
  microgravity - nothing stays put; people and fluids float
  partial      - Moon or Mars surface; a floor exists, but everything is lighter
  earth        - normal gravity
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    id: str
    label: str
    g: float
    environment: str


LOCATIONS = [
    Location("earth", "Earth (1.0 g)", 1.0, "earth"),
    Location("leo", "LEO / ISS (0 g)", 0.0, "microgravity"),
    Location("transit", "Deep Space Transit (0 g)", 0.0, "microgravity"),
    Location("moon", "Moon (0.166 g)", 0.166, "partial"),
    Location("mars", "Mars (0.38 g)", 0.38, "partial"),
    Location("custom", "Custom", 0.5, "partial"),
]


def location_by_id(location_id):
    for loc in LOCATIONS:
        if loc.id == location_id:
            return loc
    return LOCATIONS[0]


def environment_for_g(g):
    """Environment for a custom gravity value."""
    if g < 0.05:
        return "microgravity"
    if g < 0.95:
        return "partial"
    return "earth"
