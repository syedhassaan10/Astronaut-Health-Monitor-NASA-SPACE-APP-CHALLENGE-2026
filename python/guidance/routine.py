"""Daily routine: has the crew member done today's check-in, vitals and workout?
Also a streak: how many days in a row all three were done (a light game element)."""

from dataclasses import dataclass


@dataclass
class DayRoutine:
    checkin: bool
    vitals: bool
    workout: bool

    @property
    def done_count(self):
        return int(self.checkin) + int(self.vitals) + int(self.workout)

    @property
    def complete(self):
        return self.done_count == 3

    def missing(self):
        """Names of the tasks still to do, in routine order."""
        out = []
        if not self.checkin:
            out.append("Check-in")
        if not self.vitals:
            out.append("Vitals")
        if not self.workout:
            out.append("Workout")
        return out


def routine_for_day(crew_id, day, checkins, vitals, records):
    """`records` are SessionRecords; a workout counts when at least one rep was done that day."""
    has_checkin = any(c.crew_id == crew_id and c.day == day for c in checkins)
    has_vitals = any(v.crew_id == crew_id and v.day == day for v in vitals)
    has_workout = any(r.crew_id == crew_id and r.day == day and len(r.reps) > 0 for r in records)
    return DayRoutine(checkin=has_checkin, vitals=has_vitals, workout=has_workout)


def streak(crew_id, today, checkins, vitals, records):
    """Days in a row, ending today (or yesterday if today is not finished yet), with the full routine done."""
    day = today
    if not routine_for_day(crew_id, day, checkins, vitals, records).complete:
        day -= 1
    count = 0
    while day >= 1 and routine_for_day(crew_id, day, checkins, vitals, records).complete:
        count += 1
        day -= 1
    return count
