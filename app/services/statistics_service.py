import random

from app.simulations.montecarlo import monte_carlo_simulation


def calculate_statistics(numbers_matrix):
    frequency = {n: 0 for n in range(1, 26)}

    for draw in numbers_matrix:
        for num in draw:
            if num in frequency:
                frequency[num] += 1

    total_draws = len(numbers_matrix)
    average_frequency = {
        n: (frequency[n] / total_draws) if total_draws else 0 for n in frequency
    }

    most_frequent = max(frequency, key=frequency.get)
    least_frequent = min(frequency, key=frequency.get)

    return {
        "frequency": frequency,
        "average_frequency": average_frequency,
        "total_draws": total_draws,
        "most_frequent": most_frequent,
        "least_frequent": least_frequent,
    }


def generate_optimized_plays(numbers_matrix):
    frequency = {n: 0 for n in range(1, 26)}

    for draw in numbers_matrix:
        for num in draw:
            if num in frequency:
                frequency[num] += 1

    # Ranking de numeros por frecuencia.
    sorted_numbers = sorted(frequency, key=frequency.get, reverse=True)
    hot_numbers = sorted_numbers[:12]
    cold_numbers = sorted_numbers[12:]

    evaluated_plays = []

    for _ in range(5):
        play = []
        play += random.sample(hot_numbers, 9)
        play += random.sample(cold_numbers, 5)
        play = sorted(play)

        evaluated = evaluate_play(play)
        evaluated_plays.append(evaluated)

    evaluated_plays.sort(key=lambda x: x["score"], reverse=True)

    ranking = sorted_numbers
    for item in evaluated_plays:
        item["balance_index"] = calculate_balance_index(item["play"], ranking)
        item["global_confidence"] = calculate_global_confidence(item)

    evaluated_plays.sort(key=lambda x: x["global_confidence"], reverse=True)

    for i, item in enumerate(evaluated_plays):
        item["is_best"] = i == 0

    return evaluated_plays[:3]


def evaluate_play(play):
    results = monte_carlo_simulation(play, simulations=15000)

    prob_10_plus = sum(v for k, v in results.items() if int(k) >= 10)
    prob_11_plus = sum(v for k, v in results.items() if int(k) >= 11)
    prob_12_plus = sum(v for k, v in results.items() if int(k) >= 12)

    score = (prob_10_plus * 1) + (prob_11_plus * 2) + (prob_12_plus * 3)

    return {
        "play": play,
        "prob_10_plus": round(prob_10_plus, 4),
        "prob_11_plus": round(prob_11_plus, 4),
        "prob_12_plus": round(prob_12_plus, 4),
        "score": round(score, 4),
    }


def calculate_balance_index(play, ranking):
    score = 0

    for number in play:
        position = ranking.index(number)

        if position <= 4:
            score += 5
        elif position <= 9:
            score += 3
        elif position <= 14:
            score += 2
        elif position <= 19:
            score += 1

    max_score = 14 * 5
    balance_percentage = (score / max_score) * 100

    return round(balance_percentage, 2)


def calculate_global_confidence(item):
    score_component = min(item["score"] * 5, 100)
    balance_component = item["balance_index"]
    montecarlo_component = item["prob_10_plus"] * 10

    weight_score = 0.4
    weight_balance = 0.3
    weight_montecarlo = 0.3

    confidence = (
        score_component * weight_score
        + balance_component * weight_balance
        + montecarlo_component * weight_montecarlo
    )

    return round(min(confidence, 100), 2)
