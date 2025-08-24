import requests
import json
from datetime import datetime, UTC

# =====================
# CONFIGURACIÓN LIGA
# =====================
USER_TO_TEAM = {
    "Junior192415": "Dodgers",
    "Yosoyreynoso_": "Padres",
    "edwar13-21": "Yankees",
    "Passing-wile5": "Brewers",
    "LuisMiguelRD": "Phillies",
    "rauz-444": "Braves",
    "ALEXCONDE01": "Cubs",
    "Joshuan_c95": "Mariners",
    "MVP140605": "Blue Jays",
    "SergiioRD": "Tigers",
    "vicentealoise": "Mets",
    "Ernerst12cuba": "Astros",
    "Bititi2024": "Diamondbacks",
}

TEAM_TO_USER = {team: user for user, team in USER_TO_TEAM.items()}

# Ajustes manuales para la tabla extendida
MERCYS_DADOS = {     # equipo: cantidad
    # "Dodgers": 1,
}
MERCYS_RECIBIDOS = {
    # "Yankees": 1,
}
ABANDONOS = {
    # "Padres": 1,
}

PROGRAMADOS = 12
START_DATE = datetime(2025, 8, 23)
MODE_OF_LEAGUE = "LEAGUE"


# =====================
# API
# =====================
def get_game_history(username, platform, api_version="mlb25", page=1):
    url = f"https://{api_version}.theshow.com/apis/game_history.json"
    params = {"username": username, "platform": platform, "page": page}
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error en la solicitud para la página {page} de '{username}': {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error al decodificar la respuesta JSON en la página {page} de '{username}': {e}")
        return None


# =====================
# PROCESAMIENTO
# =====================
def generate_league_table(user_to_team_map, start_date, mode_of_league):
    league_table = {team: {"Jugados": 0, "Ganados": 0, "Perdidos": 0, "Empates": 0} for team in user_to_team_map.values()}
    normalized = {u.replace('^b53^', '').replace('^b54^', '').lower().strip(): t for u, t in user_to_team_map.items()}
    team_to_user = {v: k for k, v in user_to_team_map.items()}
    processed_games = set()

    for my_username in user_to_team_map.keys():
        all_games, page, total_pages = [], 1, 1
        print(f"Iniciando descarga del historial para '{my_username}'...")
        while page <= total_pages:
            data = get_game_history(my_username, "psn", page=page)
            if data and "game_history" in data:
                all_games.extend(data["game_history"])
                total_pages = data.get("total_pages", total_pages)
            else:
                break
            page += 1

        for game in all_games:
            ds = game.get("display_date")
            if not ds:
                continue
            try:
                gd = datetime.strptime(ds, "%m/%d/%Y %H:%M:%S")
            except ValueError:
                continue
            if gd < start_date or game.get("game_mode") != mode_of_league:
                continue

            home_user = game.get("home_name", "").replace('^b53^', '').replace('^b54^', '').lower().strip()
            away_user = game.get("away_name", "").replace('^b53^', '').replace('^b54^', '').lower().strip()
            if home_user == "cpu":
                home_full = game.get("home_full_name", "")
                if home_full in team_to_user:
                    home_user = team_to_user[home_full].lower().strip()
            if away_user == "cpu":
                away_full = game.get("away_full_name", "")
                if away_full in team_to_user:
                    away_user = team_to_user[away_full].lower().strip()

            if home_user in normalized and away_user in normalized:
                home_team = normalized[home_user]
                away_team = normalized[away_user]
                key = tuple(sorted((home_user, away_user))) + (gd,)
                if key in processed_games:
                    continue
                processed_games.add(key)

                hr = int(game.get("home_runs", 0) or 0)
                ar = int(game.get("away_runs", 0) or 0)

                league_table[home_team]["Jugados"] += 1
                league_table[away_team]["Jugados"] += 1
                if hr > ar:
                    league_table[home_team]["Ganados"] += 1
                    league_table[away_team]["Perdidos"] += 1
                elif ar > hr:
                    league_table[away_team]["Ganados"] += 1
                    league_table[home_team]["Perdidos"] += 1
                else:
                    league_table[home_team]["Empates"] += 1
                    league_table[away_team]["Empates"] += 1
    return league_table


def build_points_extended(league_table):
    rows = []
    for team, st in league_table.items():
        j = st.get("Jugados", 0)
        g = st.get("Ganados", 0)
        p = st.get("Perdidos", 0)
        e = st.get("Empates", 0)

        mg = max(0, min(MERCYS_DADOS.get(team, 0), g))
        mr = max(0, min(MERCYS_RECIBIDOS.get(team, 0), p))
        ab = max(0, ABANDONOS.get(team, 0))

        # Puntos base + ajustes por mercy:
        # win normal: +3, lose normal: +2, win mercy: +4 (= +1 extra por MG), lose mercy: +1 (= -1 por MR)
        pts = (3 * g) + (2 * p) + (1 * mg) - (1 * mr)
        row = {
            "equipo": team,
            "participante": TEAM_TO_USER.get(team, ""),
            "prog": PROGRAMADOS,
            "j": j,
            "g": g,
            "p": p,
            "por_jugar": max(0, PROGRAMADOS - j),
            "pts": max(0, pts),
            "mg": mg,
            "mr": mr,
            "ab": ab,
            "e": e,
        }
        rows.append(row)

    rows.sort(key=lambda r: (r["pts"], r["g"], r["j"], -r["p"]), reverse=True)
    return rows


def save_json_and_js(rows, json_path="standings.json", js_path="standings.js"):
    payload = {"generated_at": datetime.now(UTC).isoformat(), "rows": rows}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.STANDINGS = ")
        json.dump(payload, f, ensure_ascii=False)
        f.write(";")
    print(f"Guardado {json_path} y {js_path}")


def print_console_table(rows):
    headers = ["Equipo","Participante","Prog","J","G","P","Por jugar","PTS","MG","MR","AB"]
    widths = [18,14,4,3,3,3,9,4,3,3,3]
    sep = "+-" + "-+-".join("-"*w for w in widths) + "-+"
    fmt = "| " + " | ".join("{:<%d}"%w for w in widths) + " |"
    print(sep)
    print(fmt.format(*headers))
    print(sep)
    for i, r in enumerate(rows, start=1):
        print(fmt.format(r["equipo"], r["participante"], r["prog"], r["j"], r["g"], r["p"], r["por_jugar"], r["pts"], r["mg"], r["mr"], r["ab"]))
        if i==8:
            print(sep)  # separador después del 8.º
    print(sep)


def generate_html_table(league_table):
    rows = build_points_extended(league_table)
    html = ["<!DOCTYPE html><html><head><meta charset='utf-8'><title>Tabla SDC</title></head><body>"]
    html.append("<h2>Tabla de Posiciones (11 columnas)</h2>")
    html.append("<table border='1' cellpadding='6' cellspacing='0'>")
    html.append("<tr><th>Equipo</th><th>Participante</th><th>Prog</th><th>J</th><th>G</th><th>P</th><th>Por jugar</th><th>PTS</th><th>MG</th><th>MR</th><th>AB</th></tr>")
    for i, r in enumerate(rows, start=1):
        tr_style = " style='border-bottom:2px dashed #999'" if i==8 else ""
        html.append(f"<tr{tr_style}><td>{r['equipo']}</td><td>{r['participante']}</td><td>{r['prog']}</td><td>{r['j']}</td><td>{r['g']}</td><td>{r['p']}</td><td>{r['por_jugar']}</td><td>{r['pts']}</td><td>{r['mg']}</td><td>{r['mr']}</td><td>{r['ab']}</td></tr>")
    html.append("</table></body></html>")
    return "\n".join(html)


if __name__ == "__main__":
    print("--- GENERANDO TABLA DE POSICIONES (11 columnas) ---")
    league_table = generate_league_table(USER_TO_TEAM, START_DATE, MODE_OF_LEAGUE)
    rows = build_points_extended(league_table)
    print_console_table(rows)
    # Archivos de salida
    with open("tabla_SDC.html", "w", encoding="utf-8") as f:
        f.write(generate_html_table(league_table))
    save_json_and_js(rows, json_path="standings.json", js_path="standings.js")
    print("Listo.")
