"""Fit the original fishing rewards without importing network-loading game modules."""
import json
from pathlib import Path
from math import sqrt


def fit_rewards(host):
    data = host / 'data/fishgame'
    fish = json.loads((data / 'fish_data_poke_ver.json').read_text())
    groups = json.loads((data / 'fish_data_group.json').read_text())
    fish += [entry for group in groups for entry in group['fish']]
    result = {}
    for rarity in ('R', 'SR', 'SSR'):
        pairs = [(entry['std_power'], entry['exp']) for entry in fish if entry['rarity'] == rarity]
        count = len(pairs)
        mx = sum(x for x,y in pairs)/count
        my = sum(y for x,y in pairs)/count
        slope = sum((x-mx)*(y-my) for x,y in pairs)/sum((x-mx)**2 for x,y in pairs)
        intercept = my-slope*mx
        rmse = sqrt(sum((y-(slope*x+intercept))**2 for x,y in pairs)/count)
        result[rarity] = {'samples':count, 'slope':slope, 'intercept':intercept, 'rmse':rmse}
    return result


if __name__ == '__main__':
    print(json.dumps(fit_rewards(Path(__file__).resolve().parents[3]), indent=2))
