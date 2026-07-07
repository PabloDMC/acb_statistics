import pandas as pd

PT_STARTING_LINEUP = 599
PT_SUB_IN = 112
PT_SUB_OUT = 115

def build_lineups(df):

    results = []
    stint_id = 1

    current_lineups = {}

    EVENTS_SUB = {PT_SUB_IN, PT_SUB_OUT}

    for (match_id, quarter), q_df in df.groupby(
        ["match_id", "quarter"],
        sort=False,
    ):

        ###############################################################
        # PBP en orden cronológico real
        ###############################################################

        q_df = (
            q_df
            .sort_values("event_order")
            .reset_index(drop=True)
        )

        start_time = q_df.iloc[0].seconds_remaining
        end_row = q_df.iloc[-1]

        ###############################################################
        # Equipos del cuarto
        ###############################################################

        teams = [
            t
            for t in q_df.team_id.dropna().unique()
        ]

        if len(teams) != 2:
            continue

        ###############################################################
        # Quintetos iniciales
        ###############################################################

        current = {}
        stint_start = {}
        score_h_start = {}
        score_a_start = {}

        for team in teams:

            if quarter == 1:

                lineup = set(
                    map(
                        int,
                        q_df.loc[
                            (q_df.team_id == team)
                            & (
                                q_df.play_type_id
                                == PT_STARTING_LINEUP
                            ),
                            "player_id",
                        ],
                    )
                )

            else:

                lineup = current_lineups.get(
                    team,
                    set(),
                ).copy()

            current[team] = lineup

            stint_start[team] = start_time
            score_h_start[team] = q_df.iloc[0].score_home
            score_a_start[team] = q_df.iloc[0].score_away

        ###############################################################
        # Recorrer el PBP completo
        ###############################################################

        i = 0

        while i < len(q_df):

            row = q_df.iloc[i]

            ###########################################################
            # No es sustitución
            ###########################################################

            if row.play_type_id not in EVENTS_SUB:
                i += 1
                continue

            ###########################################################
            # Inicio de un bloque de sustituciones
            ###########################################################

            block_team = row.team_id
            block_second = row.seconds_remaining

            block = []

            while (
                i < len(q_df)
                and q_df.iloc[i].play_type_id in EVENTS_SUB
                and q_df.iloc[i].team_id == block_team
                and q_df.iloc[i].seconds_remaining == block_second
            ):

                block.append(q_df.iloc[i])

                i += 1

            ###########################################################
            # Cerrar el stint SOLO del equipo que cambia
            ###########################################################

            first = block[0]

            results.append(
                {
                    "match_id": match_id,
                    "team_id": block_team,
                    "stint_id": stint_id,
                    "quarter": quarter,
                    "start_time": stint_start[block_team],
                    "end_time": first.seconds_remaining,
                    "score_h_start": score_h_start[block_team],
                    "score_h_end": first.score_home,
                    "score_a_start": score_a_start[block_team],
                    "score_a_end": first.score_away,
                    "player_ids": tuple(
                        sorted(current[block_team])
                    ),
                }
            )

            stint_id += 1

            ###########################################################
            # Aplicar el bloque EXACTAMENTE en orden PBP
            ###########################################################

            for event in block:

                player = int(event.player_id)

                if event.play_type_id == PT_SUB_OUT:

                    current[event.team_id].discard(player)

                else:

                    current[event.team_id].add(player)

            ###########################################################
            # Abrir el siguiente stint SOLO para ese equipo
            ###########################################################

            stint_start[block_team] = first.seconds_remaining
            score_h_start[block_team] = first.score_home
            score_a_start[block_team] = first.score_away

        ###############################################################
        # Cerrar último stint del cuarto
        ###############################################################

        for team in teams:

            results.append(
                {
                    "match_id": match_id,
                    "team_id": team,
                    "stint_id": stint_id,
                    "quarter": quarter,
                    "start_time": stint_start[team],
                    "end_time": 0,
                    "score_h_start": score_h_start[team],
                    "score_h_end": end_row.score_home,
                    "score_a_start": score_a_start[team],
                    "score_a_end": end_row.score_away,
                    "player_ids": tuple(
                        sorted(current[team])
                    ),
                }
            )

            stint_id += 1

            current_lineups[team] = current[team].copy()

    return pd.DataFrame(results)
    
def model(dbt, session):

    dbt.config(
        materialized="incremental",
        schema="marts",
        tags=["acb_analytics"],
    )

    df = dbt.ref("int_play_by_play").df()

    if dbt.is_incremental:

        existing = (
            session.table(str(dbt.this))
            .select("match_id")
            .distinct()
        )

        df = df.join(
            existing,
            on="match_id",
            how="left_anti",
        )

    return build_lineups(df)