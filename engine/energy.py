"""Daily energy needs (kcal), from Hudebia Shaikh's health monitor: Mifflin-St Jeor resting energy times an
activity factor. An estimate for planning meals, not a measurement."""

ACTIVITY_FACTORS = {
    "low": 1.2,        # mostly desk work
    "moderate": 1.55,  # daily exercise sessions
    "high": 1.725,     # long exercise plus physical work (spacewalk training, heavy maintenance)
}


def resting_energy(weight_kg, height_cm, age, sex):
    """Mifflin-St Jeor resting energy in kcal/day. sex: "M" or "F"."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "M" else base - 161


def daily_energy(weight_kg, height_cm, age, sex, activity="moderate"):
    """Estimated kcal per day, rounded to the nearest 10."""
    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        raise ValueError("weight, height and age must be positive")
    kcal = resting_energy(weight_kg, height_cm, age, sex) * ACTIVITY_FACTORS[activity]
    return int(round(kcal / 10.0) * 10)
