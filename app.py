import calendar
import json
from datetime import date, datetime, timedelta

import requests
import streamlit as st


# ============================================================
# Semesterplaner – Streamlit
# Datenquelle: private GitHub-Repository
#
# .streamlit/secrets.toml:
# GITHUB_TOKEN = "ghp_..."
# GITHUB_REPO = "owner/repository"
# GITHUB_FILE = "daten.json"
# GITHUB_BRANCH = "main"
# ============================================================

st.set_page_config(
    page_title="Semesterplaner",
    page_icon="🗓️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------------------- Styling -----------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Libre+Baskerville:wght@700&family=Source+Sans+3:wght@400;600;700&display=swap');

    :root {
        --bg: #EEF1EC;
        --ink: #1C2430;
        --muted: #5B6472;
        --border: #DADFD6;
        --white: #FFFFFF;
        --red: #A6433D;
        --red-bg: #F3DEDB;
        --gold: #B8813A;
        --gold-bg: #F1E3C9;
        --teal: #2E6B60;
        --teal-bg: #DCEAE6;
    }

    .stApp {
        background: var(--bg);
        color: var(--ink);
    }

    .block-container {
        max-width: 1100px;
        padding-top: 1.3rem;
        padding-bottom: 3rem;
    }

    h1, h2, h3 {
        font-family: "Libre Baskerville", Georgia, serif !important;
        color: var(--ink) !important;
    }

    h1 {
        font-size: 2.35rem !important;
        margin-bottom: .1rem !important;
    }

    h2 {
        font-size: 1.55rem !important;
        margin-top: 1.7rem !important;
    }

    .subtitle, .mono {
        font-family: "DM Mono", Consolas, monospace;
        color: var(--muted);
    }

    .subtitle {
        font-size: .82rem;
        margin-bottom: 1rem;
    }

    /* Streamlit buttons */
    div.stButton > button {
        border: 1px solid var(--border);
        border-radius: 999px;
        background: var(--white);
        color: var(--ink);
        min-height: 2.35rem;
        padding: .25rem 1rem;
        font-family: "DM Mono", Consolas, monospace;
    }

    div.stButton > button:hover {
        border-color: #BFC7BC;
        color: var(--ink);
    }

    /* Tabs */
    button[data-baseweb="tab"] {
        font-family: "Source Sans 3", sans-serif !important;
        font-size: 1rem !important;
        color: var(--muted) !important;
        padding: .7rem 1rem !important;
    }

    button[data-baseweb="tab"][aria-selected="true"] {
        color: white !important;
        background: var(--ink) !important;
        border-radius: 10px !important;
    }

    [data-baseweb="tab-list"] {
        gap: 0 !important;
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 5px;
        background: rgba(255,255,255,.35);
    }

    /* Cards */
    .card {
        background: var(--white);
        border: 1px solid var(--border);
        border-radius: 15px;
        margin: .45rem 0;
        padding: .85rem 1rem;
    }

    .card-red { border-left: 5px solid var(--red); }
    .card-gold { border-left: 5px solid var(--gold); }
    .card-teal { border-left: 5px solid var(--teal); }

    .card-title {
        font-family: "Source Sans 3", sans-serif;
        font-weight: 700;
        font-size: 1.08rem;
        color: var(--ink);
    }

    .card-meta {
        font-family: "DM Mono", Consolas, monospace;
        color: var(--muted);
        font-size: .84rem;
        margin-top: .12rem;
    }

    .badge {
        display: inline-block;
        border-radius: 999px;
        padding: .25rem .65rem;
        font-family: "DM Mono", Consolas, monospace;
        font-size: .78rem;
        white-space: nowrap;
    }

    .badge-red { background: var(--red-bg); color: var(--red); }
    .badge-gold { background: var(--gold-bg); color: var(--gold); }
    .badge-teal { background: var(--teal-bg); color: var(--teal); }

    .today-row {
        display: flex;
        align-items: center;
        gap: .65rem;
        border-bottom: 1px solid #E1E4E0;
        padding: .58rem .2rem;
    }

    .today-label {
        flex: 1;
        font-family: "Source Sans 3", sans-serif;
        font-size: 1rem;
    }

    .today-time {
        font-family: "DM Mono", Consolas, monospace;
        font-size: .82rem;
        color: var(--ink);
        white-space: nowrap;
    }

    .color-study { color: var(--gold); }
    .color-chore { color: var(--teal); }
    .color-free { color: var(--muted); font-style: italic; }
    .color-task { color: var(--gold); }

    .calendar-cell {
        min-height: 115px;
        background: var(--white);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: .45rem;
        margin: .15rem;
    }

    .calendar-cell.today {
        background: var(--gold-bg);
        border-color: var(--gold);
    }

    .calendar-cell.outside {
        opacity: .42;
    }

    .day-number {
        font-family: "Libre Baskerville", Georgia, serif;
        font-size: .95rem;
    }

    .dots {
        margin-top: 2.7rem;
        display: flex;
        gap: 5px;
    }

    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
    }

    .dot-red { background: var(--red); }
    .dot-gold { background: var(--gold); }
    .dot-teal { background: var(--teal); }

    .section-gap {
        height: .25rem;
    }

    .error-box {
        background: var(--red-bg);
        border: 1px solid #E6C2BE;
        color: var(--red);
        padding: .8rem 1rem;
        border-radius: 12px;
    }

    /* Streamlit-Oberflächen ausblenden */
    [data-testid="stHeader"] {
        display: none;
    }

    [data-testid="stToolbar"] {
        display: none;
    }

    footer {
        display: none;
    }

    #MainMenu {
        display: none;
    }

    /* App beginnt ganz oben */
    .block-container {
        padding-top: 1.2rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------- Data -----------------------------

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]

SUBJECT_DIFFICULTY = {
    "geschichte": 1,
    "biologie": 2,
    "geografie": 3,
    "englisch": 4,
}

GAP_MINUTES = 10


def iso(d):
    return d.strftime("%Y-%m-%d")


def parse_iso(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def format_day(s):
    d = parse_iso(s)
    return f"{WEEKDAYS[d.weekday()]}, {d.day:02d}.{d.month:02d}."


def format_day_long(s):
    d = parse_iso(s)
    return f"{WEEKDAYS[d.weekday()]}, {d.day:02d}. {MONTHS[d.month - 1]} {d.year}"


def days_until(s):
    return (parse_iso(s) - date.today()).days


def time_to_minutes(t):
    h, m = map(int, t.split(":"))
    return h * 60 + m


def minutes_to_time(n):
    return f"{int(n // 60):02d}:{int(n % 60):02d}"


def add_minutes(t, mins):
    return minutes_to_time(time_to_minutes(t) + int(mins))


def urgency(days):
    if days <= 3:
        return "red"
    if days <= 7:
        return "gold"
    return "teal"


def get_work_hours(iso_date):
    d = parse_iso(iso_date)
    if d.weekday() in (0, 1):
        return [("13:00", "20:00")]
    if d.weekday() == 2:
        return [("13:00", "14:00"), ("18:00", "20:00")]
    if d.weekday() == 3:
        return [("16:30", "20:00")]
    if d.weekday() == 4:
        return [("17:00", "20:00")]
    if d.weekday() == 5:
        return [("08:00", "20:00")]
    return []


def halfway_point(windows):
    if not windows:
        return None
    total = sum(time_to_minutes(e) - time_to_minutes(s) for s, e in windows)
    remaining = total / 2
    for s, e in windows:
        duration = time_to_minutes(e) - time_to_minutes(s)
        if remaining <= duration:
            return time_to_minutes(s) + remaining
        remaining -= duration
    return time_to_minutes(windows[-1][1])


def get_session_dates(exam_date):
    exam = parse_iso(exam_date)
    result = []
    offset = 1
    while len(result) < 10 and offset < 60:
        d = exam - timedelta(days=offset)
        if d.weekday() != 6:
            result.append(iso(d))
        offset += 1
    result.reverse()
    return result


def get_base_per_day(hours, day_count):
    total = round(float(hours) * 60)
    if not total:
        return 0
    divisor = max(day_count - 1, 1)
    return min(round(total / divisor), 45)


def get_study_plan(exam):
    if not exam.get("date") or not exam.get("hours"):
        return []
    dates = get_session_dates(exam["date"])
    base = get_base_per_day(exam["hours"], len(dates))
    if not base:
        return []

    completed = exam.get("completed", [])
    today_iso = iso(date.today())
    past = [d for d in dates if d < today_iso]
    future = [d for d in dates if d >= today_iso]

    missed = sum(1 for d in past if d not in completed) * base
    extra = round(missed / len(future)) if future else 0

    result = []
    for d in dates:
        is_past = d < today_iso
        result.append({
            "date": d,
            "minutes": base if is_past else min(base + extra, 45),
            "isPast": is_past,
            "isToday": d == today_iso,
            "done": d in completed,
        })
    return result


def get_task_session_dates(task):
    due = parse_iso(task["due"])
    result = []
    offset = 1
    # gleiche Grundidee wie die Desktop-Version: bis zu 10 Werktage vor Abgabe
    while len(result) < 10 and offset < 60:
        d = due - timedelta(days=offset)
        if d.weekday() != 6:
            result.append(iso(d))
        offset += 1
    result.reverse()
    return result


def get_task_plan(task):
    total = round(float(task.get("hours", 0) or 0) * 60)
    if not total or not task.get("due"):
        return {"entries": [], "basePerDay": 0}

    dates = get_task_session_dates(task)
    if not dates:
        return {"entries": [], "basePerDay": 0}

    base = min(round(total / len(dates)), 45)
    if not base:
        return {"entries": [], "basePerDay": 0}

    completed = task.get("completed", [])
    today_iso = iso(date.today())
    past = [d for d in dates if d < today_iso]
    future = [d for d in dates if d >= today_iso]

    missed = sum(1 for d in past if d not in completed) * base
    extra = round(missed / len(future)) if future else 0

    entries = []
    for d in dates:
        entries.append({
            "date": d,
            "minutes": base if d < today_iso else min(base + extra, 45),
            "isPast": d < today_iso,
            "isToday": d == today_iso,
            "done": d in completed,
        })
    return {"entries": entries, "basePerDay": base}


def is_chore_active_on_date(chore, iso_date):
    if chore.get("frequency") == "einmalig":
        return chore.get("date") == iso_date

    d = parse_iso(iso_date)
    if d.weekday() == 6:
        return False

    start = chore.get("startDate")
    if not start or iso_date < start:
        return False

    interval = max(1, int(chore.get("interval", 1) or 1))
    count = 0
    cursor = parse_iso(start)

    while iso(cursor) < iso_date:
        if cursor.weekday() != 6:
            count += 1
        cursor += timedelta(days=1)

    return count % interval == 0


def get_day_items(iso_date, exams, tasks, chores):
    d = parse_iso(iso_date)
    is_sunday = d.weekday() == 6
    chore_items = []

    for c in chores:
        if is_chore_active_on_date(c, iso_date):
            minutes = int(c.get("duration", 30) or 30)
            chore_items.append({
                "type": "chore",
                "id": c["id"],
                "label": c["title"],
                "start": c["time"],
                "end": add_minutes(c["time"], minutes),
                "minutes": minutes,
                "done": iso_date in c.get("completed", []),
                "date": iso_date,
            })

    if is_sunday:
        return sorted(chore_items, key=lambda x: x["start"])

    work_windows = get_work_hours(iso_date)

    free_item = None
    if d.weekday() != 3 and work_windows:
        half = halfway_point(work_windows)
        if half is not None:
            start = minutes_to_time(round(half / 5) * 5)
            free_item = {
                "type": "freizeit",
                "id": f"freizeit-{iso_date}",
                "label": "Freizeit",
                "start": start,
                "end": add_minutes(start, 90),
                "minutes": 90,
                "date": iso_date,
            }

    obstacles = list(chore_items)
    if free_item:
        obstacles.append(free_item)

    def free_slots(blocked, day_end="23:00"):
        slots = [
            {"start": time_to_minutes(s), "end": time_to_minutes(e)}
            for s, e in work_windows
        ]

        last_end = time_to_minutes(work_windows[-1][1]) if work_windows else time_to_minutes("13:00")
        day_end_min = time_to_minutes(day_end)
        if day_end_min > last_end:
            slots.append({"start": last_end, "end": day_end_min})

        for o in blocked:
            occ_start = time_to_minutes(o["start"]) - GAP_MINUTES
            occ_end = time_to_minutes(o["end"]) + GAP_MINUTES
            new_slots = []

            for slot in slots:
                if occ_end <= slot["start"] or occ_start >= slot["end"]:
                    new_slots.append(slot)
                    continue
                if occ_start > slot["start"]:
                    new_slots.append({"start": slot["start"], "end": occ_start})
                if occ_end < slot["end"]:
                    new_slots.append({"start": occ_end, "end": slot["end"]})
            slots = new_slots

        return sorted([s for s in slots if s["end"] > s["start"]], key=lambda x: x["start"])

    def place_first_fit(slots, minutes):
        for i, slot in enumerate(slots):
            if slot["end"] - slot["start"] >= minutes:
                start = slot["start"]
                end = start + minutes
                slots[i]["start"] = end
                if slots[i]["start"] >= slots[i]["end"]:
                    slots.pop(i)
                return {"start": minutes_to_time(start), "end": minutes_to_time(end)}
        return None

    # Lernzeiten zuerst
    study_slots = free_slots(obstacles)
    study_candidates = []

    for ex in exams:
        for entry in get_study_plan(ex):
            if entry["date"] == iso_date and entry["minutes"] > 0:
                study_candidates.append({
                    "type": "study",
                    "id": ex["id"],
                    "label": ex["subject"],
                    "minutes": entry["minutes"],
                    "done": entry["done"],
                    "date": iso_date,
                })

    study_candidates.sort(key=lambda x: SUBJECT_DIFFICULTY.get(
        x["label"].split(":")[0].strip().lower(), 99
    ))

    for item in study_candidates:
        pos = place_first_fit(study_slots, item["minutes"])
        if pos:
            item.update(pos)

    # Aufträge danach
    task_candidates = []
    for task in tasks:
        for entry in get_task_plan(task)["entries"]:
            if entry["date"] == iso_date and entry["minutes"] > 0:
                task_candidates.append({
                    "type": "task",
                    "id": task["id"],
                    "label": task["title"],
                    "minutes": entry["minutes"],
                    "done": entry["done"],
                    "date": iso_date,
                    "guaranteed": bool(task.get("guaranteed", False)),
                })

    for item in task_candidates:
        pos = place_first_fit(study_slots, item["minutes"])
        if pos:
            item.update(pos)

    result = chore_items + study_candidates + task_candidates
    if free_item:
        result.append(free_item)

    return sorted(
        [x for x in result if x.get("start")],
        key=lambda x: time_to_minutes(x["start"])
    )


@st.cache_data(ttl=60)
def load_github_json():
    token = st.secrets["GITHUB_TOKEN"]
    repo = st.secrets["GITHUB_REPO"]
    path = st.secrets.get("GITHUB_FILE", "daten.json")
    branch = st.secrets.get("GITHUB_BRANCH", "main")

    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    response = requests.get(
        url,
        headers=headers,
        params={"ref": branch},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def prepare_data(data):
    today_iso = iso(date.today())

    exams = [
        e for e in data.get("exams", [])
        if e.get("date", "") >= today_iso
    ]
    tasks = [
        t for t in data.get("tasks", [])
        if t.get("due", "") >= today_iso
    ]
    chores = [
        c for c in data.get("chores", [])
        if c.get("frequency") != "einmalig"
        or (c.get("date") and c.get("date") >= today_iso)
    ]

    return exams, tasks, chores


# ----------------------------- UI helpers -----------------------------

def badge_text(days):
    if days == 0:
        return "heute"
    if days == 1:
        return "morgen"
    return f"in {days} Tagen"


def card_class(level):
    return f"card-{level}"


def badge_class(level):
    return f"badge-{level}"


def render_exam_card(ex):
    d = days_until(ex["date"])
    level = urgency(d)
    st.markdown(
        f"""
        <div class="card {card_class(level)}">
            <div style="display:flex;justify-content:space-between;gap:1rem;align-items:center;">
                <div>
                    <div class="card-title">{ex["subject"]}</div>
                    <div class="card-meta">{format_day(ex["date"])} · {ex["hours"]} h Lernzeit</div>
                </div>
                <span class="badge {badge_class(level)}">{badge_text(d)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_task_card(task):
    d = days_until(task["due"])
    plan = get_task_plan(task)
    fully_done = len(task.get("completed", [])) > 0 and not plan["entries"]
    level = "teal" if fully_done else urgency(min(d, 5))
    badge = "✓ erledigt" if fully_done else badge_text(d)

    st.markdown(
        f"""
        <div class="card {card_class(level)}">
            <div style="display:flex;justify-content:space-between;gap:1rem;align-items:center;">
                <div>
                    <div class="card-title">{task["title"]}</div>
                    <div class="card-meta">{format_day(task["due"])}, {task.get("time","23:59")} · {task["hours"]} h Aufwand</div>
                </div>
                <span class="badge {badge_class(level)}">{badge}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_today_item(item, index):
    typ = item["type"]
    if typ == "study":
        label = item["label"]
        cls = "color-study"
    elif typ == "chore":
        label = f"Aufgabe: {item['label']}"
        cls = "color-chore"
    elif typ == "freizeit":
        label = "Freizeit"
        cls = "color-free"
    else:
        label = f"Auftrag: {item['label']}"
        if not item.get("guaranteed"):
            label += " (freiwillig)"
        cls = "color-task"

    done = item.get("done", False)
    can_check = typ in ("study", "chore") or (typ == "task" and item.get("guaranteed"))

    cols = st.columns([0.04, 0.72, 0.24])
    with cols[0]:
        if can_check:
            st.checkbox("", value=done, key=f"today_{item['id']}_{item['date']}", label_visibility="collapsed")
    with cols[1]:
        st.markdown(f'<div class="today-label {cls}">{label}</div>', unsafe_allow_html=True)
    with cols[2]:
        st.markdown(
            f'<div class="today-time">{item["start"]}–{item["end"]} · {item["minutes"]} Min</div>',
            unsafe_allow_html=True,
        )


# ----------------------------- Header -----------------------------

try:
    data = load_github_json()
    exams, tasks, chores = prepare_data(data)
except KeyError as exc:
    st.markdown(
        '<div class="error-box">Secret fehlt: '
        f'<code>{exc.args[0]}</code></div>',
        unsafe_allow_html=True,
    )
    st.stop()
except requests.HTTPError as exc:
    st.markdown(
        f'<div class="error-box">GitHub konnte die daten.json nicht laden: '
        f'{exc.response.status_code} {exc.response.reason}</div>',
        unsafe_allow_html=True,
    )
    st.stop()
except Exception as exc:
    st.markdown(
        f'<div class="error-box">Fehler beim Laden der Daten: {exc}</div>',
        unsafe_allow_html=True,
    )
    st.stop()

st.title("Semesterplaner")
st.markdown(
    f'<div class="subtitle">{len(exams)} Prüfungen&nbsp;&nbsp;·&nbsp;&nbsp;'
    f'{len(tasks)} Aufträge&nbsp;&nbsp;·&nbsp;&nbsp;{len(chores)} Aufgaben</div>',
    unsafe_allow_html=True,
)

if st.button("↻ Daten neu laden"):
    load_github_json.clear()
    st.rerun()

tab_overview, tab_week, tab_month = st.tabs(["Übersicht", "Woche", "Monat"])


# ============================= Übersicht =============================

with tab_overview:
    st.subheader("Heute")

    today_iso = iso(date.today())
    items = get_day_items(today_iso, exams, tasks, chores)

    left, right = st.columns([1, 1])
    with left:
        hide_times = st.toggle("Zeiten ausblenden", value=False)
    with right:
        hide_voluntary = st.toggle("Freiwillige Aufträge ausblenden", value=False)

    filtered = [
        x for x in items
        if not (
            hide_voluntary
            and x["type"] == "task"
            and not x.get("guaranteed")
        )
    ]

    if not filtered:
        st.markdown('<div class="card"><span class="mono">Keine Einträge für heute.</span></div>', unsafe_allow_html=True)
    else:
        for i, item in enumerate(filtered):
            if hide_times:
                # gleicher Aufbau, nur die rechte Zeitangabe fehlt
                typ = item["type"]
                if typ == "study":
                    label = item["label"]
                    cls = "color-study"
                elif typ == "chore":
                    label = f"Aufgabe: {item['label']}"
                    cls = "color-chore"
                elif typ == "freizeit":
                    label = "Freizeit"
                    cls = "color-free"
                else:
                    label = f"Auftrag: {item['label']}"
                    cls = "color-task"
                st.markdown(f'<div class="today-row"><div class="today-label {cls}">{label}</div></div>', unsafe_allow_html=True)
            else:
                render_today_item(item, i)

    st.subheader("Alle Prüfungen")
    show_all_exams = st.button(
        "← Nächste 7 Prüfungen anzeigen" if len(exams) > 7 else "Alle Prüfungen",
        key="show_exams",
    )
    visible_exams = sorted(exams, key=lambda x: x["date"])
    if not show_all_exams:
        visible_exams = visible_exams[:7]

    for ex in visible_exams:
        render_exam_card(ex)

    st.subheader("Aufträge")
    c1, c2 = st.columns([0.34, 0.66])
    with c1:
        current_only = st.toggle("Nur aktuelle Aufträge anzeigen", value=True)
    with c2:
        subject_filter = st.text_input("Fach eingeben ...", label_visibility="collapsed", placeholder="Fach eingeben ...")

    visible_tasks = sorted(tasks, key=lambda x: x["due"] + x.get("time", "23:59"))

    if current_only:
        current = []
        for task in visible_tasks:
            entries = get_task_plan(task)["entries"]
            if entries and entries[0]["date"] <= today_iso:
                current.append(task)
        visible_tasks = current

    if subject_filter.strip():
        q = subject_filter.strip().lower()
        visible_tasks = [
            t for t in visible_tasks
            if q in t.get("title", "").lower()
            or q in t.get("subject", "").lower()
        ]

    for task in visible_tasks:
        render_task_card(task)

    st.subheader("Aufgaben")
    for chore in chores:
        freq = (
            f"alle {chore.get('interval', 1)} Tage (ausser So)"
            if chore.get("frequency") != "einmalig"
            else "einmalig"
        )
        st.markdown(
            f"""
            <div style="padding:.7rem .25rem;border-bottom:1px solid #DADFD6;">
                <div style="display:flex;justify-content:space-between;">
                    <div>
                        <div style="font-family:'Source Sans 3';font-size:1rem;">{chore["title"]}</div>
                        <div class="card-meta">{freq} · {chore["time"]} · {chore.get("duration",30)} Min</div>
                    </div>
                    <div class="mono">Bearbeiten&nbsp;&nbsp;×</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# =============================== Woche ===============================

with tab_week:
    if "week_offset" not in st.session_state:
        st.session_state.week_offset = 0

    c1, c2, c3 = st.columns([1, 5, 1])
    with c1:
        if st.button("‹", key="week_prev"):
            st.session_state.week_offset -= 1
            st.rerun()
    with c3:
        if st.button("›", key="week_next"):
            st.session_state.week_offset += 1
            st.rerun()

    monday = date.today() - timedelta(days=date.today().weekday())
    monday += timedelta(weeks=st.session_state.week_offset)
    week_dates = [monday + timedelta(days=i) for i in range(7)]

    with c2:
        st.markdown(
            f"<h3 style='text-align:center;margin-top:.2rem;'>"
            f"{week_dates[0].day:02d}. {MONTHS[week_dates[0].month-1]} – "
            f"{week_dates[-1].day:02d}. {MONTHS[week_dates[-1].month-1]} "
            f"{week_dates[-1].year}</h3>",
            unsafe_allow_html=True,
        )

    for d in week_dates:
        s = iso(d)
        row_bg = "#F1E3C9" if d == date.today() else "#FFFFFF"
        st.markdown(
            f"""
            <div class="card" style="background:{row_bg};">
                <div style="display:flex;gap:1rem;">
                    <div style="min-width:82px;">
                        <div class="mono">{WEEKDAYS[d.weekday()]}</div>
                        <div style="font-family:'Libre Baskerville';font-weight:700;font-size:1.1rem;">
                            {d.day}.{d.month}.
                        </div>
                    </div>
                    <div style="flex:1;">
            """,
            unsafe_allow_html=True,
        )

        day_exams = [e for e in exams if e.get("date") == s]
        day_tasks = [t for t in tasks if t.get("due") == s]
        day_items = get_day_items(s, exams, tasks, chores)

        for ex in day_exams:
            st.markdown(
                f'<div class="color-study"><b>Prüfung: {ex["subject"]}</b></div>',
                unsafe_allow_html=True,
            )
        for task in day_tasks:
            st.markdown(
                f'<div class="color-chore"><b>Abgabe: {task["title"]} ({task.get("time","23:59")})</b></div>',
                unsafe_allow_html=True,
            )
        for item in day_items:
            if item["type"] == "study":
                label = f"Lernzeit {item['label']}"
                cls = "color-study"
            elif item["type"] == "chore":
                label = f"Aufgabe „{item['label']}“"
                cls = "color-chore"
            elif item["type"] == "freizeit":
                label = "Freizeit"
                cls = "color-free"
            else:
                suffix = "" if item.get("guaranteed") else " (freiwillig)"
                label = f"Auftrag „{item['label']}“{suffix}"
                cls = "color-task"

            st.markdown(
                f'<div class="{cls} mono" style="margin:.1rem 0;">'
                f'{label}: {item["start"]}–{item["end"]}</div>',
                unsafe_allow_html=True,
            )

        if not day_exams and not day_tasks and not day_items:
            st.markdown('<span class="mono" style="color:#B0B5B0;">–</span>', unsafe_allow_html=True)

        st.markdown("</div></div></div>", unsafe_allow_html=True)


# =============================== Monat ===============================

with tab_month:
    if "month_offset" not in st.session_state:
        st.session_state.month_offset = 0
    if "selected_day" not in st.session_state:
        st.session_state.selected_day = iso(date.today())

    c1, c2, c3 = st.columns([1, 5, 1])
    with c1:
        if st.button("‹", key="month_prev"):
            st.session_state.month_offset -= 1
            st.rerun()
    with c3:
        if st.button("›", key="month_next"):
            st.session_state.month_offset += 1
            st.rerun()

    base = date(date.today().year, date.today().month, 1)
    raw_month = base.month - 1 + st.session_state.month_offset
    year = base.year + raw_month // 12
    month = raw_month % 12 + 1
    month_first = date(year, month, 1)

    with c2:
        st.markdown(
            f"<h3 style='text-align:center;margin-top:.2rem;'>"
            f"{MONTHS[month-1]} {year}</h3>",
            unsafe_allow_html=True,
        )

    if st.session_state.month_offset != 0:
        if st.button("Heute", key="month_today"):
            st.session_state.month_offset = 0
            st.rerun()

    # Kalender: CSS Grid statt Streamlit columns, damit es optisch nahe am Screenshot bleibt.
    cal = calendar.Calendar(firstweekday=0)
    weeks = cal.monthdatescalendar(year, month)

    header = "".join(
        f'<div style="text-align:center;font-family:DM Mono;color:#5B6472;">{w}</div>'
        for w in WEEKDAYS
    )

    cells = []
    for d in [d for week in weeks for d in week]:
        s = iso(d)
        outside = d.month != month
        today_cls = " today" if d == date.today() else ""
        outside_cls = " outside" if outside else ""

        dots = []
        if any(e.get("date") == s for e in exams):
            dots.append('<span class="dot dot-red"></span>')
        if any(t.get("due") == s for t in tasks):
            dots.append('<span class="dot dot-gold"></span>')
        if any(
            is_chore_active_on_date(c, s) or
            any(x["date"] == s for x in get_day_items(s, exams, tasks, chores))
            for c in chores
        ):
            dots.append('<span class="dot dot-teal"></span>')

        cells.append(
            f"""
            <div class="calendar-cell{today_cls}{outside_cls}">
                <div class="day-number">{d.day}</div>
                <div class="dots">{''.join(dots)}</div>
            </div>
            """
        )

    st.markdown(
        f"""
        <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:2px;">
            {header}
            {''.join(cells)}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)

    selectable_days = [d for week in weeks for d in week if d.month == month]
    selected = st.date_input(
        "Tag auswählen",
        value=parse_iso(st.session_state.selected_day)
        if parse_iso(st.session_state.selected_day).month == month
        else month_first,
        min_value=month_first,
        max_value=date(year, month, calendar.monthrange(year, month)[1]),
        label_visibility="collapsed",
    )
    st.session_state.selected_day = iso(selected)

    s = iso(selected)
    st.markdown(
        f'<div class="card"><h3 style="margin-top:0;">{format_day_long(s)}</h3>',
        unsafe_allow_html=True,
    )

    selected_exams = [e for e in exams if e.get("date") == s]
    selected_tasks = [t for t in tasks if t.get("due") == s]
    selected_items = get_day_items(s, exams, tasks, chores)

    if not selected_exams and not selected_tasks and not selected_items:
        st.markdown('<span class="mono">Keine Einträge an diesem Tag.</span>', unsafe_allow_html=True)

    for ex in selected_exams:
        st.markdown(f'<b style="color:#A6433D;">Prüfung: {ex["subject"]}</b>', unsafe_allow_html=True)
    for task in selected_tasks:
        st.markdown(f'<b style="color:#2E6B60;">Abgabe: {task["title"]} ({task.get("time","23:59")})</b>', unsafe_allow_html=True)

    for item in selected_items:
        typ = item["type"]
        if typ == "study":
            label, cls = f'{item["label"]}', "color-study"
        elif typ == "chore":
            label, cls = f'Aufgabe: {item["label"]}', "color-chore"
        elif typ == "freizeit":
            label, cls = "Freizeit", "color-free"
        else:
            label, cls = f'Auftrag: {item["label"]}', "color-task"

        st.markdown(
            f'<div class="{cls} mono" style="margin-top:.25rem;">'
            f'{label}: {item["start"]}–{item["end"]}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
