from decimal import Decimal


def fish_reward(rarity, difficulty):
    value = Decimal(str(difficulty))
    if not value.is_finite() or value < 0:
        raise ValueError("Fish difficulty must be finite and nonnegative")
    slope, intercept = {"R": (1, 10), "SR": (2, 0), "SSR": (3, 0)}[rarity]
    return int(slope * value + intercept)


def birth_stats(rarity, levels, rarity_settings):
    if len(levels) != 2 or any(not isinstance(level, int) or level < 1 for level in levels):
        raise ValueError("Two positive integer contributor levels are required")
    average = sum(levels) / 2
    difficulty = rarity_settings[rarity]["difficulty"] + average
    return {"contributor_levels": list(levels), "mean_contributor_level": average,
            "difficulty": difficulty, "reward": fish_reward(rarity, difficulty)}
