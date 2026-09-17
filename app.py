from __future__ import annotations

import base64
import calendar
import hashlib
import json
from datetime import date, datetime, timedelta
from html import escape

import requests
import streamlit as st

st.set_page_config(
    page_title="Semesterplaner",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

COLOR_CHORE = (61, 139, 135)
COLOR_SUBJECT_DEFAULT = (0, 255, 255)
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
    "Latein": (0, 255, 255),
}
WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTH_NAMES = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
GAP_MINUTES = 10
MAX_STUDY_DAYS = 10
MAX_MINUTES_PER_DAY = 45
WORK_HOURS = {
    0: [("13:00", "20:00")],
    1: [("13:00", "20:00")],
    2: [("13:00", "14:00"), ("18:00", "20:00")],
    3: [("16:30", "20:00")],
    4: [("17:00", "20:00")],
    5: [("08:00", "20:00")],
    6: [],
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
    values = (task.get("subject"), task.get("fach"), task.get("title"))
    return get_subject_color(" ".join(str(value) for value in values if value))


def render_item_card(
    title: str,
    meta: str = "",
    color: tuple[int, int, int] | None = None,
    done: bool = False,
) -> None:
    meta_html = f'<div class="item-meta">{escape_html(meta)}</div>' if meta else ""
    title_style = ' style="text-decoration:line-through;opacity:.55;"' if done else ""
    color_style = f' style="border-left:5px solid {rgb_to_css(color)};"' if color else ""
    render_html(
        f'<div class="item-card"{color_style}>'
        f'<div class="item-title"{title_style}>{escape_html(title)}</div>'
        f'{meta_html}</div>'
    )


def inject_css() -> None:
    render_html("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Libre+Baskerville:wght@400;700&family=Source+Sans+3:wght@400;500;600;700&display=swap');
    :root{--bg:#EEF1EC;--ink:#1C2430;--muted:#5B6472;--border:#DADFD6;--white:#FFF}
    html{color-scheme:light!important}
    body,[data-testid="stAppViewContainer"],[data-testid="stAppViewContainer"]>.main{background:var(--bg)!important;color:var(--ink)!important}
    [data-testid="stHeader"],[data-testid="stToolbar"]{display:none}
    #MainMenu,footer{visibility:hidden}
    .block-container{max-width:1400px;padding-top:2rem;padding-bottom:3rem}
    h1,h2,h3{color:var(--ink);font-family:"Libre Baskerville",serif}
    .section-title{color:var(--ink);font-family:"Libre Baskerville",serif;font-size:1.3rem;font-weight:700;margin:1.2rem 0 .8rem}
    .item-card{background:var(--white);border:1px solid var(--border);border-radius:10px;padding:.75rem 1rem;margin-bottom:.5rem}
    .item-title{color:var(--ink);font-size:1rem;font-weight:600}
    .item-meta{color:var(--muted);font-size:.85rem;margin-top:.15rem}
    </style>
    """)


def parse_date(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError:
        return None


def iso(value: date) -> str:
    return value.isoformat()


def format_date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def format_short_date(value: date | None) -> str:
    return value.strftime("%d.%m.") if value else ""


def parse_time(value: str):
    return datetime.strptime(value, "%H:%M").time()


def minutes_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() / 60)


def get_exam_title(exam: dict) -> str:
    return exam.get("subject") or exam.get("title") or "Prüfung"


def get_exam_minutes(exam: dict) -> int:
    if "hours" in exam:
        return int(exam.get("hours", 0)) * 60
    return int(exam.get("duration", 45))


def get_task_title(task: dict) -> str:
    return task.get("title") or "Auftrag"


def get_task_minutes(task: dict) -> int:
    if "hours" in task:
        return int(task.get("hours", 0)) * 60
    return int(task.get("duration", 45))


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
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


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
    if response.status_code in messages:
        return messages[response.status_code]
    return f"{fallback} GitHub meldet: {message}" if message else f"{fallback} HTTP-Status {response.status_code}"


def decode_github_content(payload: dict) -> dict:
    content = payload.get("content")
    if not content:
        raise RuntimeError("GitHub hat keinen Dateiinhalt zurückgegeben.")
    try:
        decoded = base64.b64decode(content.replace("\n", "")).decode("utf-8")
        data = json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("daten.json konnte nicht gelesen werden.") from error
    if not isinstance(data, dict):
        raise RuntimeError("daten.json muss ein JSON-Objekt enthalten.")
    for key in ("exams", "tasks", "chores"):
        data.setdefault(key, [])
    data.setdefault("completions", {})
    return data


@st.cache_data(ttl=60)
def load_data() -> dict:
    token, repo, file_path, branch = get_github_config()
    response = requests.get(
        get_github_url(repo, file_path),
        headers=get_github_headers(token),
        params={"ref": branch},
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(get_github_error_message(response, "Daten konnten nicht geladen werden."))
    return decode_github_content(response.json())


def build_save_content(data: dict) -> dict:
    return {
        "exams": data.get("exams", []),
        "tasks": data.get("tasks", []),
        "chores": data.get("chores", []),
        "completions": data.get("completions", {}),
    }


def save_data(data: dict, commit_message: str = "Status aktualisiert") -> None:
    token, repo, file_path, branch = get_github_config()
    url = get_github_url(repo, file_path)
    headers = get_github_headers(token)
    encoded = base64.b64encode(
        json.dumps(build_save_content(data), ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    for attempt in range(2):
        metadata = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
        if not metadata.ok:
            raise RuntimeError(get_github_error_message(metadata, "Aktueller Dateistand konnte nicht gelesen werden."))
        sha = metadata.json().get("sha")
        if not sha:
            raise RuntimeError("GitHub hat keinen SHA-Wert zurückgegeben.")
        response = requests.put(
            url,
            headers=headers,
            json={"message": commit_message, "content": encoded, "sha": sha, "branch": branch},
            timeout=20,
        )
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
    return hashlib.sha256(
        json.dumps(identity, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def update_task_done(data: dict, task_identifier: str, done: bool) -> None:
    for task in data.get("tasks", []):
        if get_task_identifier(task) == task_identifier:
            task["done"] = bool(done)
            return
    raise RuntimeError("Der Auftrag wurde in daten.json nicht gefunden.")


def sync_task_checkbox_keys(task_identifier: str, done: bool) -> None:
    suffix = f"_{task_identifier}"
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.endswith(suffix) and "task_done" in key:
            st.session_state[key] = done


def save_task_checkbox(task_identifier: str, checkbox_key: str) -> None:
    checked = bool(st.session_state.get(checkbox_key, False))
    try:
        load_data.clear()
        current_data = load_data()
        update_task_done(current_data, task_identifier, checked)
        save_data(current_data, "Auftragsstatus aktualisiert")
        sync_task_checkbox_keys(task_identifier, checked)
        st.session_state["save_success"] = "Auftrag wurde gespeichert."
        st.session_state.pop("save_error", None)
    except Exception as error:
        st.session_state[checkbox_key] = not checked
        sync_task_checkbox_keys(task_identifier, not checked)
        st.session_state["save_error"] = str(error)


def render_task_checkbox(task: dict, widget_prefix: str) -> bool:
    identifier = get_task_identifier(task)
    key = f"{widget_prefix}_task_done_{identifier}"
    if key not in st.session_state:
        st.session_state[key] = bool(task.get("done", False))
    st.checkbox("", key=key, on_change=save_task_checkbox, args=(identifier, key))
    return bool(st.session_state[key])


def get_daily_item_identifier(item: dict, item_date: date) -> str:
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


def sync_daily_checkbox_keys(item_identifier: str, done: bool) -> None:
    suffix = f"daily_done_{item_identifier}"
    for key in list(st.session_state.keys()):
        if isinstance(key, str) and key.endswith(suffix):
            st.session_state[key] = done


def save_daily_checkbox(item_identifier: str, checkbox_key: str) -> None:
    checked = bool(st.session_state.get(checkbox_key, False))
    try:
        load_data.clear()
        current_data = load_data()
        completions = current_data.setdefault("completions", {})
        if checked:
            completions[item_identifier] = True
        else:
            completions.pop(item_identifier, None)
        save_data(current_data, "Tagesstatus aktualisiert")
        sync_daily_checkbox_keys(item_identifier, checked)
        st.session_state["save_success"] = "Status wurde gespeichert."
        st.session_state.pop("save_error", None)
    except Exception as error:
        st.session_state[checkbox_key] = not checked
        sync_daily_checkbox_keys(item_identifier, not checked)
        st.session_state["save_error"] = str(error)


def render_daily_checkbox(data: dict, item: dict, item_date: date, widget_prefix: str) -> bool:
    identifier = get_daily_item_identifier(item, item_date)
    key = f"{widget_prefix}_daily_done_{identifier}"
    if key not in st.session_state:
        st.session_state[key] = get_daily_completion(data, identifier)
    st.checkbox("", key=key, on_change=save_daily_checkbox, args=(identifier, key))
    return bool(st.session_state[key])


def prepare_data(data: dict):
    today = date.today()
    exams = [exam for exam in data.get("exams", []) if (exam_date := parse_date(exam.get("date"))) and exam_date >= today]
    tasks = [task for task in data.get("tasks", []) if (due_date := parse_date(task.get("due"))) and due_date >= today]
    chores = []
    for chore in data.get("chores", []):
        start = parse_date(chore.get("startDate"))
        end = parse_date(chore.get("endDate"))
        if start and (not end or end >= today):
            chores.append(chore)
    return exams, tasks, chores


def is_chore_active(chore: dict, day: date) -> bool:
    start = parse_date(chore.get("startDate"))
    end = parse_date(chore.get("endDate"))
    if not start or day < start or (end and day > end) or day.weekday() == 6:
        return False
    recurring = chore.get("frequency") == "recurring" or chore.get("recurring", False)
    if not recurring:
        return day == start
    interval = int(chore.get("interval", chore.get("intervalDays", 1))) or 1
    return (day - start).days % interval == 0


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
    result = {day: 0 for day in days}
    remaining = total_minutes
    while remaining >= 15:
        changed = False
        for day in days:
            if remaining < 15:
                break
            if result[day] < max_per_day:
                result[day] += 15
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
    study_plans = {index: build_study_plan(exam) for index, exam in enumerate(exams)}
    task_plans = {index: build_task_plan(task) for index, task in enumerate(tasks)}
    return study_plans, task_plans


def get_work_slots(day: date) -> list[tuple[datetime, datetime]]:
    return [
        (datetime.combine(day, parse_time(start)), datetime.combine(day, parse_time(end)))
        for start, end in WORK_HOURS.get(day.weekday(), [])
    ]


def find_free_slot(day: date, busy: list[tuple[datetime, datetime]], duration: int):
    for slot_start, slot_end in get_work_slots(day):
        current = slot_start
        overlapping = sorted((start, end) for start, end in busy if end > slot_start and start < slot_end)
        for busy_start, busy_end in overlapping:
            if busy_start > current and minutes_between(current, busy_start) >= duration:
                return current, current + timedelta(minutes=duration)
            current = max(current, busy_end + timedelta(minutes=GAP_MINUTES))
        if current < slot_end and minutes_between(current, slot_end) >= duration:
            return current, current + timedelta(minutes=duration)
    return None


def get_day_items(day: date, exams: list[dict], tasks: list[dict], chores: list[dict], study_plans: dict, task_plans: dict) -> list[dict]:
    items: list[dict] = []
    busy: list[tuple[datetime, datetime]] = []
    if day.weekday() == 6:
        return items
    for chore in chores:
        if is_chore_active(chore, day):
            slot = find_free_slot(day, busy, int(chore.get("duration", 30)))
            if slot:
                start, end = slot
                items.append({"title": chore.get("title", "Ämtli"), "start": start, "end": end, "type": "chore", "color": COLOR_CHORE})
                busy.append(slot)
    if day.weekday() != 3:
        work_slots = get_work_slots(day)
        if work_slots:
            first_start, last_end = work_slots[0][0], work_slots[-1][1]
            midpoint = first_start + (last_end - first_start) / 2
            leisure_start = midpoint - timedelta(minutes=45)
            leisure_end = midpoint + timedelta(minutes=45)
            free = not any(not (leisure_end <= start or leisure_start >= end) for start, end in busy)
            if leisure_start >= first_start and leisure_end <= last_end and free:
                items.append({"title": "Freizeit", "start": leisure_start, "end": leisure_end, "type": "leisure", "color": None})
                busy.append((leisure_start, leisure_end))
    for index, exam in enumerate(exams):
        duration = study_plans.get(index, {}).get(day, 0)
        slot = find_free_slot(day, busy, duration) if duration > 0 else None
        if slot:
            start, end = slot
            items.append({"title": "Lernen: " + get_exam_title(exam), "start": start, "end": end, "type": "study", "color": get_exam_color(exam)})
            busy.append(slot)
    for index, task in enumerate(tasks):
        duration = task_plans.get(index, {}).get(day, 0)
        slot = find_free_slot(day, busy, duration) if duration > 0 else None
        if slot:
            start, end = slot
            items.append({
                "title": get_task_title(task), "start": start, "end": end,
                "type": "task", "task_index": index,
                "done": bool(task.get("done", False)), "color": get_task_color(task),
            })
            busy.append(slot)
    items.sort(key=lambda item: (item["start"] is None, item["start"] or datetime.max))
    return items


def format_time_range(item: dict) -> str:
    start, end = item.get("start"), item.get("end")
    return f"{start.strftime('%H:%M')} – {end.strftime('%H:%M')}" if start and end else ""


def show_save_messages() -> None:
    success = st.session_state.pop("save_success", None)
    error = st.session_state.pop("save_error", None)
    if success:
        st.success(success)
    if error:
        st.error("GitHub-Speicherung fehlgeschlagen.")
        st.code(error)


def render_overview(data, exams, tasks, chores, study_plans, task_plans) -> None:
    today = date.today()
    show_save_messages()
    render_section_title("Heute")
    today_items = get_day_items(today, exams, tasks, chores, study_plans, task_plans)
    if not today_items:
        st.info("Für heute ist nichts geplant.")
    for index, item in enumerate(today_items):
        col1, col2 = st.columns([0.05, 0.95])
        task = tasks[item["task_index"]] if item.get("type") == "task" else None
        with col1:
            if task is not None:
                checked = render_task_checkbox(task, "overview_today")
            else:
                checked = render_daily_checkbox(data, item, today, "overview")
        with col2:
            render_item_card(item["title"], format_time_range(item), item.get("color"), done=checked)
    render_section_title("Prüfungen")
    if not exams:
        st.info("Keine kommenden Prüfungen.")
    for exam in exams:
        render_item_card(get_exam_title(exam), format_date(parse_date(exam.get("date"))), get_exam_color(exam))
    render_section_title("Aufträge")
    if not tasks:
        st.info("Keine offenen Aufträge.")
    for task in tasks:
        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            checked = render_task_checkbox(task, "overview_list")
        with col2:
            render_item_card(get_task_title(task), f"Fällig: {format_date(parse_date(task.get('due')))}", get_task_color(task), done=checked)
    render_section_title("Ämtli")
    active_chores = [chore for chore in chores if is_chore_active(chore, today)]
    if not active_chores:
        st.info("Heute keine Ämtli.")
    for chore in active_chores:
        render_item_card(chore.get("title", "Ämtli"), color=COLOR_CHORE)


def render_week(data, exams, tasks, chores, study_plans, task_plans) -> None:
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
    columns = st.columns(7)
    for index in range(7):
        current_date = monday + timedelta(days=index)
        with columns[index]:
            st.markdown(f"**{WEEKDAYS[index]}**  \n`{format_short_date(current_date)}`")
            items = get_day_items(current_date, exams, tasks, chores, study_plans, task_plans)
            due_tasks = [task for task in tasks if parse_date(task.get("due")) == current_date]
            if not items and not due_tasks:
                st.caption("—")
            for item in items:
                if item.get("type") == "task":
                    done = bool(item.get("done", False))
                elif current_date == today:
                    done = get_daily_completion(data, get_daily_item_identifier(item, current_date))
                else:
                    done = False
                render_item_card(item["title"], format_time_range(item), item.get("color"), done=done)
            if due_tasks:
                st.caption("Fällig")
            for task in due_tasks:
                render_item_card(f"📌 {get_task_title(task)}", "Auftrag fällig", get_task_color(task), done=bool(task.get("done", False)))


def render_selected_day(data, selected_date, exams, tasks, chores, study_plans, task_plans) -> None:
    render_section_title(f"{WEEKDAYS[selected_date.weekday()]}, {format_date(selected_date)}")
    items = get_day_items(selected_date, exams, tasks, chores, study_plans, task_plans)
    due_tasks = [task for task in tasks if parse_date(task.get("due")) == selected_date]
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
                checked = render_task_checkbox(task, f"month_plan_{iso(selected_date)}")
                if parse_date(task.get("due")) == selected_date:
                    shown_due_task_ids.add(get_task_identifier(task))
            elif item.get("type") == "chore" and selected_date != date.today():
                checked = get_daily_completion(data, get_daily_item_identifier(item, selected_date))
                st.checkbox(
                    "", value=checked,
                    key=f"month_readonly_{iso(selected_date)}_{index}",
                    disabled=True,
                    help="Ämtli können nur am heutigen Tag abgehakt werden.",
                )
            else:
                checked = render_daily_checkbox(data, item, selected_date, "month")
        with col2:
            render_item_card(item["title"], format_time_range(item), item.get("color"), done=checked)
    remaining_due_tasks = [task for task in due_tasks if get_task_identifier(task) not in shown_due_task_ids]
    if remaining_due_tasks:
        st.caption("An diesem Tag fällig")
    for task in remaining_due_tasks:
        col1, col2 = st.columns([0.05, 0.95])
        with col1:
            checked = render_task_checkbox(task, f"month_due_{iso(selected_date)}")
        with col2:
            render_item_card(f"📌 {get_task_title(task)}", "Auftrag fällig", get_task_color(task), done=checked)


def render_month(data, exams, tasks, chores, study_plans, task_plans) -> None:
    st.session_state.setdefault("month_offset", 0)
    st.session_state.setdefault("selected_calendar_date", iso(date.today()))
    today = date.today()
    month_index = today.year * 12 + today.month - 1 + st.session_state.month_offset
    year = month_index // 12
    month = month_index % 12 + 1
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("← Vorheriger Monat", key="previous_month"):
            st.session_state.month_offset -= 1
            st.rerun()
    with col2:
        render_centered_heading(f"{MONTH_NAMES[month - 1]} {year}", size="1.35rem")
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
                f"<div style='text-align:center;color:#5B6472;font-family:monospace;font-weight:600'>{weekday}</div>",
                unsafe_allow_html=True,
            )
    weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
    for week_index, week in enumerate(weeks):
        day_columns = st.columns(7)
        for day_index, current_date in enumerate(week):
            with day_columns[day_index]:
                outside = current_date.month != month
                selected = st.session_state.selected_calendar_date == iso(current_date)
                exam_count = sum(1 for exam in exams if exam.get("date") == iso(current_date))
                task_count = sum(1 for task in tasks if task.get("due") == iso(current_date))
                chore_count = sum(1 for chore in chores if is_chore_active(chore, current_date))
                indicators = ("🔴" if exam_count else "") + ("🟡" if task_count else "") + ("🟢" if chore_count else "")
                label = str(current_date.day) + (f"\n{indicators}" if indicators else "")
                if st.button(
                    label,
                    key=f"calendar_day_{iso(current_date)}_{week_index}_{day_index}",
                    use_container_width=True,
                    type="primary" if selected else "secondary",
                    disabled=outside,
                ):
                    st.session_state.selected_calendar_date = iso(current_date)
                    st.rerun()
    selected_date = parse_date(st.session_state.selected_calendar_date) or today
    if selected_date.year == year and selected_date.month == month:
        render_selected_day(data, selected_date, exams, tasks, chores, study_plans, task_plans)
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
