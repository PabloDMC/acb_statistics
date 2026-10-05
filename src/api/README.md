# ACB Statistics API

API REST (FastAPI + DuckDB) que sirve el modelo analítico de ACB Statistics
(staging → intermediate → marts) con un contrato pensado para consumo
(Streamlit u otro cliente), no para exponer el warehouse tal cual.

## ⚠️ Aviso importante sobre el esquema

Este código se ha escrito **sin poder abrir tu `.duckdb` real** (el entorno
en el que lo generé no tenía red ni el paquete `duckdb` instalado). Los
nombres de tabla/columna en `app/repositories/*.py` están **asumidos** a
partir de la descripción detallada que me diste del proyecto.

Antes de dar por bueno el código:

```bash
pip install duckdb
python scripts/inspect_schema.py /ruta/a/acb_analytics.duckdb
```

Esto vuelca el esquema real de `main_marts` y `main_reference`. Pásame la
salida (o ajústalo tú mismo) y corregimos los `SELECT` en
`app/repositories/*.py` — es la única capa que tocaría, ya que schemas,
servicios y routers no dependen de los nombres físicos de columna.

Puntos que casi seguro necesitan ajuste:
- Nombre exacto de la tabla/columnas de `dim_players` (asumí `full_name`,
  `birth_date`, `nationality`, `position`, `height_cm`).
- Si `dim_teams` tiene `club_name` como columna propia o si existe una
  `dim_clubs` separada.
- Dónde viven exactamente las métricas on-court/on-off (asumí que están en
  `agg_player_totals`; si tienes una tabla separada, cambia el `FROM` en
  `player_repo.get_impact`).
- Tipo/estructura de `player_ids` en `fact_lineups` / `agg_lineup_combinations`
  (asumí `LIST` de DuckDB, uso `list_contains`).

## Arquitectura

```
app/
├── core/
│   ├── config.py        # settings vía variables de entorno (.env)
│   ├── db.py             # conexión DuckDB read-only + dependencia get_db()
│   ├── serialization.py  # numpy/duckdb -> tipos JSON-safe (una sola vez)
│   └── exceptions.py     # ResourceNotFoundError -> 404 consistente
├── schemas/               # CONTRATO de la API (Pydantic). No es 1:1 con dbt.
├── repositories/          # Todo el SQL vive aquí, aislado por recurso.
├── services/               # Lógica de negocio + aplanado -> anidado.
└── routers/                # Capa fina: parsea query params, llama al servicio.
```

Principio de diseño (como comentabas en el resumen del proyecto): la API
esconde `edition_id`/`competition_id`/`club_id`/`team_id` internamente y
expone hacia fuera objetos `{id, name}` (`NamedRef`) y contexto legible
(`CompetitionContext`, `ClubTeamRef`). Cambiar un nombre de columna en dbt
nunca debería romper el JSON que recibe Streamlit; solo tocas el
repositorio correspondiente.

## Cómo correrlo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edita ACB_DUCKDB_PATH para apuntar a tu fichero real

uvicorn app.main:app --reload
```

Documentación interactiva en `http://localhost:8000/docs`.

## Endpoints

### Players
- `GET /api/v1/players?q=&edition_id=&competition_id=&club_id=&team_id=&limit=&offset=&sort=`
- `GET /api/v1/players/{id}` — info básica
- `GET /api/v1/players/{id}/profile` — **endpoint compuesto** para la página
  de jugador (perfil + totales + shooting + impacto + top lineups) en una
  sola llamada
- `GET /api/v1/players/{id}/totals`
- `GET /api/v1/players/{id}/games` — partido a partido, paginado
- `GET /api/v1/players/{id}/shooting` — incluye desglose por zonas
- `GET /api/v1/players/{id}/impact` — on-court / on-off
- `GET /api/v1/players/{id}/lineups` — quintetos en los que participa

### Teams
- `GET /api/v1/teams?q=&...filtros...`
- `GET /api/v1/teams/{id}/totals`
- `GET /api/v1/teams/{id}/games`
- `GET /api/v1/teams/{id}/lineups?combination_size=2..5` — combinaciones de
  jugadores (parejas, tríos, quintetos...)

### Matches
- `GET /api/v1/matches?...filtros...`
- `GET /api/v1/matches/{id}`
- `GET /api/v1/matches/{id}/shots?team_id=&player_id=` — datos para shot chart
- `GET /api/v1/matches/{id}/lineups` — stints de quinteto del partido

### Leaderboards
- `GET /api/v1/leaderboards/metrics` — métricas disponibles (para que
  Streamlit monte un selector sin hardcodear)
- `GET /api/v1/leaderboards/players?metric=points&...filtros...`
- `GET /api/v1/leaderboards/teams?metric=net_rating&...filtros...`

Todos los endpoints de listado aceptan los filtros comunes
(`edition_id`, `competition_id`, `competition_phase`, `club_id`, `team_id`)
y, donde aplica, paginación (`limit`, `offset`, `sort`).

## Qué falta a propósito (por ahora)

Según lo que comentabas: sin auth, sin Docker, sin ORM, sin caché, todavía.
El `CORSMiddleware` está abierto a `*` — ciérralo a tu origen de Streamlit
antes de exponer esto fuera de tu máquina.

## Siguientes pasos sugeridos

1. Ejecutar `scripts/inspect_schema.py` y ajustar `app/repositories/*.py`.
2. Levantar la API y probar `/docs` contra tu base real, endpoint a endpoint.
3. Añadir `Matches`/`Leaderboards` que falten a tu API actual (ya están aquí).
4. Empezar Streamlit consumiendo `/players/{id}/profile` para la página de
   jugador, y `/matches/{id}/shots` para el primer shot chart.
5. Cuando el contrato esté estable: Docker, caché (si algún endpoint es
   lento), y auth si vas a exponerlo públicamente.

---

## Actualización: código corregido contra el esquema real

Después de que me pasaras la salida de `scripts/inspect_schema.py`, corregí
`app/repositories/*.py`, `app/services/*.py` y parte de `app/schemas/*.py`
contra los nombres reales de tabla/columna. Los 500 que veías eran, casi
con toda seguridad, columnas/tablas inexistentes (`dim_players`, `team_name`,
`points_for`, etc.) — deberían estar resueltos ahora.

Cambios de fondo (no solo de nombre):

- **No existe `dim_players`**: la ficha de un jugador se resuelve tomando la
  fila más reciente de `dim_rosters` para ese `player_id`. Se añadió
  `app/repositories/common_repo.py` para resolver nombres de jugador en
  lote (se usa en lineups, shot charts y leaderboards, donde antes asumía
  columnas `player_name`/`player_ids` con nombres que no existen).
- **No hay nombre de club en ningún sitio**: `club.name` viaja como `null`
  a propósito (ver más abajo, sección de dbt).
- `agg_player_totals` / `agg_team_totals` no tienen `club_id` propio: se
  añadió un JOIN a `dim_teams` (por `team_id` + `edition_id`, ya que
  `dim_teams` está particionada por edición) para poder filtrar por club.
- `wins`/`losses` de equipo no están materializados en `agg_team_totals`:
  se derivan con una segunda consulta de agregación sobre
  `fact_team_games` (`points > opponent_points`).
- `app/core/config.py` ya no usa una ruta relativa "de facto hardcodeada":
  calcula la raíz del repo a partir de la ubicación del propio fichero y
  lee el `.env` de la raíz (el mismo que ya usa tu ingesta), así que
  `ACB_DUCKDB_PATH` (o cualquier otra `ACB_*`) se respeta venga de donde
  venga el proceso.

### Recomendaciones para la capa dbt (no para la API)

1. **`dim_clubs`**: hoy "club" es solo un id. Si quieres que la distinción
   club/team sea usable de verdad en producto, hace falta una tabla
   pequeña `club_id -> nombre_canónico` en `main_marts`. Es la pieza que
   más echo en falta del modelo actual.
2. **Bio de jugador**: si la API de la ACB expone nacimiento/nacionalidad/
   posición/altura en algún endpoint de jugador que aún no ingieres, vale
   la pena añadirlo — es justo lo que hace única a una página estilo
   Basketball-Reference frente a una tabla de números.
3. **`is_win` / resultado de partido**: hoy se deriva en cada consulta
   (`points > opponent_points`). Si vas a usarlo mucho (leaderboards de
   rachas, standings), materializarlo en `fact_team_games` ahorra ese
   cálculo repetido.
4. **Nombres de jugador en `fact_lineups` / `agg_lineup_combinations`**:
   ahora mismo la API resuelve nombres con una consulta extra en Python
   (`common_repo.player_names_batch`). Funciona, pero si estos endpoints
   se vuelven un cuello de botella, sería más barato desnormalizar un
   array de nombres directamente en dbt (ya tienes el patrón con
   `list_transform` para arrays en DuckDB).
5. Las tablas `*__dbt_backup` (`fact_lineups__dbt_backup`,
   `fact_shots__dbt_backup`, `fact_possessions__dbt_backup`) son restos de
   un `dbt run` — la API no las toca, pero merece la pena limpiarlas o
   excluirlas del esquema si no las necesitas.

---

## v3: fixes y funcionalidad nueva

### Bug corregido
- `GET /teams`: el `ORDER BY` referenciaba una columna del `FROM` interior
  (`full_name`) en vez de la del `SELECT` exterior (`name`) → `BinderException`.
  Corregido.
- Los JOIN a `dim_teams` por `(team_id, edition_id)` podían duplicar fila si
  una edición tiene varias competiciones (Liga+Copa): se añadió
  `competition_id` al join en todos los repositorios.

### Nuevo: `/players/{id}/shots`
Lanzamientos de **toda la temporada** (sin agregar, uno por lanzamiento),
filtrable por los filtros comunes. Para un partido concreto sigue existiendo
`/matches/{id}/shots`. Pensado para construir un shot chart de jugador a lo
largo de una temporada/competición, no solo de un partido.

### Nuevo: recurso `Clubs`
`GET /clubs/{club_id}/teams` — trayectoria histórica: qué `team_id` tuvo ese
club en cada edición/competición. Responde a tu pregunta de "filtrar por
club_id como eje principal": ya puedes pasar `club_id` directamente a
`/teams`, `/teams/{id}/totals`, `/leaderboards/*`, etc. (se traduce a un JOIN
contra `dim_teams` donde hace falta). Este endpoint nuevo es para cuando
necesitas ir de "club" a "qué team_id uso esta temporada" antes de llamar a
un endpoint que sí pide `team_id`.

### Nuevo: `scope` y `per` en leaderboards
`GET /leaderboards/players?metric=points&scope=career&per=per_game`

- **`scope=season`** (por defecto, comportamiento de antes): cada fila es
  jugador+edición+competición+fase. Si no filtras `edition_id`, esto ya es
  "mejor marca histórica en una sola temporada" (al estilo "single-season
  leaders" de Basketball-Reference).
- **`scope=career`**: agrega (`SUM`, o fórmula ponderada para porcentajes/
  ratings) todas las filas que cumplan tus filtros, agrupando solo por
  jugador. Es la carrera completa (o la carrera dentro de un competition_id,
  si lo filtras).
- **`per`**: `total` (por defecto), `per_game`, `per_100_poss`, `per_40_min`.
  Solo válido sobre métricas contables (`points`, `assists`, `rebounds`,
  `steals`, `blocks`, `rating`) — sobre un porcentaje o un rating no tiene
  sentido (ya son una tasa) y el endpoint devuelve 422 si lo intentas.
- Nota honesta sobre `onoff_net_rating` en `scope=career`: se calcula como
  media ponderada por posesiones de los on/off de cada fila, no reconstruido
  desde cero a partir de lineups. Es razonable para ordenar un ranking, no
  es un dato de precisión matemática exacta.

Falta por hacer (no implementado todavía, dímelo si lo quieres ya):
leaderboards por zona de tiro (`agg_player_shooting_zones`), y `scope=career`
con filtro de club_id a través de distintos `team_id` del mismo club (hoy el
`GROUP BY` de carrera es por jugador sin filtrar club, habría que añadir el
JOIN de club también ahí si lo necesitas).

### Respuestas a tus preguntas de diseño

- **¿Materializar `competition_phase` en `dim_matches`?** Sí, te lo
  recomiendo. Ahora mismo la API la deriva con un JOIN a `fact_team_games`
  agrupado por `match_id` cada vez que se pide — funciona, pero es trabajo
  repetido que dbt podría hacer una vez. Es una columna barata de añadir en
  `int_matches`/`dim_matches` si ya tienes la fase en algún punto anterior
  del pipeline.
- **¿Definir un nombre de club?** Sí — ver el punto del `dim_clubs` que ya
  comentamos. Es la única pieza de datos que de verdad falta para que
  "club" sea algo más que un id en toda la API.
- **"Solo devuelve la última temporada", ¿está bien?** Ya no debería pasar
  en ningún endpoint de listado (`/totals`, `/shooting`, `/impact`,
  `/lineups`, `/games`): todos devuelven **todas** las filas que matcheen
  filtros. El único sitio donde es intencional es `/players/{id}/profile`,
  que coge la temporada más reciente a propósito porque es un resumen tipo
  "ficha actual", no un listado.

### Ideas adicionales para la API (no implementadas, propuestas)

- **`/standings`** — clasificación de una edición/competición/fase (derivable
  de `fact_team_games`: victorias, derrotas, % victorias, diferencia de
  puntos). Muy pedido en cualquier app de liga.
- **`/teams/{id}/roster`** — plantilla de un equipo en una edición concreta
  (ya tienes los datos en `dim_rosters`, solo falta el endpoint).
  **`/players/{id}/game-highs`** — ya estaba en tu lista original de
  endpoints; lo dejé fuera por tiempo, es sencillo de añadir sobre
  `fact_player_games` (MAX de cada stat).
- **Splits** (casa/fuera, antes/después de una fecha, contra un rival
  concreto, en *clutch*) — `fact_player_games` y `fact_team_games` ya tienen
  `is_home` e `is_clutch` a nivel de tiro; un endpoint de "splits" que agrupe
  por esas dimensiones sería natural.
- **Comparador de jugadores** — `/players/compare?ids=1,2,3` devolviendo
  varios `PlayerTotals`/`PlayerShootingProfile` en paralelo, para que
  Streamlit no tenga que hacer N llamadas sueltas.
- **Leaderboards por zona de tiro** — `/leaderboards/shooting-zones?zone=...`
  sobre `agg_player_shooting_zones`, mencionado arriba.
- **Búsqueda/autocompletar jugador y equipo** — ya existe `q=` en
  `/players` y `/teams`; si Streamlit necesita autocompletado rápido, vale
  la pena un `limit` bajo por defecto ahí y asegurarse de que hay índice
  (o al menos que el ILIKE no escanea demasiado) cuando la tabla crezca.

Dime cuáles de estas quieres que implemente ahora y seguimos.

---

## v4: zonas de tiro, catálogo completo de métricas, game highs y clutch

### 1. Leaderboard de tiro por zona (y clutch)
`GET /leaderboards/shooting?metric=pct&zone=...&clutch_only=false&min_attempts=10`
- `metric`: `made`, `attempted`, `pct`, `frequency`.
- `zone`: opcional — valores reales en `GET /leaderboards/shooting/zones`
  (no los hardcodeé porque no conozco las etiquetas exactas de tu
  `shot_zone_basic`; ese endpoint te las devuelve directo de la BBDD).
  Si no se pasa, combina todas las zonas.
- `clutch_only`: si es `true`, usa `fact_shots` filtrando `is_clutch = true`
  en vez de la tabla pre-agregada (`agg_player_shooting_zones` no distingue
  clutch). Por eso `frequency` no está disponible todavía en modo clutch:
  necesitaría un segundo agregado de "todos los tiros clutch del jugador"
  como denominador: se puede añadir si lo necesitas.

### 2. Catálogo de métricas ampliado
`PLAYER_LEADERBOARD_METRICS` y `TEAM_LEADERBOARD_METRICS` ahora cubren
prácticamente todas las columnas de `agg_player_totals`/`agg_team_totals`:
todos los splits de tiro (`field_goals_pct`, `three_pointers_made`...),
rebotes ofensivos/defensivos por separado, `plus_minus`, dobles-dobles,
triples-dobles, `onoff_offensive_rating`/`onoff_defensive_rating`, etc.
`scope=career` funciona para todas (las de porcentaje/rating usan la
fórmula ponderada correcta, no un `AVG` ingenuo). `GET /leaderboards/metrics`
ya devuelve la lista completa.

### 3. Game highs
`GET /players/{id}/game-highs` y `GET /teams/{id}/game-highs` — mejor marca
de cada estadística **y el `match_id` en el que ocurrió**, calculado con
`arg_max()` de DuckDB en una sola pasada (no N queries, una por estadística).
Acepta los filtros comunes, así que puedes pedir "mejor partido de Francis
Alonso en la 24-25" o "en toda su carrera" sin más.

### 4. Clutch
Confirmado: el único flag de clutch que existe hoy en el warehouse es
`fact_shots.is_clutch` (a nivel de lanzamiento individual). No existe nada
de clutch en `fact_player_games`/`fact_team_games` ni en ninguna tabla
agregada. Con eso, lo que es fiable implementar ya en la API:
- `clutch_only=true` en `/players/{id}/shots` y `/matches/{id}/shots`
  (filtra lanzamientos clutch para un shot chart).
- El leaderboard de tiro de arriba, con `clutch_only=true`.

Lo que **no** es posible sin tocar dbt: puntos/rebotes/asistencias/etc. "en
clutch" como estadística de caja, porque `fact_player_games` es un
agregado de partido completo, no por tramo de partido. Para eso haría falta
una tabla nueva construida desde play-by-play (`int_play_by_play`),
filtrando eventos donde se cumpla tu definición de clutch (típicamente:
diferencia ≤5 puntos y ≤5 min restantes) y volviendo a agregar puntos/
rebotes/asistencias/etc. ahí. Es trabajo de dbt, no de la API — si quieres,
en la siguiente pasada de ingesta lo diseñamos juntos (encaja con lo que ya
comentaste de revisar la construcción de posesiones).
