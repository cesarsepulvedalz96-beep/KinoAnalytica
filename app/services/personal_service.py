import json
import os
from datetime import datetime

from app.paths import ensure_runtime_file

DATA_PATH = ensure_runtime_file(os.path.join("app", "data", "personal_history.json"), seed_from_resource=True)


def save_play(play, real_result, category="Kino"):
    aciertos = len(set(play) & set(real_result))

    record = {
        "fecha": datetime.now().strftime("%Y-%m-%d"),
        "categoria": category,
        "jugada": play,
        "resultado_real": real_result,
        "aciertos": aciertos,
    }

    data = []
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            try:
                loaded = json.load(f)
            except json.JSONDecodeError:
                loaded = []

        if isinstance(loaded, list):
            data = loaded

    data.append(record)

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    return aciertos
