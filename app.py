from __future__ import annotations

import base64
import calendar
import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from html import escape

import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Semesterplaner", page_icon="🗓️", layout="wide", initial_sidebar_state="collapsed")

COLOR_EXAM = (201, 76, 76)
COLOR_TASK = (201, 162, 39)
COLOR_CHORE = (61, 139, 135)
COLOR_FIXED = (91, 105, 125)
COLOR_SUBJECT_DEFAULT = (0, 255, 255)
SUBJECT_COLORS = {
    "Mathematik": (52, 152, 219), "Deutsch": (155, 89, 182),
    "Englisch": (46, 204, 113), "Französisch": (241, 196, 15),
    "Geschichte": (230, 126, 34), "Geografie": (26, 188, 156),
    "Physik": (231, 76, 60), "Chemie": (52, 73, 94),
    "Biologie": (39, 174, 96), "Informatik": (127, 140, 141),
    "Latein": (0, 255, 255),
}
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTH_NAMES = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
GAP_MINUTES = 10
MAX_STUDY_DAYS = 10
MAX_MINUTES_PER_DAY = 45
WORK_HOURS = {
    0: [("13:00", "20:00")], 1: [("13:00", "20:00")],
    2: [("13:00", "14:00"), ("18:00", "20:00")],
    3: [("16:30", "20:00")], 4: [("17:00", "20:00")],
    5: [("08:00", "20:00")], 6: [],
}


def render_html(html: str) -> None:
    cleaned = "\n".join(line.strip() for line in html.strip().splitlines())
    st.markdown(cleaned, unsafe_allow_html=True)


def escape_html(value) -> str:
    return escape(str(value), quote=True) if value is not None else ""


def render_section_title(title: str) -> None:
    render_html(f'<div class="section-title">{escape_html(title)}</div>')


def render_centered_heading(text: str, size: str = "1.3rem") -> None:
    render_html(
        f'<div style="text-align:center;font-family:\'Libre Baskerville\',serif;'
        f'font-size:{size};font-weight:700;color:var(--ink);padding-top:.35rem;">'
        f'{escape_html(text)}</div>'
    )


def rgb_to_css(color: tuple[int, int, int]) -> str:
    return f"rgb({color[0]}, {color[1]}, {color[2]})"


def get_subject_color(text: str | None) -> tuple[int, int, int]:
    text = str(text or "")
    for subject, color in SUBJECT_COLORS.items():
        if subject.lower() in text.lower():
            return color
    return COLOR_SUBJECT_DEFAULT


def get_exam_color(exam: dict) -> tuple[int, int, int]:
    return get_subject_color(exam.get("subject") or exam.get("title"))


def get_task_color(task: dict) -> tuple[int, int, int]:
    text = " ".join(str(v) for v in (task.get("subject"), task.get("fach"), task.get("title")) if v)
    return get_subject_color(text)


def render_item_card(title: str, meta: str = "", color: tuple[int, int, int] | None = None, done: bool = False) -> None:
    meta_html = f'<div class="item-meta">{escape_html(meta)}</div>' if meta else ""
    title_style = ' style="text-decoration:line-through;opacity:.55;"' if done else ""
    color_style = f' style="border-left:5px solid {rgb_to_css(color)};"' if color else ""
    render_html(f'<div class="item-card"{color_style}><div class="item-title"{title_style}>{escape_html(title)}</div>{meta_html}</div>')


def inject_css() -> None:
    render_html("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Libre+Baskerville:wght@400;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');
    :root{--bg:#EEF1EC;--ink:#1C2430;--muted:#5B6472;--border:#DADFD6;--white:#FFF}
    html{color-scheme:light!important}body,[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"]>.main{background:var(--bg)!important;color:var(--ink)!important}
    [data-testid="stHeader"],[data-testid="stToolbar"]{display:none}#MainMenu,footer{visibility:hidden}
    .block-container{max-width:1400px;padding-top:2rem;padding-bottom:3rem}
    h1,h2,h3{color:var(--ink);font-family:"Libre Baskerville",serif}
    .section-title{color:var(--ink);font-family:"Libre Baskerville",serif;font-size:1.3rem;font-weight:700;margin:1.2rem 0 .8rem}
    .item-card{background:var(--white);border:1px solid var(--border);border-radius:10px;padding:.75rem 1rem;margin-bottom:.5rem}
    .item-title{color:var(--ink);font-size:1rem;font-weight:600}.item-meta{color:var(--muted);font-size:.85rem;margin-top:.15rem}
    </style>
    """)


def parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
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


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() / 60)


def get_exam_title(exam: dict) -> str:
    return exam.get("subject") or exam.get("title") or "Prüfung"


def get_exam_minutes(exam: dict) -> int:
    return round(float(exam.get("hours", 0)) * 60) if "hours" in exam else int(exam.get("duration", 45))


def get_task_title(task: dict) -> str:
    return task.get("title") or "Auftrag"


def get_task_minutes(task: dict) -> int:
    return round(float(task.get("hours", 0)) * 60) if "hours" in task else int(task.get("duration", 45))


def format_calendar_tooltip(title: str, kind: str, start: datetime, end: datetime, entry: dict | None = None, extra: list[str] | None = None) -> str:
    """Erstellt einen vollständigen mehrzeiligen Tooltip für einen Kalendereintrag."""
    lines = [title, f"Art: {kind}", f"Zeit: {start.strftime('%d.%m.%Y, %H:%M')}–{end.strftime('%H:%M')}"]
    labels = {
        "subject": "Fach", "fach": "Fach", "title": "Titel", "date": "Prüfungsdatum",
        "due": "Deadline", "hours": "Aufwand (Stunden)", "duration": "Dauer (Minuten)",
        "freiwillig": "Freiwillig", "done": "Erledigt", "startDate": "Startdatum",
        "endDate": "Enddatum", "frequency": "Wiederholung", "recurring": "Wiederkehrend",
        "interval": "Intervall (Tage)", "intervalDays": "Intervall (Tage)",
        "start": "Beginn", "end": "Ende", "enabled": "Aktiv", "description": "Beschreibung",
        "notes": "Notizen", "topic": "Thema", "color": "Farbe",
    }
    if entry:
        for key, value in entry.items():
            if key == "id" or value is None or value == "":
                continue
            if isinstance(value, bool):
                value_text = "Ja" if value else "Nein"
            elif key in ("date", "due", "startDate", "endDate"):
                parsed = parse_date(value)
                value_text = format_date(parsed) if parsed else str(value)
            elif key in ("start", "end"):
                value_text = str(value)
            elif isinstance(value, (dict, list)):
                value_text = json.dumps(value, ensure_ascii=False)
            else:
                value_text = str(value)
            lines.append(f"{labels.get(key, key.replace('_', ' ').capitalize())}: {value_text}")
    if extra:
        lines.extend(extra)
    return "\n".join(lines)


def get_github_config() -> tuple[str, str, str, str]:
    token = str(st.secrets.get("GITHUB_TOKEN", "")).strip()
    repo = str(st.secrets.get("GITHUB_REPO", "")).strip()
    file_path = str(st.secrets.get("GITHUB_FILE", "daten.json")).strip() or "daten.json"
    branch = str(st.secrets.get("GITHUB_BRANCH", "main")).strip() or "main"
    if not token:
        raise RuntimeError("GITHUB_TOKEN fehlt in den Streamlit-Secrets.")
    if not repo:
        raise RuntimeError("GITHUB_REPO fehlt in den Streamlit-Secrets.")
    return token, repo, file_path, branch


def get_github_url(repo: str, file_path: str) -> str:
    return f"https://api.github.com/repos/{repo}/contents/{file_path}"


def get_github_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def get_github_error_message(response: requests.Response, fallback: str) -> str:
    try:
        message = response.json().get("message")
    except ValueError:
        message = None
    messages = {
        401: "GitHub-Anmeldung fehlgeschlagen. GITHUB_TOKEN prüfen.",
        403: "GitHub verweigert den Zugriff. Token-Berechtigung und Repository-Zugriff prüfen.",
        404: "Repository, Branch oder daten.json wurde nicht gefunden.",
        409: "GitHub-Konflikt beim Speichern. Die Datei wurde gleichzeitig geändert.",
        422: "GitHub hat die Änderung abgelehnt. Branch, SHA und Dateipfad prüfen.",
    }
    return messages.get(response.status_code, f"{fallback} GitHub meldet: {message}" if message else f"{fallback} HTTP-Status {response.status_code}")


def decode_github_content(payload: dict) -> dict:
    content = payload.get("content")
    if not content:
        raise RuntimeError("GitHub hat keinen Dateiinhalt zurückgegeben.")
    try:
        data = json.loads(base64.b64decode(content.replace("\n", "")).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("daten.json konnte nicht gelesen werden.") from error
    if not isinstance(data, dict):
        raise RuntimeError("daten.json muss ein JSON-Objekt enthalten.")
    for key in ("exams", "tasks", "chores", "fixed_events"):
        data.setdefault(key, [])
    data.setdefault("completions", {})
    data.setdefault("leisure_overrides", {})
    data.setdefault("fixed_events", [])
    return data


@st.cache_data(ttl=60)
def load_data() -> dict:
    token, repo, file_path, branch = get_github_config()
    response = requests.get(get_github_url(repo, file_path), headers=get_github_headers(token), params={"ref": branch}, timeout=20)
    if not response.ok:
        raise RuntimeError(get_github_error_message(response, "Daten konnten nicht geladen werden."))
    return decode_github_content(response.json())


def build_save_content(data: dict) -> dict:
    return {
        "exams": data.get("exams", []),
        "tasks": data.get("tasks", []),
        "chores": data.get("chores", []),
        "fixed_events": data.get("fixed_events", []),
        "completions": data.get("completions", {}),
        "leisure_overrides": data.get("leisure_overrides", {}),
    }


def save_data(data: dict, commit_message: str = "Auftragsstatus aktualisiert") -> None:
    token, repo, file_path, branch = get_github_config()
    url = get_github_url(repo, file_path)
    headers = get_github_headers(token)
    encoded = base64.b64encode(json.dumps(build_save_content(data), ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii")
    for attempt in range(2):
        metadata = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
        if not metadata.ok:
            raise RuntimeError(get_github_error_message(metadata, "Aktueller Dateistand konnte nicht gelesen werden."))
        sha = metadata.json().get("sha")
        if not sha:
            raise RuntimeError("GitHub hat keinen SHA-Wert zurückgegeben.")
        response = requests.put(url, headers=headers, json={"message": commit_message, "content": encoded, "sha": sha, "branch": branch}, timeout=20)
        if response.status_code in (200, 201):
            load_data.clear()
            return
        if response.status_code != 409 or attempt == 1:
            raise RuntimeError(get_github_error_message(response, "Daten konnten nicht gespeichert werden."))


def get_task_identifier(task: dict) -> str:
    existing_id = str(task.get("id", "")).strip()
    if existing_id:
        return existing_id
    identity = {key: task.get(key) for key in ("title", "subject", "fach", "due", "hours", "duration")}
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def update_task_done(data: dict, task_identifier: str, done: bool) -> None:
    for task in data.get("tasks", []):
        if get_task_identifier(task) == task_identifier:
            task["done"] = bool(done)
            return
    raise RuntimeError("Der Auftrag wurde in daten.json nicht gefunden.")


def sync_task_checkbox_keys(task_identifier: str, done: bool) -> None:
    for prefix in ("task_done", "today_task_done"):
        key = f"{prefix}_{task_identifier}"
        if key in st.session_state:
            st.session_state[key] = done


def save_task_checkbox(
    task_identifier: str,
    checkbox_key: str,
) -> None:
    checked = bool(
        st.session_state.get(
            checkbox_key,
            False,
        )
    )

    try:
        load_data.clear()

        current_data = load_data()

        previous_state = False

        for task in current_data.get(
            "tasks",
            [],
        ):
            if (
                get_task_identifier(task)
                == task_identifier
            ):
                previous_state = bool(
                    task.get(
                        "done",
                        False,
                    )
                )
                break

        update_task_done(
            current_data,
            task_identifier,
            checked,
        )

        save_data(
            current_data,
            "Auftragsstatus aktualisiert",
        )

        sync_task_checkbox_keys(
            task_identifier,
            checked,
        )

        if checked and not previous_state:
            st.session_state["show_balloons"] = True

        st.session_state[
            "save_success"
        ] = (
            "Auftrag wurde gespeichert."
        )

        st.session_state.pop(
            "save_error",
            None,
        )

    except Exception as error:
        st.session_state[
            checkbox_key
        ] = not checked

        st.session_state[
            "save_error"
        ] = str(error)



def render_task_checkbox(task: dict, prefix: str) -> bool:
    identifier = get_task_identifier(task)
    key = f"{prefix}_{identifier}"
    if key not in st.session_state:
        st.session_state[key] = bool(task.get("done", False))
    st.checkbox("", key=key, on_change=save_task_checkbox, args=(identifier, key))
    return bool(st.session_state[key])



def get_daily_item_identifier(item: dict, item_date: date) -> str:
    """Erzeugt eine stabile Kennung für einen Tagesplaneintrag."""
    identity = {
        "date": iso(item_date),
        "type": item.get("type"),
        "title": item.get("title"),
        "start": item.get("start").strftime("%H:%M") if item.get("start") else None,
        "end": item.get("end").strftime("%H:%M") if item.get("end") else None,
    }
    digest = hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    return f"{iso(item_date)}_{item.get('type', 'item')}_{digest}"


def get_daily_completion(data: dict, item_identifier: str) -> bool:
    return bool(data.get("completions", {}).get(item_identifier, False))


def save_daily_checkbox(item_identifier: str, checkbox_key: str) -> None:
    """Speichert Lernen, Ämtli und weitere Tagespunkte datumsspezifisch."""
    checked = bool(st.session_state.get(checkbox_key, False))
    try:
        load_data.clear()
        current_data = load_data()
        completions = current_data.setdefault("completions", {})
        previous_state = bool(completions.get(item_identifier, False))

        if checked:
            completions[item_identifier] = True
        else:
            completions.pop(item_identifier, None)

        save_data(current_data, commit_message="Tagesstatus aktualisiert")

        if checked and not previous_state:
            st.session_state["show_balloons"] = True

        st.session_state["save_success"] = "Status wurde gespeichert."
        st.session_state.pop("save_error", None)
    except Exception as error:
        st.session_state[checkbox_key] = not checked
        st.session_state["save_error"] = str(error)


def render_daily_checkbox(
    data: dict,
    item: dict,
    item_date: date,
    widget_prefix: str,
) -> bool:
    identifier = get_daily_item_identifier(item, item_date)
    key = f"{widget_prefix}_daily_done_{identifier}"
    if key not in st.session_state:
        st.session_state[key] = get_daily_completion(data, identifier)
    st.checkbox("", key=key, on_change=save_daily_checkbox, args=(identifier, key))
    return bool(st.session_state[key])


def prepare_data(data: dict):
    today = date.today()
    exams = [exam for exam in data.get("exams", []) if (d := parse_date(exam.get("date"))) and d >= today]
    tasks = [task for task in data.get("tasks", []) if (d := parse_date(task.get("due"))) and d >= today]
    chores = []
    for chore in data.get("chores", []):
        start = parse_date(chore.get("startDate"))
        end = parse_date(chore.get("endDate"))
        if start and (not end or end >= today):
            chores.append(chore)
    return exams, tasks, chores


def is_chore_active(chore: dict, d: date) -> bool:
    start = parse_date(chore.get("startDate"))
    end = parse_date(chore.get("endDate"))
    if not start or d < start or (end and d > end) or d.weekday() == 6:
        return False
    recurring = chore.get("frequency") == "recurring" or chore.get("recurring", False)
    if not recurring:
        return d == start
    interval = int(chore.get("interval", chore.get("intervalDays", 1))) or 1
    return (d - start).days % interval == 0


def voluntary_until_date(entry: dict, deadline_key: str, finish_early_days: int, get_minutes) -> date | None:
    """Let an entry stay voluntary until daily 20-minute work must begin."""
    deadline = parse_date(entry.get(deadline_key))
    if not deadline:
        return None

    finish_date = deadline - timedelta(days=finish_early_days)
    total_minutes = max(0, int(get_minutes(entry)))
    days_needed = max(1, (total_minutes + 19) // 20)

    # Count backwards from the desired finish date; Sundays are not study days.
    current = finish_date
    while current.weekday() == 6:
        current -= timedelta(days=1)
    for _ in range(days_needed - 1):
        current -= timedelta(days=1)
        while current.weekday() == 6:
            current -= timedelta(days=1)
    return current


def is_still_voluntary(entry: dict, entry_type: str, today: date | None = None) -> bool:
    """Missing legacy flags default to voluntary; the flag expires automatically."""
    if not bool(entry.get("freiwillig", True)):
        return False
    today = today or date.today()
    if entry_type == "exam":
        start_date = voluntary_until_date(entry, "date", 3, get_exam_minutes)
    else:
        start_date = voluntary_until_date(entry, "due", 7, get_task_minutes)
    return start_date is not None and today < start_date


def future_days_until(end_date: date, max_days: int = MAX_STUDY_DAYS) -> list[date]:
    result = []
    current = date.today()
    while current < end_date and len(result) < max_days:
        if current.weekday() != 6:
            result.append(current)
        current += timedelta(days=1)
    return result


def distribute_minutes(total_minutes: int, days: list[date], max_per_day: int = MAX_MINUTES_PER_DAY) -> dict[date, int]:
    if total_minutes <= 0 or not days:
        return {}
    total_minutes = (total_minutes // 15) * 15
    max_per_day = (max_per_day // 15) * 15
    result = {d: 0 for d in days}
    remaining = total_minutes
    while remaining >= 15:
        changed = False
        for d in days:
            if remaining < 15:
                break
            if result[d] < max_per_day:
                result[d] += 15
                remaining -= 15
                changed = True
        if not changed:
            break
    return result


def build_study_plan(exam: dict) -> dict[date, int]:
    exam_date = parse_date(exam.get("date"))
    return distribute_minutes(get_exam_minutes(exam), future_days_until(exam_date)) if exam_date else {}


def build_task_plan(task: dict) -> dict[date, int]:
    due_date = parse_date(task.get("due"))
    return distribute_minutes(get_task_minutes(task), future_days_until(due_date)) if due_date else {}


def build_all_plans(exams: list[dict], tasks: list[dict]):
    return ({i: build_study_plan(exam) for i, exam in enumerate(exams)}, {i: build_task_plan(task) for i, task in enumerate(tasks)})


def get_work_slots(d: date) -> list[tuple[datetime, datetime]]:
    """Liefert verfügbare Zeitfenster; 12:00–13:00 bleibt Mittagspause."""
    slots = []
    lunch_start = datetime.combine(d, parse_time("12:00"))
    lunch_end = datetime.combine(d, parse_time("13:00"))
    for start, end in WORK_HOURS.get(d.weekday(), []):
        slot_start = datetime.combine(d, parse_time(start))
        slot_end = datetime.combine(d, parse_time(end))
        if slot_end <= lunch_start or slot_start >= lunch_end:
            slots.append((slot_start, slot_end))
        else:
            if slot_start < lunch_start:
                slots.append((slot_start, lunch_start))
            if slot_end > lunch_end:
                slots.append((lunch_end, slot_end))
    return slots


def find_free_slot(d: date, busy: list[tuple[datetime, datetime]], duration: int):
    for slot_start, slot_end in get_work_slots(d):
        current = slot_start
        overlapping = sorted((start, end) for start, end in busy if end > slot_start and start < slot_end)
        for busy_start, busy_end in overlapping:
            if busy_start > current and minutes_between(current, busy_start) >= duration:
                return current, current + timedelta(minutes=duration)
            current = max(current, busy_end + timedelta(minutes=GAP_MINUTES))
        if current < slot_end and minutes_between(current, slot_end) >= duration:
            return current, current + timedelta(minutes=duration)
    return None


def get_day_items(d: date, exams: list[dict], tasks: list[dict], chores: list[dict], study_plans: dict, task_plans: dict) -> list[dict]:
    items: list[dict] = []
    busy: list[tuple[datetime, datetime]] = []

    # Feste Termine zuerst eintragen: Sie blockieren ihre Zeit für alle automatischen Einträge.
    try:
        fixed_events = load_data().get("fixed_events", [])
    except Exception:
        fixed_events = []
    for event in fixed_events:
        if parse_date(event.get("date")) != d:
            continue
        try:
            start_dt = datetime.combine(d, parse_time(str(event.get("start", ""))))
            end_dt = datetime.combine(d, parse_time(str(event.get("end", ""))))
        except (ValueError, TypeError):
            continue
        if end_dt <= start_dt:
            continue
        items.append({
            "title": event.get("title", "Fester Termin"),
            "start": start_dt,
            "end": end_dt,
            "type": "fixed_event",
            "color": COLOR_FIXED,
            "tooltip": format_calendar_tooltip(event.get("title", "Fester Termin"), "Fixer Termin", start_dt, end_dt, event),
        })
        busy.append((start_dt, end_dt))

    # Auch am Sonntag werden feste Termine angezeigt; automatische Planung bleibt aus.
    if d.weekday() == 6:
        return sorted(items, key=lambda item: item["start"])

    for chore in chores:
        if is_chore_active(chore, d):
            slot = find_free_slot(d, busy, int(chore.get("duration", 30)))
            if slot:
                start, end = slot
                chore_title = chore.get("title", "Ämtli")
                items.append({"title": chore_title, "start": start, "end": end, "type": "chore", "color": COLOR_CHORE,
                              "tooltip": format_calendar_tooltip(chore_title, "Ämtli", start, end, chore)})
                busy.append(slot)
    if d.weekday() != 6:
        work_slots = get_work_slots(d)
        overrides = st.session_state.get("_leisure_overrides_cache", {})
        # Use the loaded data passed through the day-plan cache when available; load_data is cached.
        try:
            overrides = load_data().get("leisure_overrides", {})
        except Exception:
            overrides = overrides or {}
        override = overrides.get(iso(d))
        leisure_slot = None
        if override is not None:
            if override.get("enabled", True):
                try:
                    start_dt = datetime.combine(d, parse_time(override["start"]))
                    end_dt = datetime.combine(d, parse_time(override["end"]))
                    if end_dt > start_dt and any(start_dt >= slot_start and end_dt <= slot_end for slot_start, slot_end in work_slots):
                        leisure_slot = (start_dt, end_dt)
                except (KeyError, ValueError, TypeError):
                    leisure_slot = None
        elif d.weekday() != 3 and work_slots:
            first_start, last_end = work_slots[0][0], work_slots[-1][1]
            midpoint = first_start + (last_end - first_start) / 2
            start_dt, end_dt = midpoint - timedelta(minutes=45), midpoint + timedelta(minutes=45)
            if any(start_dt >= slot_start and end_dt <= slot_end for slot_start, slot_end in work_slots):
                leisure_slot = (start_dt, end_dt)
        if leisure_slot:
            leisure_start, leisure_end = leisure_slot
            free = not any(not (leisure_end <= start or leisure_start >= end) for start, end in busy)
            if free:
                leisure_details = ["Hinweis: automatisch eingeplante Freizeit" if override is None else "Hinweis: individuell festgelegte Freizeit"]
                if override is not None:
                    leisure_details.append(f"Individuell aktiviert: {'Ja' if override.get('enabled', True) else 'Nein'}")
                items.append({"title": "Freizeit", "start": leisure_start, "end": leisure_end, "type": "leisure", "color": None,
                              "tooltip": format_calendar_tooltip("Freizeit", "Freizeit", leisure_start, leisure_end, override, leisure_details)})
                busy.append((leisure_start, leisure_end))
    for index, exam in enumerate(exams):
        duration = study_plans.get(index, {}).get(d, 0)
        slot = find_free_slot(d, busy, duration) if duration > 0 else None
        if slot:
            start, end = slot
            study_title = "Lernen: " + get_exam_title(exam)
            items.append({"title": study_title, "start": start, "end": end, "type": "study", "color": get_exam_color(exam),
                          "tooltip": format_calendar_tooltip(study_title, "Lernzeit", start, end, exam,
                                                             [f"Geplante Lernzeit an diesem Tag: {duration} Minuten"])})
            busy.append(slot)
    for index, task in enumerate(tasks):
        duration = task_plans.get(index, {}).get(d, 0)
        slot = find_free_slot(d, busy, duration) if duration > 0 else None
        if slot:
            start, end = slot
            task_title = get_task_title(task)
            items.append({"title": task_title, "start": start, "end": end, "type": "task", "task_index": index,
                          "done": bool(task.get("done", False)), "color": get_task_color(task),
                          "tooltip": format_calendar_tooltip(task_title, "Auftrag", start, end, task,
                                                             [f"Geplante Bearbeitungszeit an diesem Tag: {duration} Minuten"])})
            busy.append(slot)
    items.sort(key=lambda item: (item["start"] is None, item["start"] or datetime.max))
    return items


def format_time_range(item: dict) -> str:
    start, end = item.get("start"), item.get("end")
    return f"{start.strftime('%H:%M')} – {end.strftime('%H:%M')}" if start and end else ""


def get_entry_identifier(entry_type: str, entry: dict) -> str:
    """Liefert eine stabile Kennung zum Löschen eines Eintrags."""
    existing_id = str(entry.get("id", "")).strip()
    if existing_id:
        return existing_id

    fields_by_type = {
        "exams": ("subject", "title", "date", "hours", "duration"),
        "tasks": ("subject", "fach", "title", "due", "hours", "duration"),
        "chores": ("title", "startDate", "endDate", "duration", "frequency", "interval"),
        "fixed_events": ("title", "date", "start", "end"),
    }
    identity = {
        key: entry.get(key)
        for key in fields_by_type.get(entry_type, tuple(sorted(entry.keys())))
    }
    return hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def delete_entry(entry_type: str, entry_identifier: str) -> None:
    """Löscht genau einen Eintrag aus dem aktuellsten GitHub-Datenstand."""
    load_data.clear()
    current_data = load_data()
    entries = current_data.get(entry_type, [])

    delete_index = next(
        (
            index
            for index, entry in enumerate(entries)
            if get_entry_identifier(entry_type, entry) == entry_identifier
        ),
        None,
    )

    if delete_index is None:
        raise RuntimeError("Der Eintrag wurde in daten.json nicht gefunden.")

    deleted_entry = entries.pop(delete_index)

    if entry_type == "tasks":
        task_identifier = get_task_identifier(deleted_entry)
        sync_task_checkbox_keys(task_identifier, False)

    save_data(current_data, commit_message="Eintrag gelöscht")
    st.session_state["save_success"] = "Eintrag wurde gelöscht."
    st.session_state.pop("save_error", None)


def render_delete_button(
    entry_type: str,
    entry: dict,
    widget_prefix: str,
) -> None:
    """Rendert einen eindeutigen Löschknopf für einen Eintrag."""
    identifier = get_entry_identifier(entry_type, entry)
    if st.button(
        "🗑️",
        key=f"delete_{widget_prefix}_{entry_type}_{identifier}",
        help="Eintrag endgültig löschen",
        use_container_width=True,
    ):
        try:
            delete_entry(entry_type, identifier)
            st.rerun()
        except Exception as error:
            st.session_state["save_error"] = str(error)
            st.rerun()


def add_entry(entry_type: str, entry: dict) -> None:
    """Fügt einen Eintrag in den aktuellsten GitHub-Daten hinzu."""
    load_data.clear()
    current_data = load_data()
    current_data.setdefault(entry_type, []).append(entry)
    save_data(current_data, commit_message="Eintrag hinzugefügt")
    st.session_state["save_success"] = "Eintrag wurde hinzugefügt."
    st.session_state.pop("save_error", None)


def update_entry(entry_type: str, entry_identifier: str, updates: dict) -> None:
    """Aktualisiert einen Eintrag im aktuellsten GitHub-Datenstand."""
    load_data.clear()
    current_data = load_data()
    entries = current_data.setdefault(entry_type, [])
    entry = next((item for item in entries if get_entry_identifier(entry_type, item) == entry_identifier), None)
    if entry is None:
        raise RuntimeError("Der Eintrag wurde in daten.json nicht gefunden. Bitte aktualisieren und erneut versuchen.")
    entry.update(updates)
    save_data(current_data, commit_message="Eintrag bearbeitet")
    st.session_state["save_success"] = "Änderungen wurden gespeichert."
    st.session_state.pop("save_error", None)


def save_leisure_override(selected_date: date, enabled: bool, start_time: str, end_time: str) -> None:
    """Speichert eine individuelle Freizeit für einen bestimmten Tag."""
    start_dt = datetime.combine(selected_date, parse_time(start_time))
    end_dt = datetime.combine(selected_date, parse_time(end_time))
    if enabled and end_dt <= start_dt:
        raise ValueError("Das Ende der Freizeit muss nach dem Beginn liegen.")
    load_data.clear()
    current_data = load_data()
    overrides = current_data.setdefault("leisure_overrides", {})
    overrides[iso(selected_date)] = {"enabled": bool(enabled), "start": start_time, "end": end_time}
    save_data(current_data, commit_message="Freizeit bearbeitet")
    st.session_state["save_success"] = "Freizeit wurde gespeichert."
    st.session_state.pop("save_error", None)


def render_add_entry_forms() -> None:
    """Formulare zum Hinzufügen von Prüfungen, Aufträgen und Ämtli."""
    with st.expander("＋ Eintrag hinzufügen", expanded=False):
        exam_tab, task_tab, chore_tab, fixed_tab = st.tabs(["Prüfung", "Auftrag", "Ämtli", "Fixer Termin"])

        with exam_tab:
            with st.form("add_exam_form", clear_on_submit=True):
                subject = st.text_input("Fach und Thema", key="new_exam_subject")
                exam_date = st.date_input("Prüfungsdatum", min_value=date.today(), key="new_exam_date")
                hours = st.number_input("Lernaufwand in Stunden", min_value=0.25, value=1.0, step=0.25, key="new_exam_hours")
                submitted = st.form_submit_button("Prüfung hinzufügen", use_container_width=True)
                if submitted:
                    if not subject.strip():
                        st.error("Bitte Fach und Thema eingeben.")
                    else:
                        try:
                            add_entry("exams", {
                                "id": uuid.uuid4().hex,
                                "subject": subject.strip(),
                                "date": iso(exam_date),
                                "hours": hours,
                                "freiwillig": True,
                            })
                            st.rerun()
                        except Exception as error:
                            st.error("Prüfung konnte nicht gespeichert werden.")
                            st.code(str(error))

        with task_tab:
            with st.form("add_task_form", clear_on_submit=True):
                subject = st.text_input("Fach", key="new_task_subject")
                title = st.text_input("Auftrag", key="new_task_title")
                due_date = st.date_input("Fälligkeitsdatum", min_value=date.today(), key="new_task_due")
                hours = st.number_input("Aufwand in Stunden", min_value=0.25, value=1.0, step=0.25, key="new_task_hours")
                submitted = st.form_submit_button("Auftrag hinzufügen", use_container_width=True)
                if submitted:
                    if not title.strip():
                        st.error("Bitte einen Auftragstitel eingeben.")
                    else:
                        try:
                            add_entry("tasks", {
                                "id": uuid.uuid4().hex,
                                "subject": subject.strip(),
                                "title": title.strip(),
                                "due": iso(due_date),
                                "hours": hours,
                                "done": False,
                                "freiwillig": True,
                            })
                            st.rerun()
                        except Exception as error:
                            st.error("Auftrag konnte nicht gespeichert werden.")
                            st.code(str(error))

        with chore_tab:
            with st.form("add_chore_form", clear_on_submit=True):
                title = st.text_input("Ämtli", key="new_chore_title")
                start_date = st.date_input("Startdatum", min_value=date.today(), key="new_chore_start")
                has_end = st.checkbox("Enddatum festlegen", value=False, key="new_chore_has_end")
                end_date = st.date_input(
                    "Enddatum (wird nur verwendet, wenn oben aktiviert)",
                    min_value=start_date,
                    value=start_date,
                    key="new_chore_end",
                )
                duration = st.number_input("Dauer in Minuten", min_value=5, value=30, step=5, key="new_chore_duration")
                recurring = st.checkbox("Wiederkehrend", value=False, key="new_chore_recurring")
                interval = st.number_input(
                    "Intervall in Tagen (wird nur bei Wiederholung verwendet)",
                    min_value=1,
                    value=1,
                    step=1,
                    key="new_chore_interval",
                )
                submitted = st.form_submit_button("Ämtli hinzufügen", use_container_width=True)
                if submitted:
                    if not title.strip():
                        st.error("Bitte eine Bezeichnung für das Ämtli eingeben.")
                    elif has_end and end_date < start_date:
                        st.error("Das Enddatum darf nicht vor dem Startdatum liegen.")
                    else:
                        entry = {
                            "id": uuid.uuid4().hex,
                            "title": title.strip(),
                            "startDate": iso(start_date),
                            "duration": int(duration),
                            "frequency": "recurring" if recurring else "once",
                            "interval": int(interval) if recurring else 1,
                        }
                        if has_end:
                            entry["endDate"] = iso(end_date)
                        try:
                            add_entry("chores", entry)
                            st.rerun()
                        except Exception as error:
                            st.error("Ämtli konnte nicht gespeichert werden.")
                            st.code(str(error))

        with fixed_tab:
            with st.form("add_fixed_event_form", clear_on_submit=True):
                fixed_title = st.text_input("Bezeichnung", key="new_fixed_title")
                fixed_date = st.date_input("Datum", value=date.today(), key="new_fixed_date")
                fixed_start = st.time_input("Beginn", value=parse_time("08:00"), step=timedelta(minutes=15), key="new_fixed_start")
                fixed_end = st.time_input("Ende", value=parse_time("09:00"), step=timedelta(minutes=15), key="new_fixed_end")
                submitted = st.form_submit_button("Fixen Termin hinzufügen", use_container_width=True)
                if submitted:
                    if not fixed_title.strip():
                        st.error("Bitte eine Bezeichnung eingeben.")
                    elif fixed_end <= fixed_start:
                        st.error("Das Ende muss nach dem Beginn liegen.")
                    else:
                        new_start_dt = datetime.combine(fixed_date, fixed_start)
                        new_end_dt = datetime.combine(fixed_date, fixed_end)
                        try:
                            current_events = load_data().get("fixed_events", [])
                            overlaps = any(
                                parse_date(event.get("date")) == fixed_date
                                and parse_time(str(event.get("start"))) < fixed_end
                                and parse_time(str(event.get("end"))) > fixed_start
                                for event in current_events
                            )
                            if overlaps:
                                st.error("Dieser Termin überschneidet sich mit einem anderen fixen Termin.")
                            else:
                                add_entry("fixed_events", {
                                    "id": uuid.uuid4().hex,
                                    "title": fixed_title.strip(),
                                    "date": iso(fixed_date),
                                    "start": fixed_start.strftime("%H:%M"),
                                    "end": fixed_end.strftime("%H:%M"),
                                })
                                st.rerun()
                        except Exception as error:
                            st.error("Fixer Termin konnte nicht gespeichert werden.")
                            st.code(str(error))

    with st.expander("✎ Einträge bearbeiten", expanded=False):
        edit_exam_tab, edit_task_tab, edit_chore_tab, edit_leisure_tab, edit_fixed_tab = st.tabs(
            ["Prüfungen", "Aufträge", "Ämtli", "Freizeiten", "Fixe Termine"]
        )

        with edit_exam_tab:
            exams_now = load_data().get("exams", [])
            if not exams_now:
                st.info("Keine Prüfungen zum Bearbeiten vorhanden.")
            else:
                exam_labels = [f"{get_exam_title(e)} — {format_date(parse_date(e.get('date')))} [Eintrag {i + 1}]" for i, e in enumerate(exams_now)]
                selected_exam_label = st.selectbox("Prüfung auswählen", exam_labels, key="edit_exam_select")
                exam_index = exam_labels.index(selected_exam_label)
                exam = exams_now[exam_index]
                with st.form(f"edit_exam_form_{get_entry_identifier('exams', exam)}"):
                    new_subject = st.text_input("Fach und Thema", value=str(exam.get("subject") or exam.get("title") or ""))
                    new_date = st.date_input("Prüfungsdatum", value=parse_date(exam.get("date")) or date.today())
                    new_hours = st.number_input("Lernaufwand in Stunden", min_value=0.25, value=max(0.25, float(get_exam_minutes(exam) / 60)), step=0.25)
                    new_voluntary = st.checkbox("Freiwillig", value=bool(exam.get("freiwillig", False)), help="Kann durch den Filter ausgeblendet werden, solange die Vorbereitung noch nicht beginnen muss.")
                    submitted = st.form_submit_button("Prüfung speichern", use_container_width=True)
                    if submitted:
                        if not new_subject.strip():
                            st.error("Bitte Fach und Thema eingeben.")
                        else:
                            try:
                                update_entry("exams", get_entry_identifier("exams", exam), {"subject": new_subject.strip(), "date": iso(new_date), "hours": new_hours, "freiwillig": new_voluntary})
                                st.rerun()
                            except Exception as error:
                                st.error("Prüfung konnte nicht gespeichert werden.")
                                st.code(str(error))

        with edit_task_tab:
            tasks_now = load_data().get("tasks", [])
            if not tasks_now:
                st.info("Keine Aufträge zum Bearbeiten vorhanden.")
            else:
                task_labels = [f"{get_task_title(t)} — {format_date(parse_date(t.get('due')))} [Eintrag {i + 1}]" for i, t in enumerate(tasks_now)]
                selected_task_label = st.selectbox("Auftrag auswählen", task_labels, key="edit_task_select")
                task_index = task_labels.index(selected_task_label)
                task = tasks_now[task_index]
                with st.form(f"edit_task_form_{get_entry_identifier('tasks', task)}"):
                    new_subject = st.text_input("Fach", value=str(task.get("subject") or task.get("fach") or ""))
                    new_title = st.text_input("Auftrag", value=str(task.get("title") or ""))
                    new_due = st.date_input("Abgabetermin", value=parse_date(task.get("due")) or date.today())
                    new_hours = st.number_input("Bearbeitungszeit in Stunden", min_value=0.25, value=max(0.25, float(get_task_minutes(task) / 60)), step=0.25)
                    new_done = st.checkbox("Auftrag erledigt", value=bool(task.get("done", False)))
                    new_voluntary = st.checkbox("Freiwillig", value=bool(task.get("freiwillig", False)), help="Kann durch den Filter ausgeblendet werden, solange die Vorbereitung noch nicht beginnen muss.")
                    submitted = st.form_submit_button("Auftrag speichern", use_container_width=True)
                    if submitted:
                        if not new_title.strip():
                            st.error("Bitte einen Auftragstitel eingeben.")
                        else:
                            try:
                                update_entry("tasks", get_entry_identifier("tasks", task), {"subject": new_subject.strip(), "title": new_title.strip(), "due": iso(new_due), "hours": new_hours, "done": new_done, "freiwillig": new_voluntary})
                                st.rerun()
                            except Exception as error:
                                st.error("Auftrag konnte nicht gespeichert werden.")
                                st.code(str(error))

        with edit_chore_tab:
            chores_now = load_data().get("chores", [])
            if not chores_now:
                st.info("Keine Ämtli zum Bearbeiten vorhanden.")
            else:
                chore_labels = [f"{c.get('title', 'Ämtli')} — {format_date(parse_date(c.get('startDate')))} [Eintrag {i + 1}]" for i, c in enumerate(chores_now)]
                selected_chore_label = st.selectbox("Ämtli auswählen", chore_labels, key="edit_chore_select")
                chore_index = chore_labels.index(selected_chore_label)
                chore = chores_now[chore_index]
                chore_start = parse_date(chore.get("startDate")) or date.today()
                with st.form(f"edit_chore_form_{get_entry_identifier('chores', chore)}"):
                    new_title = st.text_input("Bezeichnung", value=str(chore.get("title") or ""))
                    new_start = st.date_input("Startdatum", value=chore_start)
                    has_end = st.checkbox("Enddatum festlegen", value=bool(chore.get("endDate")))
                    new_end = st.date_input("Enddatum", value=parse_date(chore.get("endDate")) or chore_start)
                    new_duration = st.number_input("Dauer in Minuten", min_value=5, value=max(5, int(chore.get("duration", 30))), step=5)
                    new_recurring = st.checkbox("Wiederkehrend", value=(chore.get("frequency") == "recurring" or bool(chore.get("recurring", False))))
                    new_interval = st.number_input("Intervall in Tagen", min_value=1, value=max(1, int(chore.get("interval", chore.get("intervalDays", 1)) or 1)), step=1)
                    submitted = st.form_submit_button("Ämtli speichern", use_container_width=True)
                    if submitted:
                        if not new_title.strip():
                            st.error("Bitte eine Bezeichnung eingeben.")
                        elif has_end and new_end < new_start:
                            st.error("Das Enddatum darf nicht vor dem Startdatum liegen.")
                        else:
                            updates = {"title": new_title.strip(), "startDate": iso(new_start), "duration": int(new_duration), "frequency": "recurring" if new_recurring else "once", "interval": int(new_interval) if new_recurring else 1}
                            if has_end:
                                updates["endDate"] = iso(new_end)
                            else:
                                updates["endDate"] = None
                            try:
                                update_entry("chores", get_entry_identifier("chores", chore), updates)
                                # Leeres Enddatum entfernen, damit der Datensatz sauber bleibt.
                                load_data.clear()
                                current_data = load_data()
                                saved_chore = next((c for c in current_data.get("chores", []) if get_entry_identifier("chores", c) == get_entry_identifier("chores", chore)), None)
                                if saved_chore is not None and saved_chore.get("endDate") is None:
                                    saved_chore.pop("endDate", None)
                                    save_data(current_data, commit_message="Ämtli bearbeitet")
                                st.rerun()
                            except Exception as error:
                                st.error("Ämtli konnte nicht gespeichert werden.")
                                st.code(str(error))

        with edit_leisure_tab:
            leisure_date = st.date_input("Datum der Freizeit", value=date.today(), key="edit_leisure_date")
            overrides = load_data().get("leisure_overrides", {})
            override = overrides.get(iso(leisure_date))
            work_slots = get_work_slots(leisure_date)
            if override:
                default_start = str(override.get("start", "17:00"))
                default_end = str(override.get("end", "18:30"))
                default_enabled = bool(override.get("enabled", True))
            elif work_slots:
                first_start, last_end = work_slots[0][0], work_slots[-1][1]
                midpoint = first_start + (last_end - first_start) / 2
                default_start = (midpoint - timedelta(minutes=45)).strftime("%H:%M")
                default_end = (midpoint + timedelta(minutes=45)).strftime("%H:%M")
                default_enabled = leisure_date.weekday() != 3
            else:
                default_start, default_end, default_enabled = "17:00", "18:30", False
            with st.form("edit_leisure_form"):
                enabled = st.checkbox("Freizeit an diesem Tag einplanen", value=default_enabled)
                start_time = st.text_input("Beginn (HH:MM)", value=default_start, help="24-Stunden-Format, z. B. 17:00")
                end_time = st.text_input("Ende (HH:MM)", value=default_end, help="24-Stunden-Format, z. B. 18:30")
                submitted = st.form_submit_button("Freizeit speichern", use_container_width=True)
                if submitted:
                    try:
                        parse_time(start_time)
                        parse_time(end_time)
                        if enabled and not any(datetime.combine(leisure_date, parse_time(start_time)) >= slot_start and datetime.combine(leisure_date, parse_time(end_time)) <= slot_end and parse_time(end_time) > parse_time(start_time) for slot_start, slot_end in work_slots):
                            raise ValueError("Die Freizeit muss vollständig innerhalb eines verfügbaren Zeitfensters liegen.")
                        save_leisure_override(leisure_date, enabled, start_time, end_time)
                        st.rerun()
                    except Exception as error:
                        st.error("Freizeit konnte nicht gespeichert werden.")
                        st.code(str(error))

        with edit_fixed_tab:
            fixed_now = load_data().get("fixed_events", [])
            if not fixed_now:
                st.info("Keine fixen Termine zum Bearbeiten vorhanden.")
            else:
                fixed_labels = [
                    f"{event.get('title', 'Fixer Termin')} — {format_date(parse_date(event.get('date')))} {event.get('start', '')} [Eintrag {i + 1}]"
                    for i, event in enumerate(fixed_now)
                ]
                selected_fixed_label = st.selectbox("Fixen Termin auswählen", fixed_labels, key="edit_fixed_select")
                fixed_event = fixed_now[fixed_labels.index(selected_fixed_label)]
                fixed_date_value = parse_date(fixed_event.get("date")) or date.today()
                try:
                    fixed_start_value = parse_time(str(fixed_event.get("start", "08:00")))
                    fixed_end_value = parse_time(str(fixed_event.get("end", "09:00")))
                except ValueError:
                    fixed_start_value, fixed_end_value = parse_time("08:00"), parse_time("09:00")
                with st.form(f"edit_fixed_event_form_{get_entry_identifier('fixed_events', fixed_event)}"):
                    edit_fixed_title = st.text_input("Bezeichnung", value=str(fixed_event.get("title", "")))
                    edit_fixed_date = st.date_input("Datum", value=fixed_date_value)
                    edit_fixed_start = st.time_input("Beginn", value=fixed_start_value, step=timedelta(minutes=15))
                    edit_fixed_end = st.time_input("Ende", value=fixed_end_value, step=timedelta(minutes=15))
                    save_fixed = st.form_submit_button("Fixen Termin speichern", use_container_width=True)
                    if save_fixed:
                        if not edit_fixed_title.strip():
                            st.error("Bitte eine Bezeichnung eingeben.")
                        elif edit_fixed_end <= edit_fixed_start:
                            st.error("Das Ende muss nach dem Beginn liegen.")
                        else:
                            try:
                                event_id = get_entry_identifier("fixed_events", fixed_event)
                                latest = load_data()
                                conflicts = any(
                                    get_entry_identifier("fixed_events", event) != event_id
                                    and parse_date(event.get("date")) == edit_fixed_date
                                    and parse_time(str(event.get("start"))) < edit_fixed_end
                                    and parse_time(str(event.get("end"))) > edit_fixed_start
                                    for event in latest.get("fixed_events", [])
                                )
                                if conflicts:
                                    st.error("Dieser Termin überschneidet sich mit einem anderen fixen Termin.")
                                else:
                                    update_entry("fixed_events", event_id, {
                                        "title": edit_fixed_title.strip(),
                                        "date": iso(edit_fixed_date),
                                        "start": edit_fixed_start.strftime("%H:%M"),
                                        "end": edit_fixed_end.strftime("%H:%M"),
                                    })
                                    st.rerun()
                            except Exception as error:
                                st.error("Fixer Termin konnte nicht gespeichert werden.")
                                st.code(str(error))
                render_delete_button("fixed_events", fixed_event, "edit_fixed_event")


def render_overview(data, exams, tasks, chores, study_plans, task_plans) -> None:
    today = date.today()
    success = st.session_state.pop("save_success", None)
    error = st.session_state.pop("save_error", None)
    if success:
        st.success(success)
    if st.session_state.pop("show_balloons", False):
        st.balloons()
    if error:
        st.error("GitHub-Speicherung fehlgeschlagen.")
        st.code(error)

    render_add_entry_forms()
    render_section_title("Heute")
    today_items = get_day_items(today, exams, tasks, chores, study_plans, task_plans)
    if not today_items:
        st.info("Für heute ist nichts geplant.")
    for index, item in enumerate(today_items):
        col1, col2 = st.columns([0.05, 0.95])
        task = tasks[item["task_index"]] if item.get("type") == "task" else None
        with col1:
            if task:
                checked = render_task_checkbox(task, "today_task_done")
            elif item.get("type") == "fixed_event":
                checked = False
            else:
                checked = render_daily_checkbox(data, item, today, "overview")
        with col2:
            render_item_card(item["title"], format_time_range(item), item.get("color"), done=checked)

    render_section_title("Prüfungen")
    if not exams:
        st.info("Keine kommenden Prüfungen.")
    for exam in exams:
        card_col, delete_col = st.columns([0.94, 0.06])
        with card_col:
            render_item_card(
                get_exam_title(exam),
                format_date(parse_date(exam.get("date"))),
                get_exam_color(exam),
            )
        with delete_col:
            render_delete_button("exams", exam, "overview_exam")

    render_section_title("Aufträge")
    if not tasks:
        st.info("Keine offenen Aufträge.")
    for task in tasks:
        check_col, card_col, delete_col = st.columns([0.05, 0.89, 0.06])
        with check_col:
            checked = render_task_checkbox(task, "task_done")
        with card_col:
            render_item_card(
                get_task_title(task),
                f"Fällig: {format_date(parse_date(task.get('due')))}",
                get_task_color(task),
                done=checked,
            )
        with delete_col:
            render_delete_button("tasks", task, "overview_task")

    render_section_title("Ämtli")
    active_chores = [chore for chore in chores if is_chore_active(chore, today)]
    if not active_chores:
        st.info("Heute keine Ämtli.")
    for chore in active_chores:
        card_col, delete_col = st.columns([0.94, 0.06])
        with card_col:
            render_item_card(chore.get("title", "Ämtli"), color=COLOR_CHORE)
        with delete_col:
            render_delete_button("chores", chore, "overview_chore")


def render_week(data, exams, tasks, chores, study_plans, task_plans) -> None:
    """Outlook-ähnlicher Wochenkalender von 08:00 bis 20:00 Uhr."""
    st.session_state.setdefault("week_offset", 0)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("← Vorherige Woche", key="previous_week"):
            st.session_state.week_offset -= 1
            st.rerun()
    with col2:
        render_centered_heading("Wochenansicht")
    with col3:
        if st.button("Nächste Woche →", key="next_week"):
            st.session_state.week_offset += 1
            st.rerun()
    if st.button("Heute", key="today_week"):
        st.session_state.week_offset = 0
        st.rerun()

    today = date.today()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=st.session_state.week_offset)
    days = [monday + timedelta(days=i) for i in range(7)]
    start_hour, end_hour = 8, 20
    minutes_per_day = (end_hour - start_hour) * 60
    row_height = 36  # 30-Minuten-Zeile
    grid_height = 24 * row_height

    html = [
        '<div style="overflow-x:auto;width:100%;">',
        '<div style="min-width:1000px;display:grid;grid-template-columns:58px repeat(7,minmax(125px,1fr));font-family:Arial,sans-serif;color:#1C2430;">',
        '<div style="height:58px;border-bottom:1px solid #DADFD6;"></div>'
    ]
    for d in days:
        today_style = 'background:#E5EEF9;' if d == today else 'background:#F7F8F6;'
        html.append(
            f'<div style="height:58px;box-sizing:border-box;text-align:center;padding:8px 3px;'
            f'border-bottom:1px solid #DADFD6;border-left:1px solid #DADFD6;{today_style}">'
            f'<div style="font-size:12px;color:#5B6472;">{WEEKDAYS[d.weekday()]}</div>'
            f'<div style="font-size:17px;font-weight:700;margin-top:4px;">{d.day}. {d.strftime("%m.")}</div></div>'
        )

    # Zeitachse links; eine Zeile entspricht 30 Minuten.
    html.append(f'<div style="height:{grid_height}px;position:relative;background:#F7F8F6;">')
    for i in range(24):
        minute = i * 30
        label = f"{start_hour + minute // 60:02d}:{minute % 60:02d}"
        html.append(f'<div style="position:absolute;top:{i * row_height - 8}px;right:7px;font-size:11px;color:#687180;">{label}</div>')
    html.append('</div>')

    for d in days:
        items = get_day_items(d, exams, tasks, chores, study_plans, task_plans)
        due_tasks = [task for task in tasks if parse_date(task.get("due")) == d]
        html.append(f'<div style="height:{grid_height}px;box-sizing:border-box;position:relative;border-left:1px solid #DADFD6;border-bottom:1px solid #DADFD6;background:#fff;'
                    'background-image:repeating-linear-gradient(to bottom,transparent 0,transparent 35px,#E5E8E3 35px,#E5E8E3 36px);">')
        # Zusätzliche feinere Linien bei jeder vollen Stunde.
        for hour in range(1, 12):
            y = hour * 2 * row_height
            html.append(f'<div style="position:absolute;left:0;right:0;top:{y}px;border-top:1px solid #CBD1CA;pointer-events:none;"></div>')
        # Mittagspause bleibt sichtbar und wird nicht als Arbeitszeit verplant.
        lunch_top = (12 - start_hour) * 60 / 30 * row_height
        html.append(f'<div style="position:absolute;left:0;right:0;top:{lunch_top}px;height:{2 * row_height}px;background:#F0F1EF;opacity:.95;pointer-events:none;border-top:1px dashed #B6BDB4;border-bottom:1px dashed #B6BDB4;"></div>')
        html.append(f'<div style="position:absolute;left:3px;right:3px;top:{lunch_top + 5}px;text-align:center;color:#687180;font-size:10px;pointer-events:none;">Mittagspause</div>')

        for item in items:
            start_dt, end_dt = item.get("start"), item.get("end")
            if not start_dt or not end_dt:
                continue
            start_min = start_dt.hour * 60 + start_dt.minute - start_hour * 60
            end_min = end_dt.hour * 60 + end_dt.minute - start_hour * 60
            if end_min <= 0 or start_min >= minutes_per_day:
                continue
            start_min = max(0, start_min)
            end_min = min(minutes_per_day, end_min)
            top = start_min / minutes_per_day * grid_height
            height = max(18, (end_min - start_min) / minutes_per_day * grid_height)
            color = item.get("color")
            bg = rgb_to_css(color) if color else "#DDE8F7"
            # Use a slightly tinted event background and a clear left accent.
            title = escape_html(item.get("title", "Eintrag"))
            tooltip_text = item.get("tooltip") or format_calendar_tooltip(item.get("title", "Eintrag"), item.get("type", "Eintrag"), start_dt, end_dt)
            tooltip_attr = escape_html(tooltip_text).replace("\n", "&#10;")
            time_label = f'{start_dt.strftime("%H:%M")}–{end_dt.strftime("%H:%M")}'
            done = bool(item.get("done", False))
            decoration = 'text-decoration:line-through;opacity:.65;' if done else ''
            html.append(
                f'<div title="{tooltip_attr}" style="position:absolute;z-index:2;left:3px;right:3px;top:{top:.1f}px;height:{height:.1f}px;'
                f'box-sizing:border-box;overflow:hidden;padding:3px 4px;border-radius:4px;border-left:3px solid {bg};'
                f'background:color-mix(in srgb,{bg} 18%,white);font-size:10px;line-height:1.25;{decoration}">'
                f'<div style="font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{title}</div>'
                f'<div style="font-size:9px;color:#4E5968;">{time_label}</div></div>'
            )

        if due_tasks:
            due_parts = []
            for task in due_tasks:
                due_title = get_task_title(task)
                due_start = datetime.combine(d, parse_time("00:00"))
                due_end = datetime.combine(d, parse_time("23:59"))
                due_tooltip = escape_html(format_calendar_tooltip(due_title, "Fälliger Auftrag", due_start, due_end, task)).replace("\n", "&#10;")
                due_parts.append(f'<span title="{due_tooltip}">• {escape_html(due_title)}</span>')
            due_html = '<br>'.join(due_parts)
            html.append(f'<div style="position:absolute;z-index:3;left:3px;right:3px;top:3px;background:#FFF4CC;border:1px solid #E5C65B;border-radius:4px;padding:3px;font-size:10px;">Fällig:<br>{due_html}</div>')
        html.append('</div>')

    html.append('</div></div>')
    render_html(''.join(html))
    st.caption("Die Zeilen zeigen 30-Minuten-Schritte. Termine können kürzer sein, z. B. 15 Minuten. 12:00–13:00 ist als Mittagspause reserviert.")


def render_selected_day(
    data,
    selected_date,
    exams,
    tasks,
    chores,
    study_plans,
    task_plans,
) -> None:
    """Zeigt den ausgewählten Kalendertag wie Übersicht -> Heute."""
    render_section_title(
        f"{WEEKDAYS[selected_date.weekday()]}, {format_date(selected_date)}"
    )

    items = get_day_items(
        selected_date,
        exams,
        tasks,
        chores,
        study_plans,
        task_plans,
    )

    due_tasks = [
        task
        for task in tasks
        if parse_date(task.get("due")) == selected_date
    ]

    if not items and not due_tasks:
        st.info("Für diesen Tag ist nichts geplant.")
        return

    shown_due_task_ids = set()

    for index, item in enumerate(items):
        col1, col2 = st.columns([0.05, 0.95])
        task = None

        if item.get("type") == "task":
            task_index = item.get("task_index")
            if isinstance(task_index, int) and 0 <= task_index < len(tasks):
                task = tasks[task_index]

        with col1:
            if task is not None:
                checked = render_task_checkbox(
                    task,
                    f"month_task_done_{iso(selected_date)}",
                )
                if parse_date(task.get("due")) == selected_date:
                    shown_due_task_ids.add(get_task_identifier(task))
            elif item.get("type") == "chore" and selected_date != date.today():
                checked = get_daily_completion(
                    data,
                    get_daily_item_identifier(item, selected_date),
                )
                st.checkbox(
                    "",
                    value=checked,
                    key=f"month_readonly_{iso(selected_date)}_{index}",
                    disabled=True,
                    help="Ämtli können nur am heutigen Tag abgehakt werden.",
                )
            else:
                checked = render_daily_checkbox(data, item, selected_date, "month")

        with col2:
            render_item_card(
                item["title"],
                format_time_range(item),
                item.get("color"),
                done=checked,
            )

    remaining_due_tasks = [
        task
        for task in due_tasks
        if get_task_identifier(task) not in shown_due_task_ids
    ]

    if remaining_due_tasks:
        st.caption("An diesem Tag fällig")

    for task in remaining_due_tasks:
        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            checked = render_task_checkbox(
                task,
                f"month_due_done_{iso(selected_date)}",
            )
        with col2:
            render_item_card(
                f"📌 {get_task_title(task)}",
                "Auftrag fällig",
                get_task_color(task),
                done=checked,
            )


def render_month(
    data,
    exams,
    tasks,
    chores,
    study_plans,
    task_plans,
) -> None:
    """Monatskalender mit auswählbarem Tag und Tagesdetailansicht."""
    st.session_state.setdefault("month_offset", 0)
    st.session_state.setdefault("selected_calendar_date", iso(date.today()))

    today = date.today()
    month_index = (
        today.year * 12
        + today.month
        - 1
        + st.session_state.month_offset
    )
    year = month_index // 12
    month = month_index % 12 + 1

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("← Vorheriger Monat", key="previous_month"):
            st.session_state.month_offset -= 1
            st.rerun()

    with col2:
        render_centered_heading(
            f"{MONTH_NAMES[month - 1]} {year}",
            size="1.35rem",
        )

    with col3:
        if st.button("Nächster Monat →", key="next_month"):
            st.session_state.month_offset += 1
            st.rerun()

    if st.button("Heute", key="today_month"):
        st.session_state.month_offset = 0
        st.session_state.selected_calendar_date = iso(today)
        st.rerun()

    weekday_columns = st.columns(7)
    for index, weekday in enumerate(WEEKDAYS):
        with weekday_columns[index]:
            st.markdown(
                f"<div style='text-align:center;color:#5B6472;"
                f"font-family:monospace;font-weight:600'>{weekday}</div>",
                unsafe_allow_html=True,
            )

    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)

    for week_index, week in enumerate(weeks):
        day_columns = st.columns(7)

        for day_index, current_date in enumerate(week):
            with day_columns[day_index]:
                outside = current_date.month != month
                selected = (
                    st.session_state.selected_calendar_date
                    == iso(current_date)
                )

                exam_count = sum(
                    1 for exam in exams
                    if exam.get("date") == iso(current_date)
                )
                task_count = sum(
                    1 for task in tasks
                    if task.get("due") == iso(current_date)
                )
                chore_count = sum(
                    1 for chore in chores
                    if is_chore_active(chore, current_date)
                )

                indicators = ""
                if exam_count:
                    indicators += "🔴"
                if task_count:
                    indicators += "🟡"
                if chore_count:
                    indicators += "🟢"

                label = f"{current_date.day}"
                if indicators:
                    label += f"\n{indicators}"

                button_type = "primary" if selected else "secondary"

                if st.button(
                    label,
                    key=f"calendar_day_{iso(current_date)}_{week_index}",
                    use_container_width=True,
                    type=button_type,
                    disabled=outside,
                ):
                    st.session_state.selected_calendar_date = iso(current_date)
                    st.rerun()

    selected_date = parse_date(
        st.session_state.selected_calendar_date
    ) or today

    if selected_date.year == year and selected_date.month == month:
        render_selected_day(
            data,
            selected_date,
            exams,
            tasks,
            chores,
            study_plans,
            task_plans,
        )
    else:
        st.info("Wähle einen Tag im angezeigten Monat aus.")


def main() -> None:
    inject_css()
    st.title("Semesterplaner")
    try:
        data = load_data()
    except Exception as error:
        st.error("Die Daten konnten nicht von GitHub geladen werden.")
        st.code(str(error))
        st.stop()
    exams, tasks, chores = prepare_data(data)
    hide_voluntary = st.checkbox(
        "Freiwillige Prüfungen und Aufträge ausblenden",
        value=True,
        help="Freiwillige Einträge werden automatisch wieder angezeigt, sobald die tägliche 20-Minuten-Vorbereitung beginnen muss.",
    )
    if hide_voluntary:
        exams = [exam for exam in exams if not is_still_voluntary(exam, "exam")]
        tasks = [task for task in tasks if not is_still_voluntary(task, "task")]
    study_plans, task_plans = build_all_plans(exams, tasks)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Prüfungen", len(exams))
    with col2:
        st.metric("Aufträge", len(tasks))
    with col3:
        st.metric("Ämtli", len(chores))
    with col4:
        if st.button("↻ Aktualisieren", key="reload"):
            load_data.clear()
            st.rerun()
    tab_overview, tab_week, tab_month = st.tabs(["Übersicht", "Woche", "Monat"])
    with tab_overview:
        render_overview(data, exams, tasks, chores, study_plans, task_plans)
    with tab_week:
        render_week(data, exams, tasks, chores, study_plans, task_plans)
    with tab_month:
        render_month(data, exams, tasks, chores, study_plans, task_plans)


if __name__ == "__main__":
    main()
