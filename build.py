import os
import shutil

import jinja2

from models import load_all_peladas
from stats import compute_pelada_stats, compute_aggregate_stats, filter_peladas

DATA_DIR = "data"
OUTPUT_DIR = "output"
TEMPLATE_DIR = "templates"
STATIC_DIR = "static"
ROOT_BASE_URL = "."      # for pages at root level (index.html, stats.html)
PELADA_BASE_URL = ".."   # for pages inside pelada/ subdirectory


def build():
    peladas = load_all_peladas(DATA_DIR)
    peladas.sort(key=lambda p: p.date, reverse=True)

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(TEMPLATE_DIR))

    # Clean output
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)
    os.makedirs(os.path.join(OUTPUT_DIR, "pelada"), exist_ok=True)

    # Copy static files
    shutil.copytree(STATIC_DIR, os.path.join(OUTPUT_DIR, "static"))

    # Compute stats
    latest = peladas[0] if peladas else None
    latest_stats = compute_pelada_stats(latest) if latest else None

    # Aggregate stats for each period
    aggregate = {}
    for period in ("mensal", "anual", "total"):
        filtered = filter_peladas(peladas, period)
        aggregate[period] = compute_aggregate_stats(filtered)

    # Compute stats for each pelada (for the list table)
    peladas_with_stats = [
        {"pelada": pelada, "stats": compute_pelada_stats(pelada)}
        for pelada in peladas
    ]

    # Render index
    template = env.get_template("index.html")
    html = template.render(
        peladas_with_stats=peladas_with_stats,
        latest=latest,
        latest_stats=latest_stats,
        active_tab="peladas",
        base_url=ROOT_BASE_URL,
    )
    with open(os.path.join(OUTPUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    # Render each pelada
    template = env.get_template("pelada.html")
    for pelada in peladas:
        stats = compute_pelada_stats(pelada)
        html = template.render(
            pelada=pelada,
            stats=stats,
            active_tab="peladas",
            base_url=PELADA_BASE_URL,
        )
        path = os.path.join(OUTPUT_DIR, "pelada", f"{pelada.date}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    # Render stats page
    template = env.get_template("stats.html")
    html = template.render(
        aggregate=aggregate,
        active_tab="stats",
        base_url=ROOT_BASE_URL,
    )
    with open(os.path.join(OUTPUT_DIR, "stats.html"), "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Site gerado em {OUTPUT_DIR}/ com {len(peladas)} pelada(s).")


if __name__ == "__main__":
    build()
