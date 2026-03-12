import random
import math


def simulate_draw():
    return random.sample(range(1, 26), 14)


def monte_carlo_simulation(user_numbers, simulations=10000):
    if simulations <= 0:
        raise ValueError("simulations debe ser mayor que 0")

    if not user_numbers:
        raise ValueError("user_numbers no puede estar vacio")

    results = {i: 0 for i in range(0, 15)}

    for _ in range(simulations):
        draw = simulate_draw()
        matches = len(set(user_numbers) & set(draw))
        results[matches] += 1

    probabilities = {
        k: (v / simulations) * 100 for k, v in results.items()
    }

    return probabilities
def combinatoria(n, r):
    return math.comb(n, r)


def exact_probability(k):
    total = combinatoria(25, 14)
    prob = (combinatoria(14, k) * combinatoria(11, 14 - k)) / total
    return prob * 100
