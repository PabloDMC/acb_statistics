"""
Definición de columnas de las tablas de estadísticas (nombre en la API -> etiqueta y formato),
agrupadas como en Basketball Reference. Los porcentajes de tiro llegan en 0-1 y se muestran en
0-100; las avanzadas ya llegan en 0-100.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

# (clave en stats, etiqueta, tipo) — tipo: "n" contable, "r" tasa/rating, "p" proporción 0-1 -> %, "a" ya en %
PLAYER_GROUPS: dict[str, list[tuple[str, str, str]]] = {
    "Básicas": [
        ("points", "Pts", "n"), ("total_rebounds", "Reb", "n"), ("off_rebounds", "RO", "n"),
        ("def_rebounds", "RD", "n"), ("assists", "Ast", "n"), ("steals", "Rob", "n"),
        ("blocks", "Tap", "n"), ("turnovers", "Pér", "n"), ("personal_fouls", "FP", "n"),
        ("fouls_drawn", "FR", "n"), ("plus_minus", "+/-", "n"), ("rating", "Val", "n"),
    ],
    "Tiro": [
        ("field_goals_made", "TC", "n"), ("field_goals_attempted", "TCI", "n"), ("field_goals_pct", "TC%", "p"),
        ("two_pointers_made", "T2", "n"), ("two_pointers_attempted", "T2I", "n"), ("two_pointers_pct", "T2%", "p"),
        ("three_pointers_made", "T3", "n"), ("three_pointers_attempted", "T3I", "n"), ("three_pointers_pct", "T3%", "p"),
        ("free_throws_made", "TL", "n"), ("free_throws_attempted", "TLI", "n"), ("free_throws_pct", "TL%", "p"),
        ("effective_field_goals_pct", "eFG%", "p"), ("true_shooting_pct", "TS%", "p"),
    ],
    "Avanzadas": [
        ("usage_pct", "USG%", "a"), ("assist_pct", "AST%", "a"), ("turnover_pct", "TOV%", "a"),
        ("off_rebound_pct", "ORB%", "a"), ("def_rebound_pct", "DRB%", "a"), ("total_rebound_pct", "TRB%", "a"),
        ("steal_pct", "STL%", "a"), ("block_pct", "BLK%", "a"), ("true_shooting_pct", "TS%", "p"),
    ],
    "Impacto": [
        ("offensive_rating", "ORtg", "r"), ("defensive_rating", "DRtg", "r"), ("net_rating", "Net", "r"),
        ("onoff_net_rating", "On/Off", "r"), ("offensive_possessions", "Pos. ataque", "n"),
    ],
}

TEAM_GROUPS: dict[str, list[tuple[str, str, str]]] = {
    "Básicas": [
        ("points", "Pts", "n"), ("opponent_points", "Pts rival", "n"), ("total_rebounds", "Reb", "n"),
        ("off_rebounds", "RO", "n"), ("def_rebounds", "RD", "n"), ("assists", "Ast", "n"),
        ("steals", "Rob", "n"), ("blocks", "Tap", "n"), ("turnovers", "Pér", "n"),
        ("personal_fouls", "FP", "n"), ("rating", "Val", "n"),
    ],
    "Tiro": [
        ("field_goals_pct", "TC%", "p"), ("two_pointers_pct", "T2%", "p"), ("three_pointers_attempted", "T3I", "n"),
        ("three_pointers_pct", "T3%", "p"), ("free_throws_attempted", "TLI", "n"), ("free_throws_pct", "TL%", "p"),
        ("effective_field_goals_pct", "eFG%", "p"), ("true_shooting_pct", "TS%", "p"),
    ],
    "Rival": [
        ("opponent_points", "Pts", "n"), ("opp_field_goals_made", "TC", "n"), ("opp_field_goals_attempted", "TCI", "n"),
        ("opp_three_pointers_made", "T3", "n"), ("opp_three_pointers_attempted", "T3I", "n"),
        ("opp_free_throws_attempted", "TLI", "n"), ("opp_total_rebounds", "Reb", "n"),
        ("opp_off_rebounds", "RO", "n"), ("opp_assists", "Ast", "n"), ("opp_turnovers", "Pér", "n"),
        ("opp_steals", "Rob", "n"), ("opp_blocks", "Tap", "n"),
    ],
    "Four factors": [
        ("four_factors_efg_pct", "eFG%", "p"), ("four_factors_tov_pct", "TOV%", "p"),
        ("four_factors_orb_pct", "ORB%", "p"), ("four_factors_ft_rate", "TL/TCI", "p"),
        ("opp_four_factors_efg_pct", "eFG% rival", "p"), ("opp_four_factors_tov_pct", "TOV% rival", "p"),
        ("opp_four_factors_orb_pct", "ORB% rival", "p"), ("opp_four_factors_ft_rate", "TL/TCI rival", "p"),
    ],
    "Ratings": [
        ("offensive_rating", "ORtg", "r"), ("defensive_rating", "DRtg", "r"),
        ("net_rating", "Net", "r"), ("possessions_per_game", "Ritmo", "r"),
    ],
}


def build(
    items: list[dict],
    spec: list[tuple[str, str, str]],
    base: dict[str, callable],
    integer_counts: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """DataFrame con las columnas base (identificación) + las del grupo, y su column_config.
    `integer_counts`: las contables sin decimales (tablas de totales)."""
    rows = []
    for it in items:
        row = {label: fn(it) for label, fn in base.items()}
        for key, label, kind in spec:
            v = it["stats"].get(key)
            if v is not None and kind == "p":
                v = 100 * v
            row[label] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    config = {
        label: st.column_config.NumberColumn(label, format="%d" if (kind == "n" and integer_counts) else "%.1f")
        for key, label, kind in spec
    }
    return df, config
