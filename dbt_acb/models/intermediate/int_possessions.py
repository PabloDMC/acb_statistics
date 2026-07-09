import pandas as pd

PT_FT_MADE = 92
PT_2PM = 93
PT_3PM = 94
PT_DUNK = 100

PT_FT_MISS = 96
PT_2PMISS = 97
PT_3PMISS = 98
PT_DUNKMISS = 533

PT_OREB = 101
PT_DREB = 104

PT_TURNOVER = 106
PT_OFFENSIVE_FOUL = 109

PT_JUMP_WON = 178

PT_QEND = 116


MADE_FG = {
    PT_2PM,
    PT_3PM,
    PT_DUNK,
}

MISSED_FG = {
    PT_2PMISS,
    PT_3PMISS,
    PT_DUNKMISS,
}

FT_EVENTS = {
    PT_FT_MADE,
    PT_FT_MISS,
}

FIRST_POSSESSION_EVENTS = {

    *MADE_FG,
    *MISSED_FG,

    PT_FT_MADE,
    PT_FT_MISS,

    PT_OREB,
    PT_DREB,

    PT_TURNOVER,

    PT_OFFENSIVE_FOUL,
}

def opposite_team(
    team,
    teams,
):

    if team == teams[0]:
        return teams[1]

    return teams[0]

def first_team_of_period(
    q_df,
    quarter,
):

    ###############################################################
    # Primer cuarto
    ###############################################################

    if quarter == 1:

        jump = q_df.loc[
            q_df.play_type_id == PT_JUMP_WON
        ]

        if not jump.empty:
            return jump.iloc[0].team_id

    ###############################################################
    # Resto de cuartos
    ###############################################################

    first = q_df.loc[
        q_df.play_type_id.isin(
            FIRST_POSSESSION_EVENTS
        )
    ]

    if first.empty:
        return None

    return first.iloc[0].team_id

def possession_change(
    row,
    next_row,
    teams,
):

    pt = row.play_type_id

    ###############################################################
    # Canasta de campo
    ###############################################################

    if pt in MADE_FG:

        ###########################################################
        # ¿Hay un TL inmediatamente después del mismo equipo?
        # -> 2+1
        ###########################################################

        if (
            next_row is not None
            and next_row.team_id == row.team_id
            and next_row.play_type_id in FT_EVENTS
        ):
            return None

        return opposite_team(
            row.team_id,
            teams,
        )

    ###############################################################
    # Pérdida
    ###############################################################

    if pt == PT_TURNOVER and row.player_id is not None:

        return opposite_team(
            row.team_id,
            teams,
        )

    ###############################################################
    # Rebote defensivo
    ###############################################################

    if pt == PT_DREB:

        return row.team_id

    ###############################################################
    # Tiros libres
    ###############################################################

    if pt in FT_EVENTS:

        ###########################################################
        # Quedan tiros libres
        ###########################################################

        if (
            next_row is not None
            and next_row.play_type_id in FT_EVENTS
            and next_row.team_id == row.team_id
        ):
            return None

        ###########################################################
        # Último TL anotado
        ###########################################################

        if pt == PT_FT_MADE:

            return opposite_team(
                row.team_id,
                teams,
            )

        ###########################################################
        # Último TL fallado
        ###########################################################

        if (
            next_row is not None
            and next_row.play_type_id == PT_DREB
        ):

            #######################################################
            # NO cambiar aquí.
            # Esperamos al rebote defensivo.
            #######################################################

            return None

        ###########################################################
        # Rebote ofensivo u otra cosa
        ###########################################################

        return None

    ###############################################################
    # Todo lo demás
    ###############################################################

    return None

def build_possessions(df):

    results = []

    possession_id = 1

    ###############################################################
    # Partido
    ###############################################################

    for match_id, match_df in df.groupby(
        "match_id",
        sort=False,
    ):

        ###########################################################
        # Cuartos
        ###########################################################

        for quarter, q_df in match_df.groupby(
            "quarter",
            sort=False,
        ):

            q_df = (
                q_df
                .sort_values("event_order")
                .reset_index(drop=True)
            )

            teams = list(
                q_df.team_id.dropna().unique()
            )

            if len(teams) != 2:
                continue

            ###########################################################
            # Equipo con la primera posesión del cuarto
            ###########################################################

            current_team = first_team_of_period(
                q_df,
                quarter,
            )

            if current_team is None:
                continue

            ###########################################################
            # Inicio de posesión
            ###########################################################

            start_time = q_df.iloc[0].seconds_remaining

            score_h_start = q_df.iloc[0].score_home
            score_a_start = q_df.iloc[0].score_away

            ###########################################################
            # Recorrer eventos
            ###########################################################

            for i in range(len(q_df)):

                row = q_df.iloc[i]

                next_row = (
                    q_df.iloc[i + 1]
                    if i < len(q_df) - 1
                    else None
                )

                #######################################################
                # ¿Hay cambio de posesión?
                #######################################################

                new_team = possession_change(
                    row,
                    next_row,
                    teams,
                )

                if new_team is None:
                    continue

                #######################################################
                # Cerrar posesión
                #######################################################

                results.append(
                    {
                        "match_id": match_id,
                        "quarter": quarter,
                        "possession_id": possession_id,
                        "team_id": current_team,
                        "start_time": start_time,
                        "end_time": row.seconds_remaining,
                        "score_h_start": score_h_start,
                        "score_h_end": row.score_home,
                        "score_a_start": score_a_start,
                        "score_a_end": row.score_away,
                        "end_reason": row.play_type_id,
                    }
                )

                possession_id += 1

                #######################################################
                # Abrir siguiente posesión
                #######################################################

                current_team = new_team

                start_time = row.seconds_remaining

                score_h_start = row.score_home
                score_a_start = row.score_away

            ###########################################################
            # Última posesión del cuarto
            ###########################################################

            end_row = q_df.iloc[-1]

            if start_time != 0:

                results.append(
                    {
                        "match_id": match_id,
                        "quarter": quarter,
                        "possession_id": possession_id,
                        "team_id": current_team,
                        "start_time": start_time,
                        "end_time": 0,
                        "score_h_start": score_h_start,
                        "score_h_end": end_row.score_home,
                        "score_a_start": score_a_start,
                        "score_a_end": end_row.score_away,
                        "end_reason": 116,
                    }
                )

                possession_id += 1

    ###############################################################
    # Resultado
    ###############################################################

    return pd.DataFrame(results)

def model(dbt, session):

    dbt.config(
        materialized="incremental",
        schema="intermediate",
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

    return build_possessions(df)