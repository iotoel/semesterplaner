# ============================================================
# Semesterplaner
# ============================================================
"""
Streamlit-App, die Prüfungen, Aufträge und Ämtli aus einer JSON-Datei
in einem privaten GitHub-Repository lädt und daraus automatisch einen
Tages-, Wochen- und Monatsplan erstellt.

Wichtiger Hinweis zur Struktur:
Alle HTML-Ausgaben laufen über render_html().
Diese Funktion entfernt führende Leerzeichen aus jeder Zeile,
bevor der Text an st.markdown() übergeben wird.
Grund: Streamlits Markdown-Parser interpretiert Zeilen mit vier
oder mehr führenden Leerzeichen als Codeblock.
Mehrzeilige, eingerückte f-Strings mit HTML wurden dadurch als
reiner Text (mit sichtbaren <div>-Tags) statt als gerendertes HTML
angezeigt.
"""

from __future__ import annotations

import base64
import calendar
import json
from datetime import date, datetime, timedelta

import requests
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# KONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Semesterplaner",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# FARBEN
# ============================================================

# Grundfarben für Planungstypen
# Diese Farben werden in der MONATSANSICHT verwendet.
COLOR_EXAM = (201, 76, 76)       # Prüfungen
COLOR_TASK = (201, 162, 39)      # Aufträge
COLOR_CHORE = (61, 139, 135)     # Ämtli


# Farben für einzelne Fächer
# Diese Farben werden in der WOCHENANSICHT und ÜBERSICHT verwendet.
SUBJECT_COLORS = {
    "Mathematik": (52, 152, 219),
    "Deutsch": (155, 89, 182),
    "Englisch": (46, 204, 113),
    "Französisch": (241, 196, 15),
    "Geschichte": (230, 126, 34),
    "Geografie": (26, 188, 156),
    "Physik": (231, 76, 60),
    "Chemie": (52, 73, 94),
    "Biologie": (39, 174, 96),
    "Informatik": (127, 140, 141),
    "Latein": (127, 0, 255),
}


# Fallback, falls ein Fach nicht in SUBJECT_COLORS vorhanden ist
COLOR_SUBJECT_DEFAULT = (0, 255, 255)


WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

MONTH_NAMES = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]

GAP_MINUTES = 10
MAX_STUDY_DAYS = 10
MAX_MINUTES_PER_DAY = 45


# Arbeitszeiten je Wochentag
# 0 = Montag ... 6 = Sonntag
WORK_HOURS = {
    0: [("13:00", "20:00")],                       # Montag
    1: [("13:00", "20:00")],                       # Dienstag
    2: [("13:00", "14:00"), ("18:00", "20:00")],   # Mittwoch
    3: [("16:30", "20:00")],                       # Donnerstag
    4: [("17:00", "20:00")],                       # Freitag
    5: [("08:00", "20:00")],                       # Samstag
    6: [],                                          # Sonntag
}


# ============================================================
# HTML-RENDERING
# ============================================================

def render_html(html: str) -> None:
    """
    Rendert HTML über st.markdown, ohne dass Einrückungen als
    Markdown-Codeblock interpretiert werden.

    Jede Zeile wird getrimmt, bevor sie an st.markdown() geht.
    Das ist sicher, weil HTML- und CSS-Syntax nicht von
    führenden Leerzeichen abhängt.
    """
    cleaned = "\n".join(
        line.strip()
        for line in html.strip().splitlines()
    )
    st.markdown(cleaned, unsafe_allow_html=True)


def render_section_title(title: str) -> None:
    render_html(
        f'<div class="section-title">{escape_html(title)}</div>'
    )


def render_centered_heading(
    text: str,
    size: str = "1.3rem",
) -> None:
    render_html(
        f'<div style="text-align:center;'
        f'font-family:\'Libre Baskerville\',serif;'
        f'font-size:{size};'
        f'font-weight:700;'
        f'color:var(--ink);'
        f'padding-top:.35rem;">'
        f'{escape_html(text)}</div>'
    )


# ============================================================
# FARB-HILFSFUNKTIONEN
# ============================================================

def rgb_to_css(color: tuple[int, int, int]) -> str:
    """Wandelt ein RGB-Tupel in eine CSS-rgb()-Farbe um."""
    return f"rgb({color[0]}, {color[1]}, {color[2]})"


def get_subject_color(
    text: str | None,
) -> tuple[int, int, int]:
    """
    Sucht in einem beliebigen Text nach einem bekannten Fach.

    Dadurch funktioniert es z. B. für:
        Mathematik
        Mathematik – Ableitungen
        Prüfung Mathematik
        Lernen: Mathematik – Ableitungen

    Wenn kein Fach gefunden wird, wird die Fallback-Farbe verwendet.
    """
    text = str(text or "").strip()

    for subject, color in SUBJECT_COLORS.items():
        if subject.lower() in text.lower():
            return color

    return COLOR_SUBJECT_DEFAULT


def get_exam_color(exam: dict) -> tuple[int, int, int]:
    """
    Prüfungen bekommen in Woche und Übersicht
    die Farbe des Fachs.
    """
    return get_subject_color(
        exam.get("subject")
        or exam.get("title")
    )


def get_task_color(task: dict) -> tuple[int, int, int]:
    """
    Aufträge bekommen in Woche und Übersicht
    die Farbe des Fachs.

    Es wird zuerst nach einem separaten Fachfeld gesucht.
    Falls keines vorhanden ist, wird der komplette Auftragstitel
    nach einem bekannten Fach durchsucht.
    """
    text = " ".join(
        str(value)
        for value in [
            task.get("subject"),
            task.get("fach"),
            task.get("title"),
        ]
        if value
    )

    return get_subject_color(text)


# ============================================================
# ITEM-KARTE
# ============================================================

def render_item_card(
    title: str,
    meta: str = "",
    color: tuple[int, int, int] | None = None,
    done: bool = False,
) -> None:
    """
    Rendert eine Karte.

    Wenn color gesetzt ist, erhält die Karte links
    einen farbigen Balken.
    """
    meta_html = (
        f'<div class="item-meta">{escape_html(meta)}</div>'
        if meta
        else ""
    )

    title_style = ""
    if done:
        title_style = (
            ' style="text-decoration: line-through; '
            'opacity: 0.55;"'
        )

    color_style = ""

    if color:
        color_style = (
            f' style="border-left: 5px solid '
            f'{rgb_to_css(color)};"'
        )

    render_html(
        f'<div class="item-card"{color_style}>'
        f'<div class="item-title"{title_style}>'
        f'{escape_html(title)}'
        f'</div>'
        f'{meta_html}'
        f'</div>'
    )


# ============================================================
# CSS
# ============================================================

def inject_css() -> None:
    render_html(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Libre+Baskerville:wght@400;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');

        :root {
            --bg: #EEF1EC;
            --ink: #1C2430;
            --muted: #5B6472;
            --border: #DADFD6;
            --white: #FFFFFF;

            --red: #C94C4C;
            --gold: #C9A227;
            --teal: #3D8B87;

            --red-bg: #F8EAEA;
            --gold-bg: #FBF5DF;
            --teal-bg: #E8F3F1;
        }

        html {
            color-scheme: light !important;
        }

        body {
            background: var(--bg) !important;
            color: var(--ink) !important;
        }

        [data-testid="stAppViewContainer"],
        [data-testid="stAppViewContainer"] > .main {
            background: var(--bg) !important;
            color: var(--ink) !important;
        }

        html,
        body,
        [data-testid="stAppViewContainer"] {
            background: var(--bg);
        }

        [data-testid="stHeader"],
        [data-testid="stToolbar"] {
            display: none;
        }

        #MainMenu {
            visibility: hidden;
        }

        footer {
            visibility: hidden;
        }

        .block-container {
            max-width: 1400px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        h1,
        h2,
        h3 {
            color: var(--ink);
            font-family: "Libre Baskerville", serif;
        }

        .section-title {
            color: var(--ink);
            font-family: "Libre Baskerville", serif;
            font-size: 1.3rem;
            font-weight: 700;
            margin-top: 1.2rem;
            margin-bottom: 0.8rem;
        }

        .item-card {
            background: var(--white);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.75rem 1rem;
            margin-bottom: 0.5rem;
        }

        .item-title {
            color: var(--ink);
            font-size: 1rem;
            font-weight: 600;
        }

        .item-meta {
            color: var(--muted);
            font-size: 0.85rem;
            margin-top: 0.15rem;
        }
        </style>
        """
    )


# ============================================================
# ALLGEMEINE HILFSFUNKTIONEN
# ============================================================

def parse_date(value) -> date | None:
    """YYYY-MM-DD -> date"""
    if not value:
        return None

    try:
        return datetime.strptime(
            str(value),
            "%Y-%m-%d",
        ).date()
    except ValueError:
        return None


def iso(d: date) -> str:
    return d.isoformat()


def format_date(d: date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else ""


def format_short_date(d: date | None) -> str:
    return d.strftime("%d.%m.") if d else ""


def parse_time(value: str):
    return datetime.strptime(value, "%H:%M").time()


def minutes_between(
    start: datetime,
    end: datetime,
) -> int:
    return int(
        (end - start).total_seconds() / 60
    )


def get_exam_title(exam: dict) -> str:
    """
    Prüfungen tragen Fach + Thema im Feld
    'subject' (nicht 'title').
    """
    return (
        exam.get("subject")
        or exam.get("title")
        or "Prüfung"
    )


def get_exam_minutes(exam: dict) -> int:
    """
    Prüfungen geben die Lernzeit in 'hours' an.
    'duration' (Minuten) wird nur als Fallback
    für ältere Datensätze unterstützt.
    """
    if "hours" in exam:
        return int(exam.get("hours", 0)) * 60

    return int(exam.get("duration", 45))


def get_task_title(task: dict) -> str:
    return task.get("title") or "Auftrag"


def get_task_minutes(task: dict) -> int:
    """
    Aufträge geben den Aufwand in 'hours' an.
    'duration' (Minuten) wird nur als Fallback
    für ältere Datensätze unterstützt.
    """
    if "hours" in task:
        return int(task.get("hours", 0)) * 60

    return int(task.get("duration", 45))


def escape_html(value) -> str:
    """Verhindert, dass Benutzerdaten HTML kaputt machen."""
    if value is None:
        return ""

    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#039;")
    )


# ============================================================
# GITHUB
# ============================================================

@st.cache_data(ttl=60)
def load_data() -> dict:
    """Lädt daten.json aus dem privaten GitHub-Repository."""
    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO")
    file_path = st.secrets.get(
        "GITHUB_FILE",
        "daten.json",
    )
    branch = st.secrets.get(
        "GITHUB_BRANCH",
        "main",
    )

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN fehlt in den Streamlit-Secrets."
        )

    if not repo:
        raise RuntimeError(
            "GITHUB_REPO fehlt in den Streamlit-Secrets."
        )

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/contents/{file_path}"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.get(
        url,
        headers=headers,
        params={"ref": branch},
        timeout=20,
    )

    response.raise_for_status()

    return response.json()

def save_data(data: dict) -> None:
    """Speichert daten.json zurück ins GitHub-Repository."""

    token = st.secrets.get("GITHUB_TOKEN")
    repo = st.secrets.get("GITHUB_REPO")
    file_path = st.secrets.get("GITHUB_FILE", "daten.json")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN fehlt in den Streamlit-Secrets."
        )

    if not repo:
        raise RuntimeError(
            "GITHUB_REPO fehlt in den Streamlit-Secrets."
        )

    url = (
        f"https://api.github.com/repos/"
        f"{repo}/contents/{file_path}"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Aktuelle Datei inkl. SHA holen
    response = requests.get(
        url,
        headers=headers,
        params={"ref": branch},
        timeout=20,
    )
    response.raise_for_status()

    file_info = response.json()
    sha = file_info["sha"]

    content = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )

    encoded_content = base64.b64encode(
        content.encode("utf-8")
    ).decode("ascii")

    payload = {
        "message": "Auftragsstatus aktualisiert",
        "content": encoded_content,
        "sha": sha,
        "branch": branch,
    }

    response = requests.put(
        url,
        headers=headers,
        json=payload,
        timeout=20,
    )
    response.raise_for_status()

    load_data.clear()


# ============================================================
# DATEN BEREINIGEN
# ============================================================

def prepare_data(data: dict):
    """
    Entfernt vergangene Prüfungen und Aufträge.
    Ämtli bleiben aktiv, solange ihr Zeitraum noch läuft.
    """
    today = date.today()

    exams = [
        exam
        for exam in data.get("exams", [])
        if (
            d := parse_date(exam.get("date"))
        )
        and d >= today
    ]

    tasks = [
        task
        for task in data.get("tasks", [])
        if (
            d := parse_date(task.get("due"))
        )
        and d >= today
    ]

    chores = []

    for chore in data.get("chores", []):
        start = parse_date(
            chore.get("startDate")
        )

        if not start:
            continue

        end = parse_date(
            chore.get("endDate")
        )

        if end and end < today:
            continue

        chores.append(chore)

    return exams, tasks, chores


# ============================================================
# ÄMTLI
# ============================================================

def is_chore_active(
    chore: dict,
    d: date,
) -> bool:
    """Prüft, ob ein Ämtli an diesem Datum aktiv ist."""
    start = parse_date(
        chore.get("startDate")
    )

    if not start:
        return False

    end = parse_date(
        chore.get("endDate")
    )

    if end and d > end:
        return False

    if d < start:
        return False

    if d.weekday() == 6:
        # Sonntag = keine Ämtli
        return False

    # Unterstützt sowohl frequency: "recurring"
    # als auch das ältere boolesche Feld "recurring".
    is_recurring = (
        chore.get("frequency") == "recurring"
        or chore.get("recurring", False)
    )

    if not is_recurring:
        return d == start

    interval = int(
        chore.get(
            "interval",
            chore.get("intervalDays", 1),
        )
    ) or 1

    return (d - start).days % interval == 0


# ============================================================
# LERN- UND AUFGABENPLAN
# ============================================================

def future_days_until(
    end_date: date,
    max_days: int = MAX_STUDY_DAYS,
) -> list[date]:
    """
    Die nächsten maximal `max_days` Nicht-Sonntage
    vor dem Enddatum.
    """
    today = date.today()
    result = []
    current = today

    while (
        current < end_date
        and len(result) < max_days
    ):
        if current.weekday() != 6:
            result.append(current)

        current += timedelta(days=1)

    return result


def distribute_minutes(
    total_minutes: int,
    days: list[date],
    max_per_day: int = MAX_MINUTES_PER_DAY,
) -> dict[date, int]:
    """
    Verteilt Lern-/Aufgabenzeit auf die verfügbaren Tage.
    Es werden nur 15-Minuten-Einheiten verwendet.
    """
    if total_minutes <= 0 or not days:
        return {}

    total_minutes = (
        total_minutes // 15
    ) * 15

    if total_minutes <= 0:
        return {}

    max_per_day = (
        max_per_day // 15
    ) * 15

    result = {
        d: 0
        for d in days
    }

    remaining = total_minutes

    while remaining >= 15:
        changed = False

        for d in days:
            if remaining < 15:
                break

            if result[d] >= max_per_day:
                continue

            result[d] += 15
            remaining -= 15
            changed = True

        if not changed:
            break

    return result


def build_study_plan(
    exam: dict,
) -> dict[date, int]:
    """Erstellt einmalig den Lernplan für eine Prüfung."""
    exam_date = parse_date(
        exam.get("date")
    )

    if not exam_date:
        return {}

    total_minutes = get_exam_minutes(exam)

    days = future_days_until(
        exam_date,
        max_days=MAX_STUDY_DAYS,
    )

    return distribute_minutes(
        total_minutes,
        days,
    )


def build_task_plan(
    task: dict,
) -> dict[date, int]:
    """Erstellt einmalig den Arbeitsplan für einen Auftrag."""
    due_date = parse_date(
        task.get("due")
    )

    if not due_date:
        return {}

    total_minutes = get_task_minutes(task)

    days = future_days_until(
        due_date,
        max_days=MAX_STUDY_DAYS,
    )

    return distribute_minutes(
        total_minutes,
        days,
    )


def build_all_plans(
    exams: list[dict],
    tasks: list[dict],
):
    """
    Berechnet sämtliche Lern- und Aufgabenpläne genau einmal.
    Die Elemente werden per Index referenziert.
    """
    study_plans = {
        i: build_study_plan(exam)
        for i, exam in enumerate(exams)
    }

    task_plans = {
        i: build_task_plan(task)
        for i, task in enumerate(tasks)
    }

    return study_plans, task_plans


# ============================================================
# ZEITSLOTS
# ============================================================

def get_work_slots(
    d: date,
) -> list[tuple[datetime, datetime]]:
    """Gibt die verfügbaren Arbeitszeiten des Tages zurück."""
    result = []

    for start_text, end_text in WORK_HOURS.get(
        d.weekday(),
        [],
    ):
        start = datetime.combine(
            d,
            parse_time(start_text),
        )

        end = datetime.combine(
            d,
            parse_time(end_text),
        )

        result.append(
            (start, end)
        )

    return result


def find_free_slot(
    d: date,
    busy: list[tuple[datetime, datetime]],
    duration: int,
):
    """
    Sucht einen freien Zeitraum.
    Der GAP_MINUTES-Puffer wird nur zwischen
    bereits geplanten Aktivitäten berücksichtigt.
    """
    for slot_start, slot_end in get_work_slots(d):
        current = slot_start

        overlapping = sorted(
            (
                start,
                end
            )
            for start, end in busy
            if (
                end > slot_start
                and start < slot_end
            )
        )

        for busy_start, busy_end in overlapping:
            if busy_start > current:
                available = minutes_between(
                    current,
                    busy_start,
                )

                if available >= duration:
                    return (
                        current,
                        current + timedelta(
                            minutes=duration
                        ),
                    )

            # Erst nach einem bestehenden Block
            # kommt die definierte Pause.
            current = max(
                current,
                busy_end
                + timedelta(
                    minutes=GAP_MINUTES
                ),
            )

        if (
            current < slot_end
            and minutes_between(
                current,
                slot_end,
            ) >= duration
        ):
            return (
                current,
                current + timedelta(
                    minutes=duration
                ),
            )

    return None


# ============================================================
# TAGESPLAN
# ============================================================

def get_day_items(
    d: date,
    exams: list[dict],
    tasks: list[dict],
    chores: list[dict],
    study_plans: dict,
    task_plans: dict,
) -> list[dict]:
    """
    Baut die Anzeige für einen Tag.
    Es wird nichts neu berechnet -
    die Lern- und Aufgabenpläne kommen aus
    study_plans/task_plans.
    """
    items: list[dict] = []
    busy: list[tuple[datetime, datetime]] = []

    # --------------------------------------------------------
    # Sonntag: nur Ämtli, keine Zeitslots
    # --------------------------------------------------------

    if d.weekday() == 6:
        for chore in chores:
            if is_chore_active(chore, d):
                items.append({
                    "title": chore.get(
                        "title",
                        "Ämtli",
                    ),
                    "start": None,
                    "end": None,
                    "type": "chore",
                    "color": COLOR_CHORE,
                })

        return items

    # --------------------------------------------------------
    # Ämtli
    # --------------------------------------------------------

    for chore in chores:
        if not is_chore_active(chore, d):
            continue

        duration = int(
            chore.get("duration", 30)
        )

        slot = find_free_slot(
            d,
            busy,
            duration,
        )

        if not slot:
            continue

        start, end = slot

        items.append({
            "title": chore.get(
                "title",
                "Ämtli",
            ),
            "start": start,
            "end": end,
            "type": "chore",
            "color": COLOR_CHORE,
        })

        busy.append(
            (start, end)
        )

    # --------------------------------------------------------
    # Freizeit (nicht Donnerstag)
    # --------------------------------------------------------

    if d.weekday() != 3:
        work_slots = get_work_slots(d)

        if work_slots:
            first_start = work_slots[0][0]
            last_end = work_slots[-1][1]

            midpoint = (
                first_start
                + (last_end - first_start) / 2
            )

            leisure_start = (
                midpoint
                - timedelta(minutes=45)
            )

            leisure_end = (
                midpoint
                + timedelta(minutes=45)
            )

            if (
                leisure_start >= first_start
                and leisure_end <= last_end
            ):
                slot_is_free = not any(
                    not (
                        leisure_end <= busy_start
                        or leisure_start >= busy_end
                    )
                    for busy_start, busy_end in busy
                )

                if slot_is_free:
                    items.append({
                        "title": "Freizeit",
                        "start": leisure_start,
                        "end": leisure_end,
                        "type": "leisure",
                        "color": None,
                    })

                    busy.append(
                        (
                            leisure_start,
                            leisure_end,
                        )
                    )

    # --------------------------------------------------------
    # Lernen
    # --------------------------------------------------------

    for index, exam in enumerate(exams):
        duration = (
            study_plans
            .get(index, {})
            .get(d, 0)
        )

        if duration <= 0:
            continue

        slot = find_free_slot(
            d,
            busy,
            duration,
        )

        if not slot:
            continue

        start, end = slot

        title = (
            "Lernen: "
            + get_exam_title(exam)
        )

        items.append({
            "title": title,
            "start": start,
            "end": end,
            "type": "study",

            # Woche/Übersicht:
            # Farbe des Prüfungsfachs
            "color": get_exam_color(exam),
        })

        busy.append(
            (start, end)
        )

    # --------------------------------------------------------
    # Aufträge
    # --------------------------------------------------------

    for index, task in enumerate(tasks):
        duration = (
            task_plans
            .get(index, {})
            .get(d, 0)
        )

        if duration <= 0:
            continue

        slot = find_free_slot(
            d,
            busy,
            duration,
        )

        if not slot:
            continue

        start, end = slot

        items.append({
            "title": get_task_title(task),
            "start": start,
            "end": end,
            "type": "task",

            # Index des ursprünglichen Auftrags
            "task_index": index,

            # Erledigt?
            "done": bool(task.get("done", False)),

            # Woche/Übersicht:
            # Farbe des Auftragsfachs
            "color": get_task_color(task),
        })

        busy.append(
            (start, end)
        )

    items.sort(
        key=lambda item: (
            item["start"] is None,
            item["start"] or datetime.max,
        )
    )

    return items


def format_time_range(
    item: dict,
) -> str:
    start = item["start"]
    end = item["end"]

    return (
        f"{start.strftime('%H:%M')} – "
        f"{end.strftime('%H:%M')}"
        if start and end
        else ""
    )


# ============================================================
# ÜBERSICHT
# ============================================================

def render_overview(
    data,
    exams,
    tasks,
    chores,
    study_plans,
    task_plans,
) -> None:
    today = date.today()

    # --------------------------------------------------------
    # Heute
    # --------------------------------------------------------

    render_section_title("Heute")

    today_items = get_day_items(
        today,
        exams,
        tasks,
        chores,
        study_plans,
        task_plans,
    )

    if not today_items:
        st.info(
            "Für heute ist nichts geplant."
        )

    for index, item in enumerate(today_items):
        col1, col2 = st.columns(
            [0.05, 0.95]
        )

        with col1:
            st.checkbox(
                "",
                key=f"today_done_{index}",
            )

        with col2:
            render_item_card(
                item["title"],
                format_time_range(item),
                item.get("color"),
            )

    # --------------------------------------------------------
    # Prüfungen
    # --------------------------------------------------------

    render_section_title("Prüfungen")

    if not exams:
        st.info(
            "Keine kommenden Prüfungen."
        )

    for exam in exams:
        d = parse_date(
            exam.get("date")
        )

        render_item_card(
            get_exam_title(exam),
            format_date(d),

            # Übersicht:
            # Farbe des Prüfungsfachs
            get_exam_color(exam),
        )

    # --------------------------------------------------------
    # Aufträge
    # --------------------------------------------------------

    render_section_title("Aufträge")

    if not tasks:
        st.info(
            "Keine offenen Aufträge."
        )

    for index, task in enumerate(tasks):
        d = parse_date(task.get("due"))

        checkbox_key = f"task_done_{index}"

        # Aktuellen gespeicherten Zustand übernehmen
        if checkbox_key not in st.session_state:
            st.session_state[checkbox_key] = bool(
                task.get("done", False)
            )

        col1, col2 = st.columns([0.05, 0.95])

        with col1:
            checked = st.checkbox(
                "",
                key=checkbox_key,
            )

        with col2:
            render_item_card(
                get_task_title(task),
                f"Fällig: {format_date(d)}",
                get_task_color(task),
                done=checked,
            )

        # Nur speichern, wenn sich der Wert geändert hat
        old_value = bool(task.get("done", False))

        if checked != old_value:
            task["done"] = checked

            # Originaldaten aktualisieren.
            # Dadurch wird nicht nur die gefilterte Liste verändert.
            for original_task in data.get("tasks", []):
                if original_task is task:
                    original_task["done"] = checked
                    break

            try:
                save_data(data)
                st.rerun()
            except Exception as error:
                st.error(
                    "Der Status konnte nicht in GitHub gespeichert werden."
                )
                st.code(str(error))

    # --------------------------------------------------------
    # Ämtli
    # --------------------------------------------------------

    render_section_title("Ämtli")

    active_chores = [
        c
        for c in chores
        if is_chore_active(c, today)
    ]

    if not active_chores:
        st.info(
            "Heute keine Ämtli."
        )

    for chore in active_chores:
        render_item_card(
            chore.get(
                "title",
                "Ämtli",
            ),
            color=COLOR_CHORE,
        )


# ============================================================
# WOCHENANSICHT
# ============================================================

def render_week(
    exams,
    tasks,
    chores,
    study_plans,
    task_plans,
) -> None:
    if "week_offset" not in st.session_state:
        st.session_state.week_offset = 0

    col1, col2, col3 = st.columns(
        [1, 2, 1]
    )

    with col1:
        if st.button(
            "← Vorherige Woche",
            key="previous_week",
        ):
            st.session_state.week_offset -= 1
            st.rerun()

    with col2:
        render_centered_heading(
            "Wochenansicht"
        )

    with col3:
        if st.button(
            "Nächste Woche →",
            key="next_week",
        ):
            st.session_state.week_offset += 1
            st.rerun()

    if st.button(
        "Heute",
        key="today_week",
    ):
        st.session_state.week_offset = 0
        st.rerun()

    today = date.today()

    monday = (
        today
        - timedelta(days=today.weekday())
        + timedelta(
            weeks=st.session_state.week_offset
        )
    )

    columns = st.columns(7)

    for index in range(7):
        d = monday + timedelta(
            days=index
        )

        with columns[index]:
            st.markdown(
                f"**{WEEKDAYS[index]}**  \n"
                f"`{format_short_date(d)}`"
            )

            items = get_day_items(
                d,
                exams,
                tasks,
                chores,
                study_plans,
                task_plans,
            )

            if not items:
                st.caption("—")

            for item in items:
                render_item_card(
                    item["title"],
                    format_time_range(item),

                    # Woche:
                    # Fachfarbe oder Ämtli-Farbe
                    item.get("color"),

                    # Erledigte Aufträge durchstreichen
                    done=item.get("done", False),
                )


# ============================================================
# MONATSKALENDER
# ============================================================

def render_month(
    exams,
    tasks,
    chores,
) -> None:
    if "month_offset" not in st.session_state:
        st.session_state.month_offset = 0

    today = date.today()

    month_index = (
        today.year * 12
        + today.month
        - 1
        + st.session_state.month_offset
    )

    year = month_index // 12
    month = month_index % 12 + 1

    # --------------------------------------------------------
    # Navigation
    # --------------------------------------------------------

    col1, col2, col3 = st.columns(
        [1, 2, 1]
    )

    with col1:
        if st.button(
            "← Vorheriger Monat",
            key="previous_month",
        ):
            st.session_state.month_offset -= 1
            st.rerun()

    with col2:
        render_centered_heading(
            f"{MONTH_NAMES[month - 1]} {year}",
            size="1.35rem",
        )

    with col3:
        if st.button(
            "Nächster Monat →",
            key="next_month",
        ):
            st.session_state.month_offset += 1
            st.rerun()

    if st.button(
        "Heute",
        key="today_month",
    ):
        st.session_state.month_offset = 0
        st.rerun()

    # --------------------------------------------------------
    # Kalenderdaten
    # --------------------------------------------------------

    weeks = (
        calendar.Calendar(
            firstweekday=0
        ).monthdatescalendar(
            year,
            month,
        )
    )

    # --------------------------------------------------------
    # HTML
    #
    # In der Monatsansicht zeigen die Punkte NUR:
    # - Prüfung
    # - Auftrag
    # - Ämtli
    #
    # Die Fachfarben werden hier bewusst NICHT verwendet.
    # --------------------------------------------------------

    style = """
    * {
        box-sizing: border-box;
    }

    body {
        margin: 0;
        padding: 0;
        background: #EEF1EC;
        font-family: Arial, sans-serif;
    }

    .calendar {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 5px;
        width: 100%;
    }

    .weekday {
        text-align: center;
        color: #5B6472;
        font-family: monospace;
        font-size: 13px;
        font-weight: 500;
        padding: 7px 4px;
    }

    .calendar-cell {
        min-height: 115px;
        background: #FFFFFF;
        border: 1px solid #DADFD6;
        border-radius: 10px;
        padding: 10px;
        position: relative;
    }

    .calendar-cell.today {
        background: #FBF5DF;
        border: 2px solid #C9A227;
    }

    .calendar-cell.outside {
        background: #F4F5F2;
        opacity: 0.45;
    }

    .day-number {
        color: #1C2430;
        font-family: monospace;
        font-size: 14px;
        font-weight: 500;
    }

    .dots {
        position: absolute;
        left: 10px;
        bottom: 10px;
        display: flex;
        gap: 6px;
    }

    .dot {
        display: inline-block;
        width: 9px;
        height: 9px;
        border-radius: 50%;
    }

    /* Prüfung */
    .dot-red {
        background: #C94C4C;
    }

    /* Auftrag */
    .dot-gold {
        background: #C9A227;
    }

    /* Ämtli */
    .dot-teal {
        background: #3D8B87;
    }
    """

    cells = "".join(
        f'<div class="weekday">{wd}</div>'
        for wd in WEEKDAYS
    )

    for week in weeks:
        for d in week:
            current_date = iso(d)

            classes = [
                "calendar-cell"
            ]

            if d.month != month:
                classes.append(
                    "outside"
                )

            if d == today:
                classes.append(
                    "today"
                )

            dots = ""

            # ------------------------------------------------
            # MONAT:
            # Prüfung = rot
            # ------------------------------------------------

            if any(
                exam.get("date")
                == current_date
                for exam in exams
            ):
                dots += (
                    '<span class="dot '
                    'dot-red"></span>'
                )

            # ------------------------------------------------
            # MONAT:
            # Auftrag = gelb
            # ------------------------------------------------

            if any(
                task.get("due")
                == current_date
                for task in tasks
            ):
                dots += (
                    '<span class="dot '
                    'dot-gold"></span>'
                )

            # ------------------------------------------------
            # MONAT:
            # Ämtli = türkis
            # ------------------------------------------------

            if any(
                is_chore_active(chore, d)
                for chore in chores
            ):
                dots += (
                    '<span class="dot '
                    'dot-teal"></span>'
                )

            cells += (
                f'<div class="{" ".join(classes)}">'
                f'<div class="day-number">'
                f'{d.day}'
                f'</div>'
                f'<div class="dots">'
                f'{dots}'
                f'</div>'
                f'</div>'
            )

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>{style}</style>
    </head>

    <body>
        <div class="calendar">
            {cells}
        </div>
    </body>
    </html>
    """

    components.html(
        html,
        height=(len(weeks) + 1) * 120 + 20,
        scrolling=False,
    )


# ============================================================
# HAUPTPROGRAMM
# ============================================================

def main() -> None:
    inject_css()

    st.title("Semesterplaner")

    # --------------------------------------------------------
    # Daten laden
    # --------------------------------------------------------

    try:
        data = load_data()

    except Exception as error:
        st.error(
            "Die Daten konnten nicht von GitHub geladen werden."
        )

        st.code(str(error))
        st.stop()

    exams, tasks, chores = prepare_data(data)

    study_plans, task_plans = build_all_plans(
        exams,
        tasks,
    )

    # --------------------------------------------------------
    # Kopfbereich
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Prüfungen",
            len(exams),
        )

    with col2:
        st.metric(
            "Aufträge",
            len(tasks),
        )

    with col3:
        st.metric(
            "Ämtli",
            len(chores),
        )

    with col4:
        if st.button(
            "↻ Aktualisieren",
            key="reload",
        ):
            load_data.clear()
            st.rerun()

    # --------------------------------------------------------
    # Tabs
    # --------------------------------------------------------

    tab_overview, tab_week, tab_month = st.tabs(
        [
            "Übersicht",
            "Woche",
            "Monat",
        ]
    )

    # --------------------------------------------------------
    # Übersicht
    # --------------------------------------------------------

    with tab_overview:
        render_overview(
            data,
            exams,
            tasks,
            chores,
            study_plans,
            task_plans,
        )

    # --------------------------------------------------------
    # Woche
    # --------------------------------------------------------

    with tab_week:
        render_week(
            exams,
            tasks,
            chores,
            study_plans,
            task_plans,
        )

    # --------------------------------------------------------
    # Monat
    # --------------------------------------------------------

    with tab_month:
        render_month(
            exams,
            tasks,
            chores,
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()