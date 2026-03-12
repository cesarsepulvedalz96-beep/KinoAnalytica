import os

import pandas as pd

from app.paths import ensure_runtime_file

DATA_PATH = ensure_runtime_file(os.path.join("app", "data", "kino_historico.csv"))


def load_history():
    return pd.read_csv(DATA_PATH)


def extract_numbers(df):
    numbers_matrix = []

    for _, row in df.iterrows():
        row_numbers = []

        for value in row:
            # Convertir a numero si es posible.
            try:
                num = int(value)
            except (TypeError, ValueError):
                continue

            if 1 <= num <= 25:
                row_numbers.append(num)

        # Solo guardar filas con exactamente 14 numeros.
        if len(row_numbers) == 14:
            numbers_matrix.append(row_numbers)

    return numbers_matrix
