from flask import Blueprint, Response, jsonify, render_template, request, has_request_context
from datetime import datetime
import json
import math
import random
from app.services.history_service import load_history, extract_numbers
from app.services.statistics_service import (
    calculate_balance_index,
    calculate_global_confidence,
    calculate_statistics,
    evaluate_play,
    generate_optimized_plays,
)
from app.simulations.montecarlo import monte_carlo_simulation
from app.services.personal_service import save_play
from app.database.db import get_connection
import pandas as pd


# Blueprint
main = Blueprint("main", __name__)

I18N = {
    "es": {
        "field_required": "Campo requerido",
        "invalid_numbers_format": "Formato de numeros invalido",
        "expected_numbers": "Deben ser {count} numeros",
        "no_history": "No hay historial disponible",
        "invalid_json": "JSON invalido",
        "date_required": "Fecha requerida",
        "invalid_numbers": "Numeros invalidos",
        "params_out_of_range": "Parametros fuera de rango",
        "tickets_must_list": "tickets debe ser una lista",
        "no_valid_tickets": "No hay tickets validos",
        "invalid_count": "count invalido",
        "count_range": "count debe estar entre 1 y 300",
        "invalid_id": "id invalido",
        "record_not_found": "Registro no encontrado",
        "modes_must_list": "modes debe ser una lista",
        "file_required": "Archivo requerido",
        "excel_read_error": "No se pudo leer el archivo Excel",
        "excel_columns_error": "El archivo no tiene las columnas requeridas",
        "inverse_text": "1 en {value}",
        "hits_registered": "Aciertos registrados: {hits}",
        "back": "Volver",
        "import_ok": "Archivo importado correctamente",
    },
    "en": {
        "field_required": "Required field",
        "invalid_numbers_format": "Invalid number format",
        "expected_numbers": "Must be {count} numbers",
        "no_history": "No history available",
        "invalid_json": "Invalid JSON",
        "date_required": "Date is required",
        "invalid_numbers": "Invalid numbers",
        "params_out_of_range": "Parameters out of range",
        "tickets_must_list": "tickets must be a list",
        "no_valid_tickets": "No valid tickets",
        "invalid_count": "Invalid count",
        "count_range": "count must be between 1 and 300",
        "invalid_id": "Invalid id",
        "record_not_found": "Record not found",
        "modes_must_list": "modes must be a list",
        "file_required": "File is required",
        "excel_read_error": "Could not read Excel file",
        "excel_columns_error": "File does not contain required columns",
        "inverse_text": "1 in {value}",
        "hits_registered": "Hits registered: {hits}",
        "back": "Back",
        "import_ok": "File imported successfully",
    },
}


def current_lang():
    if not has_request_context():
        return "es"
    raw = (
        request.headers.get("X-KA-Lang")
        or request.args.get("lang")
        or request.accept_languages.best_match(["es", "en"])
        or "es"
    )
    return "en" if str(raw).lower().startswith("en") else "es"


def tr(key, **kwargs):
    lang = current_lang()
    template = I18N.get(lang, I18N["es"]).get(key, key)
    return template.format(**kwargs)


def bad_request(message):
    return jsonify({"error": message}), 400


def parse_numbers(value, expected_len=None):
    if value is None:
        raise ValueError(tr("field_required"))

    if isinstance(value, str):
        raw_parts = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple)):
        raw_parts = value
    else:
        raise ValueError(tr("invalid_numbers_format"))

    try:
        numbers = [int(part) for part in raw_parts]
    except (TypeError, ValueError):
        raise ValueError(tr("invalid_numbers_format"))

    if expected_len is not None and len(numbers) != expected_len:
        raise ValueError(tr("expected_numbers", count=expected_len))

    return numbers


def get_numbers_matrix():
    df = load_history()
    numbers_matrix = extract_numbers(df)

    # Sumar historial manual guardado en BD (draw_history) al historial base CSV.
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT numbers FROM draw_history ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        try:
            parsed = parse_numbers(row["numbers"], expected_len=14)
            numbers_matrix.append(parsed)
        except ValueError:
            continue

    return numbers_matrix


def get_frequency_ranking(numbers_matrix):
    stats = calculate_statistics(numbers_matrix)
    sorted_freq = dict(sorted(stats["frequency"].items(), key=lambda x: x[1], reverse=True))
    ranking = list(sorted_freq.keys())
    return stats, sorted_freq, ranking


def top_pairs(numbers_matrix, limit=12):
    pair_count = {}
    for draw in numbers_matrix:
        sorted_draw = sorted(set(draw))
        for i in range(len(sorted_draw)):
            for j in range(i + 1, len(sorted_draw)):
                pair = f"{sorted_draw[i]}-{sorted_draw[j]}"
                pair_count[pair] = pair_count.get(pair, 0) + 1
    return sorted(pair_count.items(), key=lambda x: x[1], reverse=True)[:limit]


def build_ai_model(numbers_matrix):
    stats, sorted_freq, ranking = get_frequency_ranking(numbers_matrix)
    total_draws = max(stats["total_draws"], 1)

    scores = []
    for n in range(1, 26):
        freq_score = (sorted_freq.get(n, 0) / total_draws) * 100
        ranking_bonus = max(0, (25 - ranking.index(n)) * 1.2) if n in ranking else 0
        score = round(min(freq_score + ranking_bonus, 100), 1)
        scores.append({"number": n, "score": score})

    scores.sort(key=lambda x: x["score"], reverse=True)
    model_precision = round(sum(x["score"] for x in scores[:10]) / 10, 1) if scores else 0

    return {
        "model_precision": model_precision,
        "training_draws": stats["total_draws"],
        "updated_at": datetime.now().strftime("%d/%m/%Y"),
        "scores": scores,
    }


def save_ai_model(model_data):
    conn = get_connection()
    cursor = conn.cursor()
    trained_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO ai_models (trained_at, training_draws, model_precision, scores_json)
        VALUES (?, ?, ?, ?)
        """,
        (
            trained_at,
            model_data["training_draws"],
            model_data["model_precision"],
            json.dumps(model_data["scores"]),
        ),
    )
    model_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return model_id, trained_at


def load_latest_ai_model():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ai_models ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    try:
        scores = json.loads(row["scores_json"])
    except json.JSONDecodeError:
        return None

    return {
        "id": row["id"],
        "model_precision": row["model_precision"],
        "training_draws": row["training_draws"],
        "updated_at": datetime.strptime(row["trained_at"], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y"),
        "scores": scores,
    }


def get_or_train_ai_model():
    latest = load_latest_ai_model()
    if latest:
        return latest

    model = build_ai_model(get_numbers_matrix())
    model_id, trained_at = save_ai_model(model)
    model["id"] = model_id
    model["updated_at"] = datetime.strptime(trained_at, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
    return model


@main.app_context_processor
def inject_sidebar_data():
    try:
        total_draws = calculate_statistics(get_numbers_matrix())["total_draws"]
    except Exception:
        total_draws = 0
    return {"sidebar_total_draws": total_draws}


# ==============================
# DASHBOARD PRINCIPAL
# ==============================

@main.route("/")
def index():
    numbers_matrix = get_numbers_matrix()

    stats = calculate_statistics(numbers_matrix)

    sorted_freq = dict(sorted(stats["frequency"].items(), key=lambda x: x[1], reverse=True))
    ranking = list(sorted_freq.keys())

    plays = generate_optimized_plays(numbers_matrix)

    return render_template(
        "dashboard.html",
        frequency=sorted_freq,
        total_draws=stats["total_draws"],
        most_frequent=stats["most_frequent"],
        least_frequent=stats["least_frequent"],
        plays=plays,
        ranking=ranking
    )


# ==============================
# SIMULACION
# ==============================

@main.route("/simulate", methods=["POST"])
def simulate():
    numbers = request.form.get("numbers")
    try:
        user_numbers = parse_numbers(numbers)
    except ValueError as exc:
        return bad_request(str(exc))

    results = monte_carlo_simulation(user_numbers, simulations=20000)

    return render_template("simulation.html", results=results, user_numbers=user_numbers)


# ==============================
# GENERAR JUGADAS
# ==============================

@main.route("/generate")
def generate():
    numbers_matrix = get_numbers_matrix()

    plays = generate_optimized_plays(numbers_matrix)

    return render_template("generate.html", plays=plays)


@main.route("/api/generate_from_manual", methods=["POST"])
def generate_from_manual():
    data = request.get_json(silent=True) or {}
    try:
        manual_play = parse_numbers(data.get("manual_play"), expected_len=14)
    except ValueError as exc:
        return bad_request(str(exc))

    numbers_matrix = get_numbers_matrix()
    if not numbers_matrix:
        return bad_request(tr("no_history"))

    ai_model = get_or_train_ai_model()
    ranking = [item["number"] for item in ai_model["scores"]]

    manual_eval = evaluate_play(manual_play)
    manual_eval["balance_index"] = calculate_balance_index(manual_play, ranking)
    manual_eval["global_confidence"] = calculate_global_confidence(manual_eval)

    # Estimar la opcion de que esta jugada sea la mejor frente a variantes cercanas.
    candidate_scores = []
    all_numbers = set(range(1, 26))
    for _ in range(60):
        candidate = set(manual_play)
        swaps = random.randint(1, 3)
        for _ in range(swaps):
            out_num = random.choice(list(candidate))
            in_num = random.choice(list(all_numbers - candidate))
            candidate.remove(out_num)
            candidate.add(in_num)

        candidate = sorted(candidate)
        evaluated = evaluate_play(candidate)
        evaluated["balance_index"] = calculate_balance_index(candidate, ranking)
        evaluated["global_confidence"] = calculate_global_confidence(evaluated)
        candidate_scores.append(evaluated["global_confidence"])

    better = sum(1 for s in candidate_scores if s > manual_eval["global_confidence"])
    best_probability = round(max(0, (1 - (better / max(1, len(candidate_scores)))) * 100), 2)

    # Generar 3 opciones nuevas desde jugada manual con sesgo a numeros mejor rankeados.
    options = []
    top_pool = set(ranking[:16])
    for _ in range(12):
        candidate = set(manual_play)
        replace_count = random.randint(1, 4)
        for _ in range(replace_count):
            out_num = random.choice(list(candidate))
            preferred = list(top_pool - candidate)
            in_num = random.choice(preferred) if preferred else random.choice(list(all_numbers - candidate))
            candidate.remove(out_num)
            candidate.add(in_num)

        candidate = sorted(candidate)
        evaluated = evaluate_play(candidate)
        evaluated["balance_index"] = calculate_balance_index(candidate, ranking)
        evaluated["global_confidence"] = calculate_global_confidence(evaluated)
        options.append(
            {
                "play": candidate,
                "prob_10_plus": evaluated["prob_10_plus"],
                "prob_11_plus": evaluated["prob_11_plus"],
                "prob_12_plus": evaluated["prob_12_plus"],
                "score": evaluated["score"],
                "global_confidence": evaluated["global_confidence"],
            }
        )

    dedup = {}
    for item in options:
        dedup[tuple(item["play"])] = item
    best_options = sorted(dedup.values(), key=lambda x: x["global_confidence"], reverse=True)[:3]

    return jsonify(
        {
            "manual": {
                "play": manual_play,
                "prob_10_plus": manual_eval["prob_10_plus"],
                "prob_11_plus": manual_eval["prob_11_plus"],
                "prob_12_plus": manual_eval["prob_12_plus"],
                "score": manual_eval["score"],
                "global_confidence": manual_eval["global_confidence"],
                "best_probability": best_probability,
            },
            "options": best_options,
        }
    )


# ==============================
# GUARDAR RESULTADO SIMPLE
# ==============================

@main.route("/save_result", methods=["POST"])
def save_result():
    try:
        play = parse_numbers(request.form.get("play"))
        real_result = parse_numbers(request.form.get("real_result"))
    except ValueError as exc:
        return bad_request(str(exc))

    aciertos = save_play(play, real_result)

    return f"{tr('hits_registered', hits=aciertos)} <br><a href='/'>{tr('back')}</a>"


# ==============================
# API GENERAR JUGADAS
# ==============================

@main.route("/api/generate")
def api_generate():
    numbers_matrix = get_numbers_matrix()

    stats = calculate_statistics(numbers_matrix)
    sorted_freq = dict(sorted(stats["frequency"].items(), key=lambda x: x[1], reverse=True))
    ranking = list(sorted_freq.keys())

    plays = generate_optimized_plays(numbers_matrix)

    return jsonify({
        "plays": plays,
        "ranking": ranking
    })


# ==============================
# API EVALUAR JUGADA (MONTE CARLO)
# ==============================

@main.route("/api/evaluate_play", methods=["POST"])
def api_evaluate_play():
    data = request.get_json(silent=True) or {}
    try:
        play = parse_numbers(data.get("play"))
    except ValueError as exc:
        return bad_request(str(exc))

    results = monte_carlo_simulation(play, simulations=25000)

    return jsonify(results)


# ==============================
# REGISTRO RESULTADO REAL
# ==============================

@main.route("/registro")
def registro():
    return render_template("registro.html")


# ==============================
# SIMULADOR
# ==============================

@main.route("/simulador")
def simulador():
    return render_template("simulador.html")


# ==============================
# HISTORIAL PERSONAL (BD)
# ==============================

@main.route("/historial")
def historial():
    return render_template("historial.html")


# ==============================
# CONFIGURACION
# ==============================

@main.route("/configuracion")
def configuracion():
    return render_template("configuracion.html")


@main.route("/frecuencias")
def frecuencias():
    return render_template("frecuencias.html")


@main.route("/probabilidad")
def probabilidad():
    return render_template("probabilidad.html")


@main.route("/simulacion")
def simulacion():
    return render_template("simulacion.html")


@main.route("/importar")
def importar():
    return render_template("importar.html")


@main.route("/aprendizaje")
def aprendizaje():
    return render_template("aprendizaje.html")


@main.route("/comparacion")
def comparacion():
    return render_template("comparacion.html")


# ==============================
# API COMPARAR RESULTADO REAL
# ==============================

@main.route("/api/compare_result", methods=["POST"])
def compare_result():

    data = request.get_json(silent=True)
    if not data:
        return bad_request(tr("invalid_json"))

    data_date = data.get("date")
    if not data_date:
        return bad_request(tr("date_required"))

    try:
        user_play = parse_numbers(data.get("user_play"), expected_len=14)
        real_result = parse_numbers(data.get("real_result"), expected_len=14)
    except ValueError as exc:
        return bad_request(str(exc))

    hits = list(set(user_play) & set(real_result))
    hit_count = len(hits)
    percentage = round((hit_count / len(user_play)) * 100, 2)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO comparisons (date, user_play, real_result, hit_count, percentage)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data_date,
        ",".join(map(str, user_play)),
        ",".join(map(str, real_result)),
        hit_count,
        percentage
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "hits": hits,
        "hit_count": hit_count,
        "percentage": percentage
    })


@main.route("/api/frecuencias_data")
def frecuencias_data():
    numbers_matrix = get_numbers_matrix()
    stats, sorted_freq, ranking = get_frequency_ranking(numbers_matrix)
    total_draws = max(stats["total_draws"], 1)

    hot_numbers = ranking[:5]
    cold_numbers = ranking[-5:]

    heatmap = []
    for number, count in sorted_freq.items():
        pct = round((count / total_draws) * 100, 1)
        heatmap.append({"number": number, "count": count, "pct": pct})

    hot_rows = [{"number": n, "count": sorted_freq[n], "pct": round((sorted_freq[n] / total_draws) * 100, 1)} for n in hot_numbers]
    cold_rows = [{"number": n, "count": sorted_freq[n], "pct": round((sorted_freq[n] / total_draws) * 100, 1)} for n in cold_numbers]
    pairs = [{"pair": pair, "count": count} for pair, count in top_pairs(numbers_matrix)]

    return jsonify(
        {
            "heatmap": heatmap,
            "hot": hot_rows,
            "cold": cold_rows,
            "pairs": pairs,
            "total_draws": stats["total_draws"],
        }
    )


@main.route("/api/probability_math", methods=["POST"])
def probability_math():
    data = request.get_json(silent=True) or {}
    try:
        total_numbers = int(data.get("total_numbers", 25))
        selected = int(data.get("selected", 14))
    except (TypeError, ValueError):
        return bad_request(tr("invalid_numbers"))

    if total_numbers <= 0 or selected <= 0 or selected > total_numbers:
        return bad_request(tr("params_out_of_range"))

    combinations = math.comb(total_numbers, selected)
    pct = (1 / combinations) * 100

    bars = []
    for sel in range(max(8, selected - 6), min(total_numbers, selected + 2) + 1):
        if sel <= total_numbers:
            bars.append({"label": f"{sel}/{total_numbers}", "value": round(math.log10(math.comb(total_numbers, sel)), 4)})

    combo_formatted = f"{combinations:,}"
    if current_lang() == "es":
        combo_formatted = combo_formatted.replace(",", ".")

    return jsonify(
        {
            "combinations": combinations,
            "probability_percent": pct,
            "inverse_text": tr("inverse_text", value=combo_formatted),
            "bars": bars,
        }
    )


@main.route("/api/ticket_score", methods=["POST"])
def ticket_score():
    data = request.get_json(silent=True) or {}
    try:
        ticket = parse_numbers(data.get("ticket"), expected_len=14)
    except ValueError as exc:
        return bad_request(str(exc))

    numbers_matrix = get_numbers_matrix()
    if not numbers_matrix:
        return bad_request(tr("no_history"))

    hits = [len(set(ticket) & set(draw)) for draw in numbers_matrix]
    avg_hits = round(sum(hits) / len(hits), 2)
    max_hits = max(hits)
    best_index = hits.index(max_hits)

    return jsonify(
        {
            "avg_hits": avg_hits,
            "max_hits": max_hits,
            "best_draw_index": best_index + 1,
            "score_pct": round((avg_hits / 14) * 100, 2),
        }
    )


@main.route("/api/ai_model_summary")
def ai_model_summary():
    return jsonify(get_or_train_ai_model())


@main.route("/api/ai_model_retrain", methods=["POST"])
def ai_model_retrain():
    model = build_ai_model(get_numbers_matrix())
    model_id, trained_at = save_ai_model(model)
    model["id"] = model_id
    model["updated_at"] = datetime.strptime(trained_at, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
    return jsonify(model)


@main.route("/api/compare_tickets", methods=["POST"])
def compare_tickets():
    data = request.get_json(silent=True) or {}
    raw_tickets = data.get("tickets", [])
    if not isinstance(raw_tickets, list) or not raw_tickets:
        return bad_request(tr("tickets_must_list"))

    numbers_matrix = get_numbers_matrix()
    _, sorted_freq, ranking = get_frequency_ranking(numbers_matrix)
    ai_model = get_or_train_ai_model()
    ai_score_map = {item["number"]: item["score"] for item in ai_model["scores"]}

    evaluated = []
    for idx, raw in enumerate(raw_tickets, start=1):
        try:
            ticket = parse_numbers(raw, expected_len=14)
        except ValueError:
            continue

        freq_points = sum(sorted_freq.get(n, 0) for n in ticket)
        avg_rank = round(sum(ranking.index(n) + 1 for n in ticket) / 14, 2)
        ai_score_avg = round(sum(ai_score_map.get(n, 0) for n in ticket) / 14, 2)
        sim = monte_carlo_simulation(ticket, simulations=12000)
        prob_10_plus = round(sum(v for k, v in sim.items() if int(k) >= 10), 2)
        global_score = round((prob_10_plus * 0.5) + (max(0, 26 - avg_rank) * 0.2) + (ai_score_avg * 0.3), 2)

        evaluated.append(
            {
                "name": f"Ticket {idx}",
                "ticket": ticket,
                "freq_points": freq_points,
                "avg_rank": avg_rank,
                "ai_score_avg": ai_score_avg,
                "prob_10_plus": prob_10_plus,
                "global_score": global_score,
            }
        )

    if not evaluated:
        return bad_request(tr("no_valid_tickets"))

    best = max(evaluated, key=lambda x: x["global_score"])
    for item in evaluated:
        item["is_best"] = item["name"] == best["name"]

    return jsonify({"results": evaluated})


@main.route("/api/generate_sample_history", methods=["POST"])
def generate_sample_history():
    data = request.get_json(silent=True) or {}
    try:
        count = int(data.get("count", 20))
    except (TypeError, ValueError):
        return bad_request(tr("invalid_count"))

    if count < 1 or count > 300:
        return bad_request(tr("count_range"))

    conn = get_connection()
    cursor = conn.cursor()

    for i in range(count):
        dt = datetime.now().strftime("%Y-%m-%d")
        user_play = sorted(random.sample(range(1, 26), 14))
        real_result = sorted(random.sample(range(1, 26), 14))
        hit_count = len(set(user_play) & set(real_result))
        percentage = round((hit_count / 14) * 100, 2)

        cursor.execute(
            """
            INSERT INTO comparisons (date, user_play, real_result, hit_count, percentage)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                dt,
                ",".join(map(str, user_play)),
                ",".join(map(str, real_result)),
                hit_count,
                percentage,
            ),
        )

    conn.commit()
    conn.close()

    return jsonify({"status": "success", "inserted": count})


@main.route("/api/delete_result", methods=["POST"])
def delete_result():
    data = request.get_json(silent=True) or {}
    result_id = data.get("id")

    try:
        result_id = int(result_id)
    except (TypeError, ValueError):
        return bad_request(tr("invalid_id"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM comparisons WHERE id = ?", (result_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted == 0:
        return jsonify({"error": tr("record_not_found")}), 404

    return jsonify({"status": "success"})


@main.route("/api/update_result", methods=["POST"])
def update_result():
    data = request.get_json(silent=True) or {}

    try:
        result_id = int(data.get("id"))
    except (TypeError, ValueError):
        return bad_request(tr("invalid_id"))

    data_date = data.get("date")
    if not data_date:
        return bad_request(tr("date_required"))

    try:
        user_play = parse_numbers(data.get("user_play"), expected_len=14)
        real_result = parse_numbers(data.get("real_result"), expected_len=14)
    except ValueError as exc:
        return bad_request(str(exc))

    hits = list(set(user_play) & set(real_result))
    hit_count = len(hits)
    percentage = round((hit_count / len(user_play)) * 100, 2)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE comparisons
        SET date = ?, user_play = ?, real_result = ?, hit_count = ?, percentage = ?
        WHERE id = ?
        """,
        (
            data_date,
            ",".join(map(str, user_play)),
            ",".join(map(str, real_result)),
            hit_count,
            percentage,
            result_id,
        ),
    )
    updated = cursor.rowcount
    conn.commit()
    conn.close()

    if updated == 0:
        return jsonify({"error": tr("record_not_found")}), 404

    return jsonify(
        {
            "status": "success",
            "id": result_id,
            "hit_count": hit_count,
            "percentage": percentage,
        }
    )


@main.route("/api/simulate_multi", methods=["POST"])
def simulate_multi():
    data = request.get_json(silent=True) or {}
    modes = data.get("modes", [])
    manual_play = data.get("manual_play")
    if not isinstance(modes, list):
        return bad_request(tr("modes_must_list"))

    numbers_matrix = get_numbers_matrix()
    # ranking termico
    stats = calculate_statistics(numbers_matrix)
    sorted_freq = dict(sorted(stats["frequency"].items(), key=lambda x: x[1], reverse=True))
    ranking = list(sorted_freq.keys())
    optimized_plays = generate_optimized_plays(numbers_matrix)
    optimized_play = optimized_plays[0]["play"] if optimized_plays else None

    results = []

    for mode in modes:

        if mode == "manual":
            try:
                play = parse_numbers(manual_play)
            except ValueError as exc:
                return bad_request(str(exc))

        elif mode == "optimized":
            if not optimized_play:
                continue
            play = optimized_play

        elif mode in ["historical", "historical_real"]:
            if not numbers_matrix:
                continue
            play = numbers_matrix[-1]

        else:
            continue

        sim_results = monte_carlo_simulation(play, simulations=15000)
        real_hits = [len(set(play) & set(draw)) for draw in numbers_matrix]

        total_sim = sum(sim_results.values())
        avg_sim = round(sum(k * v for k, v in sim_results.items()) / total_sim, 2) if total_sim else 0
        avg_real = round(sum(real_hits) / len(real_hits), 2) if real_hits else 0

        diff = round(abs(avg_sim - avg_real), 2)

        precision = round(100 - (diff * 10), 2)
        if precision < 0:
            precision = 0

        results.append({
            "mode": mode,
            "play": play,
            "avg_sim": avg_sim,
            "avg_real": avg_real,
            "diff": diff,
            "precision": precision,
            "distribution_sim": sim_results
        })
    # Detectar la mas cercana
    if results:
        best = min(results, key=lambda x: x["diff"])
        for r in results:
            r["is_best"] = (r == best)
        # Bloque agregado
        conn = get_connection()
        cursor = conn.cursor()

        for r in results:
            cursor.execute("""
                INSERT INTO strategy_performance (mode, precision, diff, date)
                VALUES (?, ?, ?, ?)
            """, (
                r["mode"],
                r["precision"],
                r["diff"],
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))

        conn.commit()
        conn.close()

    return jsonify({
        "results": results,
        "ranking": ranking
    })
    
@main.route("/api/strategy_ranking")
def strategy_ranking():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT mode,
               AVG(precision) as avg_precision,
               AVG(diff) as avg_diff,
               COUNT(*) as total_runs
        FROM strategy_performance
        GROUP BY mode
        ORDER BY avg_precision DESC
    """)

    ranking = cursor.fetchall()
    conn.close()

    return jsonify([dict(row) for row in ranking])

# ==============================
# EXPORTAR HISTORIAL A EXCEL
# ==============================

@main.route("/api/export_excel")
def export_excel():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM comparisons ORDER BY id DESC")
    rows = cursor.fetchall()

    conn.close()

    def generate():
        yield "Fecha,Jugada,Resultado,Aciertos,Porcentaje\n"
        for row in rows:
            yield f"{row['date']},{row['user_play']},{row['real_result']},{row['hit_count']},{row['percentage']}\n"

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=historial_kino.csv"}
    )


# ==============================
# IMPORTAR HISTORIAL DESDE EXCEL
# ==============================

@main.route("/import_excel", methods=["POST"])
def import_excel():

    if "file" not in request.files:
        return bad_request(tr("file_required"))

    file = request.files["file"]
    if not file.filename:
        return bad_request(tr("file_required"))

    try:
        df = pd.read_excel(file)
    except Exception:
        return bad_request(tr("excel_read_error"))

    required_columns = {"date", "user_play", "real_result", "hit_count", "percentage"}
    if not required_columns.issubset(df.columns):
        return bad_request(tr("excel_columns_error"))

    conn = get_connection()
    cursor = conn.cursor()

    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO comparisons (date, user_play, real_result, hit_count, percentage)
            VALUES (?, ?, ?, ?, ?)
        """, (
            row["date"],
            row["user_play"],
            row["real_result"],
            row["hit_count"],
            row["percentage"]
        ))

    conn.commit()
    conn.close()

    return f"{tr('import_ok')} <br><a href='/registro'>{tr('back')}</a>"

@main.route("/api/get_history")
def get_history():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM comparisons ORDER BY id DESC")
    rows = cursor.fetchall()

    conn.close()

    result = []
    for row in rows:
        result.append({
            "id": row["id"],
            "date": row["date"],
            "user_play": row["user_play"],
            "real_result": row["real_result"],
            "hit_count": row["hit_count"],
            "percentage": row["percentage"]
        })

    return jsonify(result)


@main.route("/api/draw_history")
def draw_history():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM draw_history ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        result.append(
            {
                "id": row["id"],
                "date": row["date"],
                "numbers": row["numbers"],
                "total_sum": row["total_sum"],
            }
        )
    return jsonify(result)


@main.route("/api/draw_history/add", methods=["POST"])
def add_draw_history():
    data = request.get_json(silent=True) or {}
    date_value = data.get("date")
    if not date_value:
        return bad_request(tr("date_required"))

    try:
        numbers = parse_numbers(data.get("numbers"), expected_len=14)
    except ValueError as exc:
        return bad_request(str(exc))

    total_sum = sum(numbers)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO draw_history (date, numbers, total_sum)
        VALUES (?, ?, ?)
        """,
        (date_value, ",".join(map(str, numbers)), total_sum),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify(
        {
            "status": "success",
            "id": new_id,
            "date": date_value,
            "numbers": numbers,
            "total_sum": total_sum,
        }
    )


@main.route("/api/draw_history/delete", methods=["POST"])
def delete_draw_history():
    data = request.get_json(silent=True) or {}
    try:
        row_id = int(data.get("id"))
    except (TypeError, ValueError):
        return bad_request(tr("invalid_id"))

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM draw_history WHERE id = ?", (row_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted == 0:
        return jsonify({"error": tr("record_not_found")}), 404
    return jsonify({"status": "success"})


@main.route("/api/draw_history/clear", methods=["POST"])
def clear_draw_history():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM draw_history")
    conn.commit()
    conn.close()
    return jsonify({"status": "success"})

