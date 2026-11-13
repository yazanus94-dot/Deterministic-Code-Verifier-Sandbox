def solve(payload):
    nums = payload["nums"]; target = payload["target"]
    best = None; seen = {}
    for j, value in enumerate(nums):
        need = target - value
        if need in seen:
            pair = (seen[need], j)
            if best is None or pair < best: best = pair
        seen.setdefault(value, j)
    return best
