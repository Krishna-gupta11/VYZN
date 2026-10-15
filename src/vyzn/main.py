"""
VYZN - a gamified habit tracker (PySide6, runs locally on Windows).

Run:      python vyzn.py
Install:  pip install PySide6 qtawesome        (qtawesome is optional, gives nicer icons)

Optional extras (drop next to this file):
    fonts/*.ttf   -> e.g. Rajdhani or Orbitron from Google Fonts (auto-loaded, used for headings)
    sounds/levelup.wav, sounds/xp.wav  -> played on level-up / XP gain

During development, data is stored in the project-local data/vyzn.db (SQLite).
"""
import sys
import os
import math
import sqlite3
import datetime as dt
import calendar as pycalendar
import shutil
from pathlib import Path

from PySide6.QtCore import (
    Qt, QPoint, QPointF, QRectF, QSize, QTimer, QUrl, Signal, Property,
    QPropertyAnimation, QParallelAnimationGroup, QSequentialAnimationGroup,
    QPauseAnimation, QEasingCurve, QAbstractAnimation,
)
from PySide6.QtCore import QDate
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient, QFont, QFontDatabase,
    QIcon, QPixmap, QPainterPath,
)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QGridLayout, QStackedWidget, QScrollArea,
    QLineEdit, QTextEdit, QButtonGroup, QGraphicsDropShadowEffect,
    QComboBox, QDateEdit, QCheckBox, QDialog, QFormLayout,
    QGraphicsOpacityEffect, QSizeGrip, QToolTip, QSizePolicy, QMessageBox, QInputDialog,
)

try:
    import qtawesome as qta
    HAS_QTA = True
except Exception:  # qtawesome is optional
    qta = None
    HAS_QTA = False

try:
    from PySide6.QtMultimedia import QSoundEffect
    HAS_SOUND = True
except Exception:
    HAS_SOUND = False


# ----------------------------------------------------------------------------
# Config / game design
# ----------------------------------------------------------------------------
PLAYER_NAME = "Krishna"
# Resolve the project root whether this file lives at the project root or in
# the recommended src/vyzn/ package.
_FILE = Path(__file__).resolve()
PROJECT_DIR = next(
    (parent for parent in _FILE.parents if (parent / "src").is_dir()),
    _FILE.parent,
)
# Frozen builds must write user data outside the bundled/read-only application.
if getattr(sys, "frozen", False):
    DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "VYZN"
else:
    DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "vyzn.db"
ASSET_DIR = Path(getattr(sys, "_MEIPASS", _FILE.parent))

# Preserve an existing installation database when switching to project-local
# development storage. Never overwrite an existing project-local database.
_LEGACY_DB = Path(os.environ.get("APPDATA", str(Path.home()))) / "VYZN" / "vyzn.db"
if not DB_PATH.exists() and _LEGACY_DB.exists() and _LEGACY_DB.resolve() != DB_PATH.resolve():
    shutil.copy2(_LEGACY_DB, DB_PATH)

TASK_XP = 15
JOURNAL_XP = 15

PAGES = ["Dashboard", "Habits", "Tasks", "Calendar", "Notes", "Journal", "Analysis", "Progress", "Profile"]

NAV_ITEMS = [
    ("Dashboard", "\u2302", "fa5s.home"),
    ("Habits", "\u25c8", "fa5s.fire"),
    ("Tasks", "\u2713", "fa5s.check-circle"),
    ("Calendar", "\u25a6", "fa5s.calendar-alt"),
    ("Notes", "\u25a4", "fa5s.sticky-note"),
    ("Journal", "\u270e", "fa5s.pen-nib"),
    ("Analysis", "\u25a5", "fa5s.chart-bar"),
    ("Progress", "\u2197", "fa5s.chart-line"),
]

# (min level, form name, series, colour)
RANKS = [
    (1, "BASE FORM", "Dragon Ball", "#9aa0b5"),
    (3, "KAIOKEN", "Dragon Ball", "#ff5a4d"),
    (5, "SUPER SAIYAN", "Dragon Ball", "#ffd633"),
    (8, "SUPER SAIYAN 2", "Dragon Ball", "#ffe44d"),
    (11, "SUPER SAIYAN 3", "Dragon Ball", "#ffb020"),
    (15, "SUPER SAIYAN 4", "Dragon Ball GT", "#ff2e3d"),
    (20, "SUPER SAIYAN GOD", "Dragon Ball Super", "#ff4d6d"),
    (25, "SUPER SAIYAN BLUE", "Dragon Ball Super", "#3fa7ff"),
    (30, "SSJ ROS\u00c9", "Goku Black", "#ff7ab8"),
    (36, "ULTRA INSTINCT SIGN", "Dragon Ball Super", "#9fb8ff"),
    (42, "ULTRA EGO", "Dragon Ball Super", "#b04dff"),
    (46, "GEAR 5 \u00b7 SUN GOD NIKA", "One Piece", "#ffffff"),
    (50, "MASTERED ULTRA INSTINCT", "Dragon Ball Super", "#e8eeff"),
]

# key, title, target, reward xp
QUESTS = [
    ("habits", "Complete 3 habits", 3, 25),
    ("tasks", "Finish 2 tasks", 2, 20),
    ("journal", "Write a journal entry", 1, 15),
]

# key, name, description, glyph, condition(stats)
ACHIEVEMENTS = [
    ("first_step", "FIRST STEP", "Complete your first habit", "\u25b2", lambda s: s["habit_checks"] >= 1),
    ("early_bird", "EARLY BIRD", "Complete a habit before 8 AM", "\u2600", lambda s: s["early"] >= 1),
    ("streak7", "7-DAY STREAK", "Stay active 7 days in a row", "\u26a1", lambda s: s["best_streak"] >= 7),
    ("streak30", "30-DAY STREAK", "Stay active 30 days in a row", "\u265b", lambda s: s["best_streak"] >= 30),
    ("slayer", "TASK SLAYER", "Finish 10 tasks", "\u2694", lambda s: s["tasks_done"] >= 10),
    ("scribe", "SCRIBE", "Write 5 journal entries", "\u270e", lambda s: s["journal"] >= 5),
    ("collector", "COLLECTOR", "Create 5 habits", "\u2756", lambda s: s["habits_created"] >= 5),
    ("going_super", "GOING SUPER", "Reach Super Saiyan (level 5)", "\u2605", lambda s: s["level"] >= 5),
    ("god_level", "GOD LEVEL", "Reach Super Saiyan Blue (level 25)", "\u2604", lambda s: s["level"] >= 25),
    ("power_1000", "POWER LEVEL 1000", "Earn 1,000 total XP", "\u2b22", lambda s: s["total_xp"] >= 1000),
]

QUOTES = [
    "Discipline creates the freedom to become who you envision.",
    "Every rep, every habit, every day. That is how you power up.",
    "Small daily wins stack into legendary power levels.",
    "Your next form is one consistent week away.",
    "Train today like the version of you who already made it.",
    "Do not wish for it. Grind for it. Then level up.",
    "Consistency is the real transformation.",
]

BASE = dict(
    bg="#0b0b10", panel="#14141d", panel2="#101018",
    border="#292936", text="#f5f5fa", muted="#9292a6",
)
ACCENTS = {
    "RED": ("#ff4057", "#ff6476"),
    "BLUE": ("#4388ff", "#70a5ff"),
    "WHITE": ("#f0f0f5", "#ffffff"),
    "PURPLE": ("#a259ff", "#bf85ff"),
    "CYAN": ("#19e3e0", "#6af5f2"),
    "GREEN": ("#39ff88", "#7dffb2"),
}
THEME_ORDER = list(ACCENTS.keys())


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def mix(a, b, t):
    ca, cb = QColor(a), QColor(b)
    r = round(ca.red() + (cb.red() - ca.red()) * t)
    g = round(ca.green() + (cb.green() - ca.green()) * t)
    bl = round(ca.blue() + (cb.blue() - ca.blue()) * t)
    return QColor(r, g, bl).name()


def build_palette(name, head_font):
    acc, hov = ACCENTS[name]
    p = dict(
        accent=acc,
        hover=hov,
        bg=mix(BASE["bg"], acc, 0.035),
        panel=mix(BASE["panel"], acc, 0.03),
        panel2=mix(BASE["panel2"], acc, 0.02),
        border=mix(BASE["border"], acc, 0.08),
        text=BASE["text"],
        muted=BASE["muted"],
        on_accent="#0b0b10",
        head_font='"%s"' % head_font,
    )
    p["panel_hi"] = mix(p["panel"], acc, 0.09)
    p["accent_dim"] = mix(p["panel"], acc, 0.18)
    return p


def add_glow(widget, color, blur=28, alpha=170):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 0)
    c = QColor(color)
    c.setAlpha(alpha)
    effect.setColor(c)
    widget.setGraphicsEffect(effect)


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def make_label(text, obj=None, wrap=False):
    lbl = QLabel(text)
    if obj:
        lbl.setObjectName(obj)
    if wrap:
        lbl.setWordWrap(True)
    return lbl


def today():
    return dt.date.today()


def today_str():
    return today().isoformat()


def xp_to_next(level):
    return 100 + 50 * (level - 1)


def level_info(total_xp):
    level, xp = 1, total_xp
    while xp >= xp_to_next(level):
        xp -= xp_to_next(level)
        level += 1
    return level, xp, xp_to_next(level)


def rank_for_level(level):
    current = RANKS[0]
    for r in RANKS:
        if level >= r[0]:
            current = r
    return current


def next_rank(level):
    for r in RANKS:
        if r[0] > level:
            return r
    return None


def pick_heading_font():
    fonts_dir = ASSET_DIR / "fonts"
    if fonts_dir.is_dir():
        for f in list(fonts_dir.glob("*.ttf")) + list(fonts_dir.glob("*.otf")):
            QFontDatabase.addApplicationFont(str(f))
    families = set(QFontDatabase.families())
    for name in ("Rajdhani", "Orbitron", "Bahnschrift", "Segoe UI Variable Display", "Segoe UI"):
        if name in families:
            return name
    return "Sans Serif"


def make_app_icon():
    icon = QIcon()
    for size in (256, 128, 64, 32, 16):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, size, size)
        grad.setColorAt(0, QColor("#ff6476"))
        grad.setColorAt(1, QColor("#ff2e45"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
        p.setPen(QColor("#0b0b10"))
        font = QFont("Segoe UI", max(6, int(size * 0.5)))
        font.setBold(True)
        p.setFont(font)
        p.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, "V")
        p.end()
        icon.addPixmap(pm)
    return icon


_sounds = {}


def play_sound(name):
    if not HAS_SOUND:
        return
    path = ASSET_DIR / "sounds" / f"{name}.wav"
    if not path.exists():
        return
    if name not in _sounds:
        fx = QSoundEffect()
        fx.setSource(QUrl.fromLocalFile(str(path)))
        fx.setVolume(0.6)
        _sounds[name] = fx
    _sounds[name].play()


# ----------------------------------------------------------------------------
# Data layer (SQLite)
# ----------------------------------------------------------------------------
class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS habits(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                xp INTEGER NOT NULL DEFAULT 20,
                created TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE IF NOT EXISTS habit_log(
                habit_id INTEGER NOT NULL, day TEXT NOT NULL,
                completed_at TEXT,
                PRIMARY KEY(habit_id, day));
            CREATE TABLE IF NOT EXISTS tasks(
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0, created TEXT NOT NULL, done_day TEXT,
                due_date TEXT, priority TEXT NOT NULL DEFAULT 'Medium', description TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS journal(day TEXT PRIMARY KEY, text TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS activity(
                day TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS quests_claimed(
                day TEXT NOT NULL, key TEXT NOT NULL, PRIMARY KEY(day, key));
            CREATE TABLE IF NOT EXISTS achievements(key TEXT PRIMARY KEY, day TEXT);
            CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS important_dates(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_date TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Personal',
                notes TEXT NOT NULL DEFAULT '',
                recurring_yearly INTEGER NOT NULL DEFAULT 0);
            """
        )
        # Safe migrations for databases created by earlier VYZN versions.
        habit_columns = {r[1] for r in self.db.execute("PRAGMA table_info(habits)")}
        if "active" not in habit_columns:
            self.db.execute("ALTER TABLE habits ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
        log_columns = {r[1] for r in self.db.execute("PRAGMA table_info(habit_log)")}
        if "completed_at" not in log_columns:
            self.db.execute("ALTER TABLE habit_log ADD COLUMN completed_at TEXT")
        task_columns = {r[1] for r in self.db.execute("PRAGMA table_info(tasks)")}
        if "due_date" not in task_columns:
            self.db.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
        if "priority" not in task_columns:
            self.db.execute("ALTER TABLE tasks ADD COLUMN priority TEXT NOT NULL DEFAULT 'Medium'")
        if "description" not in task_columns:
            self.db.execute("ALTER TABLE tasks ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        self.db.commit()

    def close(self):
        if self.db:
            self.db.commit()
            self.db.close()

    # Internal helpers intentionally do not commit; callers can group updates
    # in one transaction.
    def _set(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, str(value)))

    def _add_int(self, key, n):
        current = int(self.get(key, "0") or 0)
        self._set(key, max(0, current + n))

    def _add_xp(self, delta):
        self._set("xp", max(0, self.total_xp() + delta))

    # --- meta ---
    def get(self, key, default=""):
        row = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set(self, key, value):
        with self.db:
            self._set(key, value)

    def add_int(self, key, n):
        with self.db:
            self._add_int(key, n)

    # --- xp / level ---
    def total_xp(self):
        return int(self.get("xp", "0") or 0)

    def add_xp(self, delta):
        with self.db:
            self._add_xp(delta)

    def level(self):
        return level_info(self.total_xp())[0]

    # --- activity / streaks ---
    def bump(self, day, delta):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO activity(day, count) VALUES(?, 0)", (day,))
            self.db.execute("UPDATE activity SET count = MAX(0, count + ?) WHERE day=?", (delta, day))

    def active_days(self):
        rows = self.db.execute("SELECT day FROM activity WHERE count > 0").fetchall()
        return {dt.date.fromisoformat(r[0]) for r in rows}

    @staticmethod
    def _streak_from(days):
        d = today()
        if d not in days:
            d -= dt.timedelta(days=1)
        n = 0
        while d in days:
            n += 1
            d -= dt.timedelta(days=1)
        return n

    def current_streak(self):
        return self._streak_from(self.active_days())

    def best_streak(self):
        best = run = 0
        prev = None
        for d in sorted(self.active_days()):
            run = run + 1 if prev and (d - prev).days == 1 else 1
            best = max(best, run)
            prev = d
        return best

    def activity_map(self, since):
        rows = self.db.execute("SELECT day, count FROM activity WHERE day >= ?", (since.isoformat(),)).fetchall()
        return {dt.date.fromisoformat(r[0]): r[1] for r in rows}

    def important_dates_for_month(self, year, month):
        """Return dates in a month, including yearly recurring dates."""
        rows = self.db.execute("SELECT * FROM important_dates ORDER BY event_date, title").fetchall()
        found = []
        for row in rows:
            item = dict(row)
            original = dt.date.fromisoformat(item["event_date"])
            if (original.year == year and original.month == month) or (item["recurring_yearly"] and original.month == month):
                item["display_date"] = dt.date(year, month, min(original.day, pycalendar.monthrange(year, month)[1])).isoformat()
                found.append(item)
        return found

    def important_dates_on(self, day):
        rows = self.db.execute("SELECT * FROM important_dates ORDER BY title").fetchall()
        result = []
        for row in rows:
            item = dict(row)
            original = dt.date.fromisoformat(item["event_date"])
            if original == day or (item["recurring_yearly"] and original.month == day.month and original.day == day.day):
                result.append(item)
        return result

    def add_important_date(self, title, event_date, category="Personal", notes="", recurring_yearly=False):
        with self.db:
            self.db.execute(
                "INSERT INTO important_dates(title, event_date, category, notes, recurring_yearly) VALUES(?,?,?,?,?)",
                (title.strip(), event_date, category, notes.strip(), int(recurring_yearly)),
            )

    def delete_important_date(self, event_id):
        with self.db:
            self.db.execute("DELETE FROM important_dates WHERE id=?", (event_id,))

    def day_details(self, day):
        """Return activity details for a date, used by the calendar inspector."""
        habits = self.db.execute(
            """SELECT h.name, h.xp FROM habit_log l JOIN habits h ON h.id=l.habit_id
               WHERE l.day=? ORDER BY h.name""", (day,)
        ).fetchall()
        tasks = self.db.execute("SELECT title FROM tasks WHERE done=1 AND done_day=? ORDER BY title", (day,)).fetchall()
        due_tasks = self.db.execute("SELECT id, title, priority, done FROM tasks WHERE due_date=? ORDER BY done, CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, title", (day,)).fetchall()
        journal = self.get_journal(day)
        return {"habits": [dict(r) for r in habits], "tasks": [r[0] for r in tasks], "due_tasks": [dict(r) for r in due_tasks], "journal": journal}

    def analysis_summary(self):
        """Compute transparent lifetime and recent-period metrics from stored records."""
        today_date = today()
        start = today_date - dt.timedelta(days=29)
        activity = self.activity_map(start)
        habit_total = self.db.execute("SELECT COUNT(*) FROM habit_log").fetchone()[0]
        task_total = self.db.execute("SELECT COUNT(*) FROM tasks WHERE done=1").fetchone()[0]
        task_created = self.db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
        journal_total = self.db.execute("SELECT COUNT(*) FROM journal WHERE TRIM(text)<>''").fetchone()[0]
        active_habits = self.db.execute("SELECT COUNT(*) FROM habits WHERE active=1").fetchone()[0]
        habit_days = self.db.execute("SELECT COUNT(DISTINCT day) FROM habit_log").fetchone()[0]
        task_days = self.db.execute("SELECT COUNT(DISTINCT done_day) FROM tasks WHERE done=1 AND done_day IS NOT NULL").fetchone()[0]
        journal_days = self.db.execute("SELECT COUNT(*) FROM journal WHERE TRIM(text)<>''").fetchone()[0]
        last7 = [today_date - dt.timedelta(days=i) for i in range(6, -1, -1)]
        last30 = [today_date - dt.timedelta(days=i) for i in range(29, -1, -1)]
        rows = self.db.execute("SELECT day, COUNT(*) FROM habit_log WHERE day>=? GROUP BY day", (start.isoformat(),)).fetchall()
        habit_by_day = {dt.date.fromisoformat(r[0]): r[1] for r in rows}
        rows = self.db.execute("SELECT done_day, COUNT(*) FROM tasks WHERE done=1 AND done_day>=? GROUP BY done_day", (start.isoformat(),)).fetchall()
        tasks_by_day = {dt.date.fromisoformat(r[0]): r[1] for r in rows}
        rows = self.db.execute("SELECT day FROM journal WHERE TRIM(text)<>'' AND day>=?", (start.isoformat(),)).fetchall()
        journal_days_set = {dt.date.fromisoformat(r[0]) for r in rows}
        return {
            "total_xp": self.total_xp(), "current_streak": self.current_streak(),
            "best_streak": self.best_streak(), "habit_completions": habit_total,
            "tasks_completed": task_total, "tasks_created": task_created,
            "journal_entries": journal_total, "active_habits": active_habits,
            "habit_days": habit_days, "task_days": task_days, "journal_days": journal_days,
            "last7_labels": [d.strftime("%a") for d in last7],
            "last7_activity": [int(activity.get(d, 0)) for d in last7],
            "last30_labels": [d.strftime("%d") for d in last30],
            "last30_activity": [int(activity.get(d, 0)) for d in last30],
            "last30_habits": [int(habit_by_day.get(d, 0)) for d in last30],
            "last30_tasks": [int(tasks_by_day.get(d, 0)) for d in last30],
            "last30_journal": [1 if d in journal_days_set else 0 for d in last30],
        }

    # --- habits ---
    def add_habit(self, name, xp):
        with self.db:
            self.db.execute("INSERT INTO habits(name, xp, created, active) VALUES(?, ?, ?, 1)",
                            (name, xp, today_str()))
            self._add_int("habits_created", 1)

    def archive_habit(self, hid):
        with self.db:
            cur = self.db.execute("UPDATE habits SET active=0 WHERE id=? AND active=1", (hid,))
        return cur.rowcount > 0

    def restore_habit(self, hid):
        with self.db:
            cur = self.db.execute("UPDATE habits SET active=1 WHERE id=? AND active=0", (hid,))
        return cur.rowcount > 0

    def archived_habits(self):
        rows = self.db.execute("SELECT id, name, xp, created FROM habits WHERE active=0 ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    # Backward-compatible alias: old callers now archive instead of erasing history.
    def delete_habit(self, hid):
        return self.archive_habit(hid)

    def habit_streak(self, hid):
        rows = self.db.execute("SELECT day FROM habit_log WHERE habit_id=?", (hid,)).fetchall()
        return self._streak_from({dt.date.fromisoformat(r[0]) for r in rows})

    def habits_status(self, day):
        rows = self.db.execute(
            """SELECT h.id, h.name, h.xp,
                      EXISTS(SELECT 1 FROM habit_log l WHERE l.habit_id=h.id AND l.day=?) AS done
               FROM habits h WHERE h.active=1 ORDER BY h.id""", (day,)
        ).fetchall()
        return [dict(id=r["id"], name=r["name"], xp=r["xp"], done=bool(r["done"]),
                     streak=self.habit_streak(r["id"])) for r in rows]

    def toggle_habit(self, hid, day):
        with self.db:
            row = self.db.execute("SELECT xp FROM habits WHERE id=? AND active=1", (hid,)).fetchone()
            if not row:
                return 0
            xp = row["xp"]
            exists = self.db.execute("SELECT 1 FROM habit_log WHERE habit_id=? AND day=?", (hid, day)).fetchone()
            if exists:
                self.db.execute("DELETE FROM habit_log WHERE habit_id=? AND day=?", (hid, day))
                self.db.execute("UPDATE activity SET count=MAX(0, count-1) WHERE day=?", (day,))
                self._add_int("habit_checks", -1)
                self._add_xp(-xp)
                return -xp
            completed_at = dt.datetime.now().isoformat(timespec="seconds")
            self.db.execute("INSERT INTO habit_log(habit_id, day, completed_at) VALUES(?, ?, ?)",
                            (hid, day, completed_at))
            self.db.execute("INSERT OR IGNORE INTO activity(day, count) VALUES(?, 0)", (day,))
            self.db.execute("UPDATE activity SET count=count+1 WHERE day=?", (day,))
            self._add_int("habit_checks", 1)
            if dt.datetime.fromisoformat(completed_at).hour < 8:
                self._set("early", max(int(self.get("early", "0") or 0), 1))
            self._add_xp(xp)
            return xp

    # --- tasks ---
    def add_task(self, title, due_date=None, priority="Medium", description=""):
        with self.db:
            self.db.execute("INSERT INTO tasks(title, created, due_date, priority, description) VALUES(?, ?, ?, ?, ?)",
                            (title, today_str(), due_date, priority, description.strip()))

    def update_task(self, tid, title, due_date, priority, description=""):
        with self.db:
            self.db.execute("UPDATE tasks SET title=?, due_date=?, priority=?, description=? WHERE id=?",
                            (title.strip(), due_date, priority, description.strip(), tid))

    def tasks_due_on(self, day):
        rows = self.db.execute("SELECT id, title, done, priority, due_date FROM tasks WHERE due_date=? ORDER BY done, CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, title", (day,)).fetchall()
        return [dict(r) for r in rows]

    def delete_task(self, tid):
        with self.db:
            self.db.execute("DELETE FROM tasks WHERE id=?", (tid,))

    def visible_tasks(self, day):
        rows = self.db.execute("SELECT * FROM tasks WHERE done=0 OR done_day=? ORDER BY done, id", (day,)).fetchall()
        return [dict(r) for r in rows]

    def task_counts(self, day):
        pending = self.db.execute("SELECT COUNT(*) FROM tasks WHERE done=0").fetchone()[0]
        done_today = self.db.execute("SELECT COUNT(*) FROM tasks WHERE done=1 AND done_day=?", (day,)).fetchone()[0]
        return pending, done_today

    def toggle_task(self, tid, day):
        with self.db:
            row = self.db.execute("SELECT done FROM tasks WHERE id=?", (tid,)).fetchone()
            if not row:
                return 0
            if row["done"]:
                self.db.execute("UPDATE tasks SET done=0, done_day=NULL WHERE id=?", (tid,))
                self.db.execute("UPDATE activity SET count=MAX(0, count-1) WHERE day=?", (day,))
                self._add_int("tasks_done", -1)
                self._add_xp(-TASK_XP)
                return -TASK_XP
            self.db.execute("UPDATE tasks SET done=1, done_day=? WHERE id=?", (day, tid))
            self.db.execute("INSERT OR IGNORE INTO activity(day, count) VALUES(?, 0)", (day,))
            self.db.execute("UPDATE activity SET count=count+1 WHERE day=?", (day,))
            self._add_int("tasks_done", 1)
            self._add_xp(TASK_XP)
            return TASK_XP

    # --- journal ---
    def get_journal(self, day):
        row = self.db.execute("SELECT text FROM journal WHERE day=?", (day,)).fetchone()
        return row[0] if row else ""

    def save_journal(self, day, text):
        text = text.strip()
        old_text = self.get_journal(day).strip()
        with self.db:
            if not text:
                self.db.execute("DELETE FROM journal WHERE day=?", (day,))
                # Remove one journal activity contribution only when there was one.
                if old_text:
                    self.db.execute("UPDATE activity SET count=MAX(0, count-1) WHERE day=?", (day,))
                return False
            self.db.execute("INSERT OR REPLACE INTO journal(day, text) VALUES(?, ?)", (day, text))
            if not old_text:
                self.db.execute("INSERT OR IGNORE INTO activity(day, count) VALUES(?, 0)", (day,))
                self.db.execute("UPDATE activity SET count=count+1 WHERE day=?", (day,))
        return not old_text

    def journal_count(self):
        return self.db.execute("SELECT COUNT(*) FROM journal WHERE length(trim(text)) > 0").fetchone()[0]

    def recent_journal(self, n=4):
        rows = self.db.execute("SELECT day, text FROM journal WHERE length(trim(text)) > 0 ORDER BY day DESC LIMIT ?", (n,)).fetchall()
        return [(r["day"], r["text"]) for r in rows]

    # --- quests ---
    def quest_progress(self, day):
        habits = self.db.execute("SELECT COUNT(*) FROM habit_log l JOIN habits h ON h.id=l.habit_id WHERE l.day=? AND h.active=1", (day,)).fetchone()[0]
        tasks = self.db.execute("SELECT COUNT(*) FROM tasks WHERE done=1 AND done_day=?", (day,)).fetchone()[0]
        journal = 1 if self.get_journal(day).strip() else 0
        return {"habits": habits, "tasks": tasks, "journal": journal}

    def claimed_today(self, day):
        rows = self.db.execute("SELECT key FROM quests_claimed WHERE day=?", (day,)).fetchall()
        return {r[0] for r in rows}

    def claim_quests(self, day):
        prog = self.quest_progress(day)
        newly = []
        with self.db:
            claimed = self.claimed_today(day)
            for key, title, target, reward in QUESTS:
                if prog[key] >= target and key not in claimed:
                    self.db.execute("INSERT OR IGNORE INTO quests_claimed(day, key) VALUES(?, ?)", (day, key))
                    if self.db.execute("SELECT changes()").fetchone()[0]:
                        self._add_xp(reward)
                        newly.append((title, reward))
        return newly

    # --- achievements ---
    def stats(self):
        total = self.total_xp()
        early = self.db.execute("SELECT COUNT(*) FROM habit_log WHERE completed_at IS NOT NULL AND CAST(strftime('%H', completed_at) AS INTEGER) < 8").fetchone()[0]
        return dict(total_xp=total, level=level_info(total)[0],
                    habit_checks=int(self.get("habit_checks", "0") or 0),
                    early=early, tasks_done=int(self.get("tasks_done", "0") or 0),
                    habits_created=int(self.get("habits_created", "0") or 0),
                    journal=self.journal_count(), best_streak=self.best_streak())

    def unlocked(self):
        rows = self.db.execute("SELECT key FROM achievements").fetchall()
        return {r[0] for r in rows}

    def unlock_achievements(self):
        s = self.stats()
        have = self.unlocked()
        new = []
        with self.db:
            for key, name, desc, glyph, cond in ACHIEVEMENTS:
                if key not in have and cond(s):
                    self.db.execute("INSERT OR IGNORE INTO achievements(key, day) VALUES(?, ?)", (key, today_str()))
                    if self.db.execute("SELECT changes()").fetchone()[0]:
                        new.append(name)
        return new


# ----------------------------------------------------------------------------
# Custom painted widgets
# ----------------------------------------------------------------------------
class XPBar(QWidget):
    def __init__(self, height=14, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self.accent = QColor("#ff4057")
        self.hover = QColor("#ff6476")
        self.track = QColor("#292936")
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._anim = QPropertyAnimation(self, b"value", self)

    def get_value(self):
        return self._value

    def set_value(self, v):
        self._value = float(v)
        self.update()

    value = Property(float, get_value, set_value)

    def animate_to(self, v, duration=700):
        self._anim.stop()
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(float(v))
        self._anim.start()

    def set_theme(self, P):
        self.accent = QColor(P["accent"])
        self.hover = QColor(P["hover"])
        self.track = QColor(P["border"])
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bh = max(6.0, h - 8.0)
        r = QRectF(4, (h - bh) / 2, w - 8, bh)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.track)
        p.drawRoundedRect(r, bh / 2, bh / 2)
        v = max(0.0, min(1.0, self._value))
        if v > 0:
            fr = QRectF(r.left(), r.top(), max(bh, r.width() * v), bh)
            for i, a in ((3, 25), (2, 40), (1, 60)):
                c = QColor(self.accent)
                c.setAlpha(a)
                p.setBrush(c)
                g = fr.adjusted(-i, -i, i, i)
                p.drawRoundedRect(g, bh / 2 + i, bh / 2 + i)
            grad = QLinearGradient(fr.left(), 0, fr.right(), 0)
            grad.setColorAt(0, self.accent)
            grad.setColorAt(1, self.hover)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(fr, bh / 2, bh / 2)


class RingWidget(QWidget):
    def __init__(self, size=132, parent=None):
        super().__init__(parent)
        self._value = 0.0
        self.main_text = "0/0"
        self.sub_text = "DONE"
        self.accent = QColor("#ff4057")
        self.track = QColor("#292936")
        self.text_color = QColor("#f5f5fa")
        self.muted = QColor("#9292a6")
        self.head_font = "Segoe UI"
        self.setFixedSize(size, size)
        self._anim = QPropertyAnimation(self, b"value", self)

    def get_value(self):
        return self._value

    def set_value(self, v):
        self._value = float(v)
        self.update()

    value = Property(float, get_value, set_value)

    def animate_to(self, v, duration=800):
        self._anim.stop()
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(float(v))
        self._anim.start()

    def set_texts(self, main, sub):
        self.main_text, self.sub_text = main, sub
        self.update()

    def set_theme(self, P):
        self.accent = QColor(P["accent"])
        self.track = QColor(P["border"])
        self.text_color = QColor(P["text"])
        self.muted = QColor(P["muted"])
        self.head_font = P["head_font"].strip('"')
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        s = min(w, h)
        pw = 10
        rect = QRectF((w - s) / 2 + pw + 4, (h - s) / 2 + pw + 4, s - 2 * pw - 8, s - 2 * pw - 8)
        p.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(self.track, pw)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)
        v = max(0.0, min(1.0, self._value))
        if v > 0:
            span = int(-v * 360 * 16)
            gc = QColor(self.accent)
            gc.setAlpha(45)
            gpen = QPen(gc, pw + 8)
            gpen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(gpen)
            p.drawArc(rect, 90 * 16, span)
            pen = QPen(self.accent, pw)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(rect, 90 * 16, span)
        p.setPen(self.text_color)
        f = QFont(self.head_font, 20)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, h / 2 - 26, w, 32), Qt.AlignmentFlag.AlignCenter, self.main_text)
        p.setPen(self.muted)
        f2 = QFont(self.head_font, 8)
        f2.setBold(True)
        p.setFont(f2)
        p.drawText(QRectF(0, h / 2 + 6, w, 18), Qt.AlignmentFlag.AlignCenter, self.sub_text)


class Heatmap(QWidget):
    WEEKS = 16
    CELL = 15
    GAP = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = {}
        self.accent = QColor("#ff4057")
        self.empty = QColor("#1a1a24")
        self.setMouseTracking(True)
        step = self.CELL + self.GAP
        self.setFixedSize(self.WEEKS * step, 7 * step)

    def _start(self):
        end = today()
        return end - dt.timedelta(days=(self.WEEKS - 1) * 7 + end.weekday())

    def set_data(self, data):
        self.data = data
        self.update()

    def set_theme(self, P):
        self.accent = QColor(P["accent"])
        self.empty = QColor(mix(P["panel2"], P["border"], 0.65))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        start, end = self._start(), today()
        step = self.CELL + self.GAP
        levels = [0.0, 0.30, 0.50, 0.75, 1.0]
        d = start
        while d <= end:
            col, row = (d - start).days // 7, d.weekday()
            n = self.data.get(d, 0)
            lvl = 0 if n <= 0 else 1 if n <= 2 else 2 if n <= 4 else 3 if n <= 6 else 4
            if lvl == 0:
                color = self.empty
            else:
                color = QColor(mix(self.empty.name(), self.accent.name(), levels[lvl]))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(color)
            rect = QRectF(col * step, row * step, self.CELL, self.CELL)
            p.drawRoundedRect(rect, 4, 4)
            if d == end:
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.setPen(QPen(self.accent, 1.6))
                p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 5, 5)
            d += dt.timedelta(days=1)

    def mouseMoveEvent(self, event):
        step = self.CELL + self.GAP
        pos = event.position()
        col, row = int(pos.x() // step), int(pos.y() // step)
        d = self._start() + dt.timedelta(days=col * 7 + row)
        if 0 <= row < 7 and 0 <= col < self.WEEKS and d <= today():
            n = self.data.get(d, 0)
            QToolTip.showText(
                event.globalPosition().toPoint(),
                f"{d.strftime('%d %b %Y')}  -  {n} action{'s' if n != 1 else ''}",
                self,
            )
        else:
            QToolTip.hideText()


class AvatarWidget(QWidget):
    def __init__(self, letter="K", size=46, parent=None):
        super().__init__(parent)
        self.letter = letter
        self.ring = QColor("#ff4057")
        self.fill = QColor("#101018")
        self.head_font = "Segoe UI"
        self.setFixedSize(size, size)

    def set_theme(self, P):
        self.fill = QColor(P["panel2"])
        self.head_font = P["head_font"].strip('"')
        self.update()

    def set_ring(self, color):
        self.ring = QColor(color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = QRectF(4, 4, w - 8, h - 8)
        gc = QColor(self.ring)
        gc.setAlpha(55)
        p.setPen(QPen(gc, 6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(r)
        p.setPen(QPen(self.ring, 2.4))
        p.setBrush(self.fill)
        p.drawEllipse(r)
        p.setPen(self.ring)
        f = QFont(self.head_font, 15)
        f.setBold(True)
        p.setFont(f)
        p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self.letter)


class FadeStack(QStackedWidget):
    def fade_to(self, index):
        if index == self.currentIndex():
            return
        self.setCurrentIndex(index)
        w = self.currentWidget()
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", w)
        anim.setDuration(260)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(lambda wd=w: wd.setGraphicsEffect(None))
        self._anim = anim
        anim.start()


class Central(QWidget):
    resized = Signal()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__()
        self.win = window
        self.setObjectName("titleBar")
        self.setFixedHeight(40)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 6, 10, 0)
        lay.setSpacing(4)
        lay.addWidget(make_label("VYZN  \u00b7  HABIT TRACKER", "titleText"))
        lay.addStretch()
        for text, obj, slot in (
            ("\u2014", "winBtn", window.showMinimized),
            ("\u25a2", "winBtn", window.toggle_maximize),
            ("\u2715", "closeBtn", window.close),
        ):
            b = QPushButton(text)
            b.setObjectName(obj)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(slot)
            lay.addWidget(b)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.win.windowHandle()
            if handle is not None:
                handle.startSystemMove()

    def mouseDoubleClickEvent(self, event):
        self.win.toggle_maximize()


class LevelUpOverlay(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("overlay")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(6)
        self.kicker = make_label("POWER UP", "lvlKicker")
        self.title = make_label("LEVEL UP!", "lvlTitle")
        self.level = make_label("LEVEL 02", "lvlLevel")
        self.form = make_label("", "lvlRank")
        self.hint = make_label("click anywhere to continue", "muted")
        for w in (self.kicker, self.title, self.level, self.form, self.hint):
            w.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(w)
        lay.insertSpacing(4, 14)
        self.eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.eff)
        self.token = 0
        self.hide()

    def pop(self, level, form_text, color, accent):
        self.token += 1
        token = self.token
        self.level.setText(f"LEVEL {level:02d}")
        self.form.setText(form_text)
        self.form.setStyleSheet(f"color: {color};")
        self.title.setStyleSheet(f"color: {accent};")
        add_glow(self.form, color, 34, 200)
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        anim = QPropertyAnimation(self.eff, b"opacity", self)
        anim.setDuration(350)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
        QTimer.singleShot(3200, lambda: self.dismiss(token))

    def dismiss(self, token=None):
        if token is not None and token != self.token:
            return
        if not self.isVisible():
            return
        anim = QPropertyAnimation(self.eff, b"opacity", self)
        anim.setDuration(300)
        anim.setStartValue(self.eff.opacity())
        anim.setEndValue(0.0)
        anim.finished.connect(self.hide)
        anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def mousePressEvent(self, event):
        self.dismiss()


# ----------------------------------------------------------------------------
# Stylesheet
# ----------------------------------------------------------------------------
QSS = """
QToolTip { background-color: @panel; color: @text; border: 1px solid @accent; padding: 5px 8px; }
QWidget#central { background-color: @bg; border: 1px solid @border; }
QFrame#titleBar { background: transparent; border: none; }
QLabel { color: @text; background: transparent; border: none; font-size: 13px; }
QLabel#titleText { color: @muted; font-size: 11px; font-weight: bold; }
QLabel#logo { color: @accent; font-size: 38px; font-weight: bold; font-family: @head_font; }
QLabel#muted { color: @muted; font-size: 12px; }
QLabel#sectionLabel { color: @muted; font-size: 10px; font-weight: bold; padding-bottom: 6px; }
QLabel#welcomeHeading { font-size: 32px; font-weight: bold; font-family: @head_font; }
QLabel#panelHeading { font-size: 22px; font-weight: bold; font-family: @head_font; }
QLabel#cardTitle { color: @muted; font-size: 10px; font-weight: bold; }
QLabel#cardValue { color: @text; font-size: 28px; font-weight: bold; font-family: @head_font; }
QLabel#accentLabel { color: @accent; font-size: 11px; font-weight: bold; font-family: @head_font; }
QLabel#rankBig { font-size: 26px; font-weight: bold; font-family: @head_font; }
QLabel#rankSmall { font-size: 11px; font-weight: bold; font-family: @head_font; }
QLabel#profileName { font-size: 14px; font-weight: bold; font-family: @head_font; }
QLabel#quoteText { color: @muted; font-size: 13px; }
QLabel#questTitle { font-size: 13px; font-weight: bold; }
QLabel#habitName { font-size: 15px; font-weight: bold; }
QLabel#badgeName { font-size: 11px; font-weight: bold; font-family: @head_font; }
QLabel#badgeGlyph { font-size: 22px; }
QLabel#rankChip { font-size: 12px; font-weight: bold; font-family: @head_font; background: @accent_dim; border-radius: 12px; padding: 5px 12px; }
QLabel#xpChip { color: @accent; background: @accent_dim; border: 1px solid @accent; border-radius: 9px; padding: 3px 9px; font-size: 11px; font-weight: bold; }
QLabel#toast { background-color: @panel; color: @text; border: 1px solid @accent; border-radius: 10px; padding: 10px 18px; font-size: 12px; font-weight: bold; }
QLabel#floatXP { color: @accent; font-size: 20px; font-weight: bold; font-family: @head_font; background: transparent; }
QLabel#lvlKicker { color: @muted; font-size: 14px; font-weight: bold; }
QLabel#lvlTitle { font-size: 64px; font-weight: bold; font-family: @head_font; }
QLabel#lvlLevel { font-size: 26px; font-weight: bold; font-family: @head_font; }
QLabel#lvlRank { font-size: 30px; font-weight: bold; font-family: @head_font; }

QFrame#overlay { background-color: rgba(6, 6, 12, 215); border: none; }
QFrame#sidebar { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 @panel_hi, stop:1 @panel2); border: 1px solid @border; border-radius: 16px; }
QFrame#statCard, QFrame#contentCard, QFrame#quoteCard { background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 @panel_hi, stop:1 @panel2); border: 1px solid @border; border-radius: 14px; }
QFrame#statCard:hover { border: 1px solid @accent; }
QFrame#profileCard { background-color: @panel2; border: 1px solid @border; border-radius: 13px; }
QFrame#habitRow, QFrame#taskRow, QFrame#rankRow { background-color: @panel; border: 1px solid @border; border-radius: 12px; }
QFrame#habitRow:hover, QFrame#taskRow:hover { border: 1px solid @accent; }
QFrame#habitRow[done="true"], QFrame#taskRow[done="true"] { background-color: @accent_dim; }
QFrame#badge { border-radius: 12px; }
QFrame#badge[unlocked="true"] { background-color: @accent_dim; border: 1px solid @accent; }
QFrame#badge[unlocked="false"] { background-color: @panel2; border: 1px dashed @border; }

QPushButton { font-family: @head_font; }
QPushButton#navButton { background-color: transparent; color: @muted; border: 1px solid transparent; border-radius: 9px; padding: 12px 10px; text-align: left; font-size: 14px; font-weight: bold; }
QPushButton#navButton:hover { background-color: @bg; color: @text; }
QPushButton#navButton:checked { background-color: @bg; color: @accent; border: 1px solid @border; border-left: 3px solid @accent; }
QPushButton#primaryButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @accent, stop:1 @hover); color: @on_accent; border: none; border-radius: 8px; padding: 11px 18px; font-size: 12px; font-weight: bold; }
QPushButton#primaryButton:hover { background: @hover; }
QPushButton#diffButton { background: transparent; color: @muted; border: 1px solid @border; border-radius: 8px; padding: 9px 12px; font-size: 11px; font-weight: bold; }
QPushButton#diffButton:hover { color: @text; border: 1px solid @accent; }
QPushButton#diffButton:checked { color: @accent; border: 1px solid @accent; background: @accent_dim; }
QPushButton#checkButton { background: transparent; border: 2px solid @border; border-radius: 14px; min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; color: @on_accent; font-size: 14px; font-weight: bold; }
QPushButton#checkButton:hover { border: 2px solid @accent; }
QPushButton#checkButton:checked { background: @accent; border: 2px solid @accent; }
QPushButton#iconButton { background: transparent; color: @muted; border: none; border-radius: 6px; padding: 4px 8px; font-size: 14px; }
QPushButton#iconButton:hover { color: #ff5a5a; background: @panel2; }
QPushButton#winBtn, QPushButton#closeBtn { background: transparent; color: @muted; border: none; border-radius: 6px; min-width: 36px; max-width: 36px; min-height: 26px; max-height: 26px; font-size: 13px; }
QPushButton#winBtn:hover { background: @panel; color: @text; }
QPushButton#closeBtn:hover { background: #e5384c; color: #ffffff; }

QLineEdit, QTextEdit { background-color: @panel2; color: @text; border: 1px solid @border; border-radius: 9px; padding: 10px 12px; font-size: 14px; selection-background-color: @accent; selection-color: @on_accent; }
QLineEdit:focus, QTextEdit:focus { border: 1px solid @accent; }

QScrollArea { background: transparent; border: none; }
QWidget#scrollInner { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: @border; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: @accent; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }
"""


def build_qss(P):
    qss = QSS
    for key in sorted(P.keys(), key=len, reverse=True):
        qss = qss.replace("@" + key, P[key])
    return qss


class MiniBarChart(QWidget):
    """Lightweight native Qt bar chart; no external plotting dependency."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = []
        self.labels = []
        self.accent = QColor("#ff4057")
        self.track = QColor("#292936")
        self.muted = QColor("#9292a6")
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, labels, values, accent, muted="#9292a6"):
        self.labels = list(labels)
        self.values = list(values)
        self.accent = QColor(accent)
        self.muted = QColor(muted)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        left, right, top, bottom = 8, 8, 16, 30
        chart_h = max(10, h - top - bottom)
        n = max(1, len(self.values))
        slot = max(3, (w-left-right) / n)
        bar_w = max(3, min(22, slot * 0.58))
        maxv = max(self.values, default=0) or 1
        for i, value in enumerate(self.values):
            x = left + i * slot + (slot-bar_w)/2
            bh = (chart_h - 12) * value / maxv if value else 2
            y = top + chart_h - bh
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(self.track)
            p.drawRoundedRect(QRectF(x, top, bar_w, chart_h-10), 3, 3)
            if value:
                p.setBrush(self.accent)
                p.drawRoundedRect(QRectF(x, y, bar_w, bh), 3, 3)
            # Keep labels readable for 30-day charts by only showing every fifth label.
            show_label = n <= 10 or i % 5 == 0 or i == n-1
            if show_label and i < len(self.labels):
                p.setPen(self.muted)
                p.setFont(QFont("Segoe UI", 8))
                p.drawText(QRectF(left+i*slot-2, h-bottom+2, slot+4, 20), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.labels[i])
        p.end()


# ----------------------------------------------------------------------------
# Main window
# ----------------------------------------------------------------------------
class VYZNWindow(QMainWindow):
    def __init__(self, head_font):
        super().__init__()
        self.head_font = head_font
        self.store = Store(DB_PATH)
        saved_theme = self.store.get("theme", "RED")
        self.current_theme = saved_theme if saved_theme in ACCENTS else "RED"
        self.P = build_palette(self.current_theme, head_font)
        self.navigation_buttons = {}
        self.theme_buttons = {}
        self.themed = []
        self.glow_widgets = []
        self._toasts = []
        self._built = False
        self._bar_level = None

        self.setWindowTitle("VYZN")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        self.resize(1280, 800)
        self.setMinimumSize(980, 640)

        self.build_ui()
        self._built = True
        self._last_level = self.store.level()
        self.apply_theme()
        self.show_page("Dashboard")

    # ------------------------------------------------------------ window
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def closeEvent(self, event):
        self.store.close()
        event.accept()

    def on_central_resized(self):
        self.grip.move(
            self.central.width() - self.grip.width() - 3,
            self.central.height() - self.grip.height() - 3,
        )
        self.grip.raise_()
        if self.overlay.isVisible():
            self.overlay.setGeometry(self.central.rect())

    # ------------------------------------------------------------ build
    def build_ui(self):
        self.central = Central()
        self.central.setObjectName("central")
        self.central.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCentralWidget(self.central)

        outer = QVBoxLayout(self.central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(TitleBar(self))

        body = QHBoxLayout()
        body.setContentsMargins(20, 6, 20, 20)
        body.setSpacing(22)
        outer.addLayout(body, 1)

        body.addWidget(self.build_sidebar())

        main_area = QVBoxLayout()
        main_area.setSpacing(16)

        topbar = QHBoxLayout()
        self.breadcrumb = make_label("WORKSPACE  /  DASHBOARD", "muted")
        topbar.addWidget(self.breadcrumb)
        topbar.addStretch()
        self.profile_open_btn = QPushButton("PROFILE  ↗")
        self.profile_open_btn.setObjectName("navButton")
        self.profile_open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.profile_open_btn.clicked.connect(lambda: self.show_page("Profile"))
        topbar.addWidget(self.profile_open_btn)
        topbar.addSpacing(8)
        topbar.addWidget(make_label("THEME", "muted"))
        topbar.addSpacing(6)
        for name in THEME_ORDER:
            b = QPushButton()
            b.setFixedSize(20, 20)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(name.title())
            b.clicked.connect(lambda checked=False, n=name: self.change_theme(n))
            self.theme_buttons[name] = b
            topbar.addWidget(b)
        main_area.addLayout(topbar)

        self.pages = FadeStack()
        self.pages.addWidget(self.wrap_scroll(self.build_dashboard()))
        self.pages.addWidget(self.build_habits_page())
        self.pages.addWidget(self.build_tasks_page())
        self.pages.addWidget(self.build_calendar_page())
        self.pages.addWidget(self.build_notes_page())
        self.pages.addWidget(self.wrap_scroll(self.build_journal_page()))
        self.pages.addWidget(self.wrap_scroll(self.build_analysis_page()))
        self.pages.addWidget(self.wrap_scroll(self.build_progress_page()))
        self.pages.addWidget(self.wrap_scroll(self.build_profile_page()))
        main_area.addWidget(self.pages, 1)
        body.addLayout(main_area, 1)

        self.overlay = LevelUpOverlay(self.central)
        self.grip = QSizeGrip(self.central)
        self.central.resized.connect(self.on_central_resized)

    def wrap_scroll(self, inner):
        inner.setObjectName("scrollInner")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidget(inner)
        return scroll

    def page_header(self, title, subtitle):
        box = QVBoxLayout()
        box.setSpacing(4)
        box.addWidget(make_label(title, "welcomeHeading"))
        box.addWidget(make_label(subtitle, "muted"))
        return box

    # ---- sidebar
    def build_sidebar(self):
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(236)
        lay = QVBoxLayout(self.sidebar)
        lay.setContentsMargins(14, 18, 14, 14)
        lay.setSpacing(8)

        self.logo = make_label("VYZN", "logo")
        self.glow_widgets.append(self.logo)
        lay.addWidget(self.logo)
        lay.addWidget(make_label("YOUR VISION. YOUR RULES.", "muted"))
        lay.addSpacing(22)
        lay.addWidget(make_label("WORKSPACE", "sectionLabel"))

        for name, glyph, icon_name in NAV_ITEMS:
            text = f"  {name}" if HAS_QTA else f"  {glyph}    {name}"
            b = QPushButton(text)
            b.setObjectName("navButton")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.setIconSize(QSize(18, 18))
            b.clicked.connect(lambda checked=False, n=name: self.show_page(n))
            self.navigation_buttons[name] = b
            lay.addWidget(b)
        lay.addStretch()

        profile = QFrame()
        profile.setObjectName("profileCard")
        pl = QVBoxLayout(profile)
        pl.setContentsMargins(12, 12, 12, 12)
        pl.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.avatar = AvatarWidget((self.store.get("profile_name", PLAYER_NAME) or PLAYER_NAME)[:1].upper())
        self.themed.append(self.avatar)
        top.addWidget(self.avatar)
        info = QVBoxLayout()
        info.setSpacing(0)
        self.sidebar_profile_name = make_label((self.store.get("profile_name", PLAYER_NAME) or PLAYER_NAME).upper(), "profileName")
        info.addWidget(self.sidebar_profile_name)
        self.profile_rank = make_label("BASE FORM", "rankSmall")
        info.addWidget(self.profile_rank)
        self.profile_level = make_label("LEVEL 01", "muted")
        info.addWidget(self.profile_level)
        top.addLayout(info, 1)
        pl.addLayout(top)
        self.profile_bar = XPBar(14)
        self.themed.append(self.profile_bar)
        pl.addWidget(self.profile_bar)
        lay.addWidget(profile)
        return self.sidebar

    # ---- dashboard
    def create_stat_card(self, title, value, desc):
        card = QFrame()
        card.setObjectName("statCard")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(8)
        head = QHBoxLayout()
        head.addWidget(make_label(title.upper(), "cardTitle"))
        head.addStretch()
        lay.addLayout(head)
        v = make_label(value, "cardValue")
        d = make_label(desc, "muted")
        lay.addWidget(v)
        lay.addWidget(d)
        return card, v, d, head

    def build_dashboard(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 8, 6)
        lay.setSpacing(18)

        # welcome row
        wrow = QHBoxLayout()
        welcome = QVBoxLayout()
        welcome.setSpacing(4)
        self.dashboard_welcome = make_label(f"Welcome back, {self.store.get('profile_name', PLAYER_NAME) or PLAYER_NAME}.", "welcomeHeading")
        welcome.addWidget(self.dashboard_welcome)
        self.dashboard_tagline = make_label(self.store.get("profile_tagline", "Stay focused. Build consistency. Become your best self.") or "Stay focused. Build consistency. Become your best self.", "muted")
        self.dashboard_tagline.setWordWrap(True)
        welcome.addWidget(self.dashboard_tagline)
        wrow.addLayout(welcome)
        wrow.addStretch()
        self.rank_chip = make_label("BASE FORM", "rankChip")
        wrow.addWidget(self.rank_chip, alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(wrow)

        # stats
        stats = QGridLayout()
        stats.setSpacing(14)
        c1, self.stat_habits_v, self.stat_habits_d, _ = self.create_stat_card(
            "Active Habits", "0", "Start building your routine")
        c2, self.stat_tasks_v, self.stat_tasks_d, _ = self.create_stat_card(
            "Tasks Today", "0", "One step at a time")
        c3, self.stat_streak_v, self.stat_streak_d, head3 = self.create_stat_card(
            "Current Streak", "0 days", "Consistency starts today")
        self.flame = QLabel("\U0001F525")
        self.flame.setStyleSheet("font-size: 22px; background: transparent;")
        head3.addWidget(self.flame)
        stats.addWidget(c1, 0, 0)
        stats.addWidget(c2, 0, 1)
        stats.addWidget(c3, 0, 2)
        for i in range(3):
            stats.setColumnStretch(i, 1)
        lay.addLayout(stats)

        # mission + progress
        panels = QHBoxLayout()
        panels.setSpacing(14)

        mission = QFrame()
        mission.setObjectName("contentCard")
        ml = QHBoxLayout(mission)
        ml.setContentsMargins(24, 22, 24, 22)
        ml.setSpacing(20)
        mtext = QVBoxLayout()
        mtext.setSpacing(12)
        mtext.addWidget(make_label("TODAY'S MISSION", "accentLabel"))
        self.mission_title = make_label("Make today count.", "panelHeading")
        mtext.addWidget(self.mission_title)
        self.mission_desc = make_label("Every completed habit is a vote for the person you want to become.", "muted", True)
        mtext.addWidget(self.mission_desc)
        mtext.addSpacing(6)
        self.mission_btn = QPushButton("+   BUILD YOUR HABITS")
        self.mission_btn.setObjectName("primaryButton")
        self.mission_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mission_btn.clicked.connect(lambda: self.show_page("Habits"))
        self.glow_widgets.append(self.mission_btn)
        mtext.addWidget(self.mission_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        mtext.addStretch()
        ml.addLayout(mtext, 1)
        self.ring = RingWidget(140)
        self.themed.append(self.ring)
        ml.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignVCenter)

        progress = QFrame()
        progress.setObjectName("contentCard")
        pl = QVBoxLayout(progress)
        pl.setContentsMargins(24, 22, 24, 22)
        pl.setSpacing(10)
        pl.addWidget(make_label("YOUR POWER LEVEL", "accentLabel"))
        self.prog_rank = make_label("BASE FORM", "rankBig")
        pl.addWidget(self.prog_rank)
        self.prog_level = make_label("LEVEL 01", "panelHeading")
        pl.addWidget(self.prog_level)
        self.prog_xp = make_label("0 / 100 XP", "muted")
        pl.addWidget(self.prog_xp)
        self.xp_bar = XPBar(18)
        self.themed.append(self.xp_bar)
        pl.addWidget(self.xp_bar)
        self.prog_next = make_label("", "muted", True)
        pl.addWidget(self.prog_next)
        pl.addStretch()

        panels.addWidget(mission, 3)
        panels.addWidget(progress, 2)
        lay.addLayout(panels)

        # quests + heatmap
        row = QHBoxLayout()
        row.setSpacing(14)

        quests = QFrame()
        quests.setObjectName("contentCard")
        ql = QVBoxLayout(quests)
        ql.setContentsMargins(24, 22, 24, 22)
        ql.setSpacing(12)
        ql.addWidget(make_label("DAILY QUESTS", "accentLabel"))
        self.quest_widgets = []
        for key, title, target, reward in QUESTS:
            box = QVBoxLayout()
            box.setSpacing(5)
            head = QHBoxLayout()
            t = make_label(title, "questTitle")
            cnt = make_label(f"0/{target}", "muted")
            chip = make_label(f"+{reward} XP", "xpChip")
            head.addWidget(t)
            head.addStretch()
            head.addWidget(cnt)
            head.addSpacing(8)
            head.addWidget(chip)
            bar = XPBar(12)
            self.themed.append(bar)
            box.addLayout(head)
            box.addWidget(bar)
            ql.addLayout(box)
            self.quest_widgets.append((key, t, cnt, chip, bar, target, reward))
        ql.addStretch()

        heat = QFrame()
        heat.setObjectName("contentCard")
        hl = QVBoxLayout(heat)
        hl.setContentsMargins(24, 22, 24, 22)
        hl.setSpacing(12)
        hl.addWidget(make_label("CONSISTENCY  \u00b7  LAST 16 WEEKS", "accentLabel"))
        self.heatmap = Heatmap()
        self.themed.append(self.heatmap)
        hl.addWidget(self.heatmap, alignment=Qt.AlignmentFlag.AlignLeft)
        hl.addWidget(make_label("Brighter squares = more habits, tasks and entries completed that day.", "muted", True))
        hl.addStretch()

        row.addWidget(quests, 1)
        row.addWidget(heat, 1)
        lay.addLayout(row)

        # quote
        quote = QFrame()
        quote.setObjectName("quoteCard")
        qlay = QVBoxLayout(quote)
        qlay.setContentsMargins(20, 16, 20, 16)
        q = make_label('"%s"' % QUOTES[today().toordinal() % len(QUOTES)], "quoteText")
        q.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qlay.addWidget(q)
        lay.addWidget(quote)
        lay.addStretch()
        return page

    # ---- habits
    def build_habits_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(16)
        lay.addLayout(self.page_header("Habits", "Clear habits every day to earn XP and keep your streak alive."))

        card = QFrame()
        card.setObjectName("contentCard")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(18, 16, 18, 16)
        cl.setSpacing(10)
        self.habit_input = QLineEdit()
        self.habit_input.setPlaceholderText("New habit  (e.g. Workout 30 min)")
        self.habit_input.returnPressed.connect(self.add_habit)
        cl.addWidget(self.habit_input, 1)
        self.diff_group = QButtonGroup(self)
        self.diff_group.setExclusive(True)
        for label, xp in (("EASY  +10", 10), ("MEDIUM  +20", 20), ("HARD  +30", 30)):
            b = QPushButton(label)
            b.setObjectName("diffButton")
            b.setCheckable(True)
            b.setProperty("xp", xp)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if xp == 20:
                b.setChecked(True)
            self.diff_group.addButton(b)
            cl.addWidget(b)
        add = QPushButton("+  ADD HABIT")
        add.setObjectName("primaryButton")
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self.add_habit)
        self.glow_widgets.append(add)
        cl.addWidget(add)
        lay.addWidget(card)

        inner = QWidget()
        self.habit_list = QVBoxLayout(inner)
        self.habit_list.setContentsMargins(0, 0, 8, 0)
        self.habit_list.setSpacing(10)
        lay.addWidget(self.wrap_scroll(inner), 1)
        return page

    def add_habit(self):
        name = self.habit_input.text().strip()
        if not name:
            return
        btn = self.diff_group.checkedButton()
        xp = int(btn.property("xp")) if btn else 20
        self.store.add_habit(name[:80], xp)
        self.habit_input.clear()
        self.process_rewards(None, 0)

    def make_habit_row(self, h):
        row = QFrame()
        row.setObjectName("habitRow")
        row.setProperty("done", "true" if h["done"] else "false")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(16, 12, 14, 12)
        lay.setSpacing(14)
        chk = QPushButton("\u2713" if h["done"] else "")
        chk.setObjectName("checkButton")
        chk.setCheckable(True)
        chk.setChecked(h["done"])
        chk.setCursor(Qt.CursorShape.PointingHandCursor)
        chk.clicked.connect(lambda checked=False, hid=h["id"], b=chk: self.on_habit_toggle(hid, b))
        lay.addWidget(chk)
        info = QVBoxLayout()
        info.setSpacing(2)
        name = make_label(h["name"], "habitName")
        if h["done"]:
            name.setStyleSheet(f"text-decoration: line-through; color: {self.P['muted']};")
        info.addWidget(name)
        s = h["streak"]
        info.addWidget(make_label(
            f"\U0001F525 {s} day streak" if s else "No streak yet - clear it today", "muted"))
        lay.addLayout(info, 1)
        lay.addWidget(make_label(f"+{h['xp']} XP", "xpChip"))
        d = QPushButton("\u2715")
        d.setObjectName("iconButton")
        d.setCursor(Qt.CursorShape.PointingHandCursor)
        d.setToolTip("Archive habit (preserve history)")
        d.clicked.connect(lambda checked=False, hid=h["id"]: self.on_habit_delete(hid))
        lay.addWidget(d)
        return row

    def on_habit_toggle(self, hid, btn):
        delta = self.store.toggle_habit(hid, today_str())
        self.process_rewards(btn, delta)

    def on_habit_delete(self, hid):
        answer = QMessageBox.question(
            self, "Archive habit", "Archive this habit? Its completion history will be preserved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.store.archive_habit(hid)
        self.process_rewards(None, 0)

    def rebuild_habits(self, habits):
        clear_layout(self.habit_list)
        if not habits:
            self.habit_list.addWidget(make_label("No habits yet. Add your first one above to start earning XP.", "muted"))
        for h in habits:
            self.habit_list.addWidget(self.make_habit_row(h))
        self.habit_list.addStretch()

    # ---- tasks
    def build_tasks_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(16)
        lay.addLayout(self.page_header("Tasks", f"Plan your work, set deadlines, and finish tasks for +{TASK_XP} XP each."))

        card = QFrame(); card.setObjectName("contentCard")
        cl = QVBoxLayout(card); cl.setContentsMargins(18, 16, 18, 16); cl.setSpacing(10)
        top = QHBoxLayout()
        self.task_input = QLineEdit(); self.task_input.setPlaceholderText("Task title...")
        self.task_input.returnPressed.connect(self.add_task)
        top.addWidget(self.task_input, 1)
        self.task_priority = QComboBox(); self.task_priority.addItems(["Low", "Medium", "High"]); self.task_priority.setCurrentText("Medium")
        self.task_priority.setMinimumWidth(110)
        top.addWidget(self.task_priority)
        cl.addLayout(top)
        bottom = QHBoxLayout()
        self.task_has_deadline = QCheckBox("Set deadline")
        self.task_due_date = QDateEdit(); self.task_due_date.setCalendarPopup(True); self.task_due_date.setDisplayFormat("dd MMM yyyy")
        self.task_due_date.setDate(QDate.currentDate().addDays(1)); self.task_due_date.setEnabled(False)
        self.task_has_deadline.toggled.connect(self.task_due_date.setEnabled)
        bottom.addWidget(self.task_has_deadline); bottom.addWidget(self.task_due_date); bottom.addStretch()
        add = QPushButton("+  ADD TASK"); add.setObjectName("primaryButton"); add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self.add_task); self.glow_widgets.append(add); bottom.addWidget(add)
        cl.addLayout(bottom)
        lay.addWidget(card)

        inner = QWidget(); self.task_list = QVBoxLayout(inner)
        self.task_list.setContentsMargins(0, 0, 8, 0); self.task_list.setSpacing(10)
        lay.addWidget(self.wrap_scroll(inner), 1)
        return page

    def add_task(self):
        title = self.task_input.text().strip()
        if not title:
            return
        due = self.task_due_date.date().toString("yyyy-MM-dd") if self.task_has_deadline.isChecked() else None
        self.store.add_task(title[:120], due, self.task_priority.currentText())
        self.task_input.clear()
        self.task_priority.setCurrentText("Medium")
        self.task_has_deadline.setChecked(False)
        self.process_rewards(None, 0)

    def edit_task(self, task):
        dialog = QDialog(self); dialog.setWindowTitle("Task options"); dialog.setMinimumWidth(380)
        form = QFormLayout(dialog)
        title = QLineEdit(task["title"])
        description = QLineEdit(task.get("description", "")); description.setPlaceholderText("Optional details")
        priority = QComboBox(); priority.addItems(["Low", "Medium", "High"]); priority.setCurrentText(task.get("priority", "Medium"))
        has_due = QCheckBox("Task has a deadline"); has_due.setChecked(bool(task.get("due_date")))
        due = QDateEdit(); due.setCalendarPopup(True); due.setDisplayFormat("dd MMM yyyy")
        due.setDate(QDate.fromString(task.get("due_date") or today_str(), "yyyy-MM-dd")); due.setEnabled(has_due.isChecked())
        has_due.toggled.connect(due.setEnabled)
        form.addRow("Task title", title); form.addRow("Details", description); form.addRow("Priority", priority)
        form.addRow("Deadline", has_due); form.addRow("Due date", due)
        buttons = QHBoxLayout(); save = QPushButton("SAVE CHANGES"); save.setObjectName("primaryButton")
        cancel = QPushButton("CANCEL"); cancel.setObjectName("navButton")
        save.clicked.connect(dialog.accept); cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel); buttons.addWidget(save); form.addRow(buttons)
        if dialog.exec() == QDialog.DialogCode.Accepted and title.text().strip():
            due_value = due.date().toString("yyyy-MM-dd") if has_due.isChecked() else None
            self.store.update_task(task["id"], title.text()[:120], due_value, priority.currentText(), description.text())
            self.process_rewards(None, 0)

    def make_task_row(self, t):
        done = bool(t["done"])
        row = QFrame(); row.setObjectName("taskRow"); row.setProperty("done", "true" if done else "false")
        lay = QHBoxLayout(row); lay.setContentsMargins(16, 12, 14, 12); lay.setSpacing(10)
        chk = QPushButton("✓" if done else ""); chk.setObjectName("checkButton")
        chk.setCheckable(True); chk.setChecked(done); chk.setCursor(Qt.CursorShape.PointingHandCursor)
        chk.clicked.connect(lambda checked=False, tid=t["id"], b=chk: self.on_task_toggle(tid, b)); lay.addWidget(chk)
        text_col = QVBoxLayout(); text_col.setSpacing(3)
        name = make_label(t["title"], "habitName")
        if done: name.setStyleSheet(f"text-decoration: line-through; color: {self.P['muted']};")
        text_col.addWidget(name)
        meta = []
        due = t.get("due_date")
        if due:
            due_date = dt.date.fromisoformat(due)
            if done: due_text = "DUE " + due_date.strftime("%d %b %Y")
            elif due_date < today(): due_text = "OVERDUE · " + due_date.strftime("%d %b %Y")
            elif due_date == today(): due_text = "DUE TODAY"
            else: due_text = "DUE " + due_date.strftime("%d %b %Y")
            meta.append(due_text)
        meta.append("PRIORITY: " + t.get("priority", "Medium").upper())
        if t.get("description"): meta.append(t["description"])
        meta_label = make_label("  ·  ".join(meta), "muted", True); text_col.addWidget(meta_label)
        if not done and due and dt.date.fromisoformat(due) < today():
            name.setStyleSheet(f"color: {self.P['accent']}; font-weight: 700;")
        lay.addLayout(text_col, 1)
        lay.addWidget(make_label(f"+{TASK_XP} XP", "xpChip"))
        edit = QPushButton("✎"); edit.setObjectName("iconButton"); edit.setToolTip("Edit title, details, priority or deadline")
        edit.clicked.connect(lambda checked=False, task=dict(t): self.edit_task(task)); lay.addWidget(edit)
        d = QPushButton("✕"); d.setObjectName("iconButton"); d.setToolTip("Delete task")
        d.clicked.connect(lambda checked=False, tid=t["id"]: self.on_task_delete(tid)); lay.addWidget(d)
        return row

    def on_task_toggle(self, tid, btn):
        delta = self.store.toggle_task(tid, today_str())
        self.process_rewards(btn, delta)

    def on_task_delete(self, tid):
        answer = QMessageBox.question(
            self, "Delete task", "Permanently delete this task? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.store.delete_task(tid)
        self.process_rewards(None, 0)

    def rebuild_tasks(self):
        clear_layout(self.task_list)
        tasks = self.store.visible_tasks(today_str())
        if not tasks:
            self.task_list.addWidget(make_label("No tasks right now. Add one above.", "muted"))
        for t in tasks:
            self.task_list.addWidget(self.make_task_row(t))
        self.task_list.addStretch()

    # ---- notes
    def build_notes_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(16)
        lay.addLayout(self.page_header("Notes", "A scratchpad that saves itself."))
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Ideas, plans, reminders...")
        self.notes_edit.setPlainText(self.store.get("notes", ""))
        self.notes_timer = QTimer(self)
        self.notes_timer.setSingleShot(True)
        self.notes_timer.setInterval(600)
        self.notes_timer.timeout.connect(lambda: self.store.set("notes", self.notes_edit.toPlainText()))
        self.notes_edit.textChanged.connect(self.notes_timer.start)
        lay.addWidget(self.notes_edit, 1)
        return page

    # ---- journal
    def build_journal_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 8, 6)
        lay.setSpacing(16)
        lay.addLayout(self.page_header("Journal", f"Write today's entry for +{JOURNAL_XP} XP."))
        card = QFrame()
        card.setObjectName("contentCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 20, 22, 20)
        cl.setSpacing(12)
        cl.addWidget(make_label(today().strftime("%A, %d %B %Y").upper(), "accentLabel"))
        self.journal_edit = QTextEdit()
        self.journal_edit.setMinimumHeight(240)
        self.journal_edit.setPlaceholderText("How did today go? What did you learn?")
        self.journal_edit.setPlainText(self.store.get_journal(today_str()))
        cl.addWidget(self.journal_edit)
        row = QHBoxLayout()
        self.journal_btn = QPushButton("SAVE ENTRY")
        self.journal_btn.setObjectName("primaryButton")
        self.journal_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.journal_btn.clicked.connect(self.save_journal)
        self.glow_widgets.append(self.journal_btn)
        self.journal_status = make_label("", "muted")
        row.addWidget(self.journal_btn)
        row.addWidget(self.journal_status)
        row.addStretch()
        cl.addLayout(row)
        lay.addWidget(card)

        lay.addWidget(make_label("RECENT ENTRIES", "accentLabel"))
        self.journal_recent = QVBoxLayout()
        self.journal_recent.setSpacing(8)
        lay.addLayout(self.journal_recent)
        lay.addStretch()
        return page

    def save_journal(self):
        text = self.journal_edit.toPlainText().strip()
        if not text:
            self.journal_status.setText("Write something first.")
            return
        is_new = self.store.save_journal(today_str(), text)
        delta = JOURNAL_XP if is_new else 0
        if is_new:
            self.store.add_xp(delta)
        self.journal_status.setText("Saved." if not is_new else "Saved. XP earned!")
        self.process_rewards(self.journal_btn, delta)

    # ---- calendar
    def build_calendar_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 8, 6)
        lay.setSpacing(16)
        lay.addLayout(self.page_header("Calendar", "Explore your consistency and review what you completed on any day."))

        card = QFrame(); card.setObjectName("contentCard")
        outer = QVBoxLayout(card); outer.setContentsMargins(20, 18, 20, 20); outer.setSpacing(14)
        header = QHBoxLayout()
        self.calendar_prev = QPushButton("‹  PREVIOUS")
        self.calendar_prev.setObjectName("navButton")
        self.calendar_next = QPushButton("NEXT  ›")
        self.calendar_next.setObjectName("navButton")
        self.calendar_today = QPushButton("TODAY")
        self.calendar_today.setObjectName("navButton")
        self.calendar_month_label = make_label("MONTH YEAR", "panelHeading")
        header.addWidget(self.calendar_prev); header.addWidget(self.calendar_today); header.addStretch()
        header.addWidget(self.calendar_month_label); header.addStretch(); header.addWidget(self.calendar_next)
        outer.addLayout(header)
        self.calendar_grid = QGridLayout(); self.calendar_grid.setSpacing(6)
        for col, name in enumerate(("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")):
            lbl = make_label(name, "cardTitle"); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.calendar_grid.addWidget(lbl, 0, col)
        outer.addLayout(self.calendar_grid)
        legend = QHBoxLayout()
        legend.addWidget(make_label("LESS ACTIVITY", "muted"))
        for alpha in (0.12, 0.30, 0.52, 0.78, 1.0):
            swatch = QFrame(); swatch.setFixedSize(18, 12); swatch.setStyleSheet(f"background: {mix(self.P['panel'], self.P['accent'], alpha)}; border-radius: 3px;")
            legend.addWidget(swatch)
        legend.addWidget(make_label("MORE ACTIVITY", "muted")); legend.addStretch()
        outer.addLayout(legend)
        lay.addWidget(card)

        detail = QFrame(); detail.setObjectName("contentCard")
        dl = QVBoxLayout(detail); dl.setContentsMargins(20, 18, 20, 20); dl.setSpacing(8)
        self.calendar_detail_title = make_label("SELECT A DAY", "panelHeading")
        self.calendar_detail_summary = make_label("Days with completed habits, tasks, or journal entries are highlighted.", "muted", True)
        self.calendar_detail_habits = make_label("Habits: —", "bodyText", True)
        self.calendar_detail_tasks = make_label("Completed tasks: —", "bodyText", True)
        self.calendar_detail_deadlines = make_label("Deadlines: —", "bodyText", True)
        self.calendar_detail_events = make_label("Important dates: —", "bodyText", True)
        self.calendar_detail_journal = make_label("Journal: —", "bodyText", True)
        dl.addWidget(self.calendar_detail_title); dl.addWidget(self.calendar_detail_summary)
        dl.addWidget(self.calendar_detail_habits); dl.addWidget(self.calendar_detail_tasks); dl.addWidget(self.calendar_detail_deadlines); dl.addWidget(self.calendar_detail_events); dl.addWidget(self.calendar_detail_journal)
        lay.addWidget(detail); lay.addStretch()
        self.calendar_cursor = today().replace(day=1)
        self.calendar_selected = today()
        self.calendar_prev.clicked.connect(lambda: self.shift_calendar_month(-1))
        self.calendar_next.clicked.connect(lambda: self.shift_calendar_month(1))
        self.calendar_today.clicked.connect(self.calendar_go_today)
        self.render_calendar()
        return page

    def shift_calendar_month(self, delta):
        y, m = self.calendar_cursor.year, self.calendar_cursor.month + delta
        if m < 1: y, m = y-1, 12
        if m > 12: y, m = y+1, 1
        self.calendar_cursor = dt.date(y, m, 1)
        self.render_calendar()

    def calendar_go_today(self):
        self.calendar_cursor = today().replace(day=1)
        self.calendar_selected = today()
        self.render_calendar()

    def select_calendar_day(self, day):
        self.calendar_selected = day
        self.render_calendar()

    def render_calendar(self):
        if not hasattr(self, "calendar_grid"):
            return
        while self.calendar_grid.count() > 7:
            item = self.calendar_grid.takeAt(7)
            widget = item.widget()
            if widget: widget.deleteLater()
        cursor = self.calendar_cursor
        self.calendar_month_label.setText(cursor.strftime("%B %Y").upper())
        _, days_in_month = pycalendar.monthrange(cursor.year, cursor.month)
        first_weekday = dt.date(cursor.year, cursor.month, 1).weekday()
        month_days = [dt.date(cursor.year, cursor.month, d) for d in range(1, days_in_month+1)]
        start = month_days[0] - dt.timedelta(days=first_weekday)
        end = start + dt.timedelta(days=41)
        activity = self.store.activity_map(start)
        details_days = {dt.date.fromisoformat(r[0]) for r in self.store.db.execute("SELECT day FROM journal WHERE TRIM(text)<>''").fetchall()}
        for r in self.store.db.execute("SELECT DISTINCT day FROM habit_log").fetchall(): details_days.add(dt.date.fromisoformat(r[0]))
        for r in self.store.db.execute("SELECT DISTINCT done_day FROM tasks WHERE done=1 AND done_day IS NOT NULL").fetchall(): details_days.add(dt.date.fromisoformat(r[0]))
        for r in self.store.db.execute("SELECT DISTINCT due_date FROM tasks WHERE due_date IS NOT NULL").fetchall(): details_days.add(dt.date.fromisoformat(r[0]))
        due_days = {dt.date.fromisoformat(r[0]) for r in self.store.db.execute("SELECT DISTINCT due_date FROM tasks WHERE due_date IS NOT NULL AND done=0").fetchall()}
        important_by_day = {}
        important_days = set()
        for event in self.store.important_dates_for_month(cursor.year, cursor.month):
            event_day = dt.date.fromisoformat(event["display_date"])
            important_days.add(event_day)
            important_by_day.setdefault(event_day, []).append(event)
        for offset in range(42):
            day = start + dt.timedelta(days=offset)
            row, col = 1 + offset//7, offset%7
            if day.month != cursor.month:
                b = QPushButton(""); b.setEnabled(False); b.setFixedHeight(42)
                b.setStyleSheet("background: transparent; border: none;")
            else:
                count = int(activity.get(day, 0))
                alpha = min(0.82, 0.14 + count*0.14) if count else 0
                bg = mix(self.P['panel'], self.P['accent'], alpha) if count else self.P['panel2']
                selected = day == self.calendar_selected
                border = self.P['text'] if selected else self.P['border']
                marker = " •" if day in details_days else ""
                deadline_marker = " !" if day in due_days else ""
                event_marker = " ★" if day in important_days else ""
                b = QPushButton(f"{day.day}{marker}{deadline_marker}{event_marker}")
                b.setFixedHeight(42); b.setCursor(Qt.CursorShape.PointingHandCursor)
                event_names = ", ".join(e["title"] for e in important_by_day.get(day, []))
                tooltip = f"{day.strftime('%A, %d %B %Y')} · {count} recorded action(s)"
                if event_names:
                    tooltip += f" · Important: {event_names}"
                b.setToolTip(tooltip)
                b.setStyleSheet(f"QPushButton {{ background: {bg}; color: {self.P['text']}; border: {'2px' if selected else '1px'} solid {border}; border-radius: 7px; font-weight: {'700' if day == today() else '500'}; }} QPushButton:hover {{ border: 1px solid {self.P['accent']}; }}")
                b.clicked.connect(lambda checked=False, d=day: self.select_calendar_day(d))
            self.calendar_grid.addWidget(b, row, col)
        self.update_calendar_details()

    def update_calendar_details(self):
        day = self.calendar_selected
        info = self.store.day_details(day.isoformat())
        self.calendar_detail_title.setText(day.strftime("%A, %d %B %Y").upper())
        count = len(info['habits']) + len(info['tasks']) + (1 if info['journal'].strip() else 0)
        self.calendar_detail_summary.setText(f"{count} recorded action(s) · {self.store.activity_map(day).get(day, 0)} activity points")
        self.calendar_detail_habits.setText("Habits: " + (", ".join(h['name'] for h in info['habits']) if info['habits'] else "None recorded"))
        self.calendar_detail_tasks.setText("Completed tasks: " + (", ".join(info['tasks']) if info['tasks'] else "None completed"))
        if info['due_tasks']:
            deadline_lines = [f"{'✓' if t['done'] else '○'} {t['title']} [{t['priority']}]{' · COMPLETED' if t['done'] else (' · OVERDUE' if day < today() else '')}" for t in info['due_tasks']]
            self.calendar_detail_deadlines.setText("Deadlines: " + "  |  ".join(deadline_lines))
        else:
            self.calendar_detail_deadlines.setText("Deadlines: No tasks due on this date")
        events = self.store.important_dates_on(day)
        if events:
            event_lines = [f"★ {e['title']} ({e['category']})" + (f" — {e['notes']}" if e['notes'] else "") for e in events]
            self.calendar_detail_events.setText("Important dates: " + "  |  ".join(event_lines))
        else:
            self.calendar_detail_events.setText("Important dates: None added")
        journal_preview = " ".join(info['journal'].split())
        if len(journal_preview) > 220: journal_preview = journal_preview[:217] + "..."
        self.calendar_detail_journal.setText("Journal: " + (journal_preview if journal_preview else "No entry"))

    # ---- profile and important dates
    def build_profile_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 8, 6)
        lay.setSpacing(16)
        lay.addLayout(self.page_header("Your Profile", "Make VYZN yours. Personalise your identity and add the dates that matter."))

        card = QFrame(); card.setObjectName("contentCard")
        form = QVBoxLayout(card); form.setContentsMargins(20, 18, 20, 20); form.setSpacing(12)
        form.addWidget(make_label("PERSONAL DETAILS", "panelHeading"))
        self.profile_name_input = QLineEdit(self.store.get("profile_name", PLAYER_NAME) or PLAYER_NAME)
        self.profile_name_input.setPlaceholderText("What should VYZN call you?")
        self.profile_tagline_input = QLineEdit(self.store.get("profile_tagline", "Stay focused. Build consistency. Become your best self.") or "")
        self.profile_tagline_input.setPlaceholderText("Your personal motivation / tagline")
        self.profile_tagline_input.setMaxLength(180)
        form.addWidget(make_label("DISPLAY NAME", "cardTitle")); form.addWidget(self.profile_name_input)
        form.addWidget(make_label("MOTIVATIONAL TAGLINE", "cardTitle")); form.addWidget(self.profile_tagline_input)
        form.addWidget(make_label("Your name appears in the sidebar and dashboard. Your tagline appears below the dashboard greeting.", "muted", True))
        self.profile_save_status = make_label("", "muted")
        save = QPushButton("SAVE PROFILE"); save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self.save_profile)
        form.addWidget(save); form.addWidget(self.profile_save_status)
        lay.addWidget(card)

        dates_card = QFrame(); dates_card.setObjectName("contentCard")
        dates = QVBoxLayout(dates_card); dates.setContentsMargins(20, 18, 20, 20); dates.setSpacing(12)
        dates.addWidget(make_label("IMPORTANT DATES", "panelHeading"))
        dates.addWidget(make_label("Add birthdays, exams, interviews, anniversaries, events, or any date you want visible in your calendar.", "muted", True))
        self.event_title_input = QLineEdit(); self.event_title_input.setPlaceholderText("Event title (e.g. Final examination)")
        self.event_date_input = QDateEdit(QDate.currentDate()); self.event_date_input.setCalendarPopup(True); self.event_date_input.setDisplayFormat("dd MMM yyyy")
        self.event_category_input = QComboBox(); self.event_category_input.addItems(["Personal", "Birthday", "Anniversary", "Exam", "Interview", "College", "Work", "Other"])
        self.event_notes_input = QLineEdit(); self.event_notes_input.setPlaceholderText("Optional notes")
        self.event_yearly_input = QCheckBox("Repeat every year")
        event_grid = QGridLayout(); event_grid.setHorizontalSpacing(10); event_grid.setVerticalSpacing(8)
        event_grid.addWidget(make_label("TITLE", "cardTitle"), 0, 0); event_grid.addWidget(make_label("DATE", "cardTitle"), 0, 1)
        event_grid.addWidget(self.event_title_input, 1, 0); event_grid.addWidget(self.event_date_input, 1, 1)
        event_grid.addWidget(make_label("CATEGORY", "cardTitle"), 2, 0); event_grid.addWidget(make_label("NOTES", "cardTitle"), 2, 1)
        event_grid.addWidget(self.event_category_input, 3, 0); event_grid.addWidget(self.event_notes_input, 3, 1)
        dates.addLayout(event_grid)
        add_row = QHBoxLayout(); add_row.addWidget(self.event_yearly_input); add_row.addStretch()
        add_event = QPushButton("+ ADD IMPORTANT DATE"); add_event.setCursor(Qt.CursorShape.PointingHandCursor); add_event.clicked.connect(self.add_important_date_from_form)
        add_row.addWidget(add_event); dates.addLayout(add_row)
        dates.addWidget(make_label("SAVED DATES", "cardTitle"))
        self.important_dates_list = QVBoxLayout(); self.important_dates_list.setSpacing(8)
        dates.addLayout(self.important_dates_list)
        lay.addWidget(dates_card)

        danger_card = QFrame(); danger_card.setObjectName("contentCard")
        danger = QVBoxLayout(danger_card); danger.setContentsMargins(20, 18, 20, 20); danger.setSpacing(10)
        danger.addWidget(make_label("DANGER ZONE", "panelHeading"))
        danger.addWidget(make_label("Start VYZN from scratch by clearing habits, completions, tasks, notes, journal entries, important dates, XP, quests, achievements, and profile details. Your current theme is kept. A backup is created first.", "muted", True))
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        self.clear_data_button = QPushButton("CLEAR ALL DATA / START FRESH")
        self.clear_data_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_data_button.setObjectName("navButton")
        self.clear_data_button.clicked.connect(self.clear_all_data_confirm)
        reset_row.addWidget(self.clear_data_button)
        danger.addLayout(reset_row)
        lay.addWidget(danger_card)
        lay.addStretch()
        self.rebuild_important_dates_list()
        return page

    def clear_all_data_confirm(self):
        first = QMessageBox.question(
            self, "Clear all VYZN data?",
            "This will permanently clear your habits, habit history, tasks, notes, journal, important dates, XP, quests, achievements, and profile name/tagline.\n\nVYZN will create a database backup before clearing. Your selected theme will be kept.\n\nDo you want to continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if first != QMessageBox.StandardButton.Yes:
            return
        confirmation, ok = QInputDialog.getText(
            self, "Confirm reset", "Type RESET to clear all data:", QLineEdit.EchoMode.Normal, ""
        )
        if not ok or confirmation.strip() != "RESET":
            QMessageBox.information(self, "Reset cancelled", "Your data has not been changed. Type RESET exactly to confirm.")
            return
        try:
            backup_dir = DATA_DIR / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"vyzn_backup_{stamp}.db"
            with sqlite3.connect(str(backup_path)) as backup_db:
                self.store.db.backup(backup_db)
            theme = self.store.get("theme", "RED")
            with self.store.db:
                for table in ("habit_log", "habits", "tasks", "journal", "activity", "quests_claimed", "achievements", "important_dates"):
                    self.store.db.execute(f"DELETE FROM {table}")
                self.store.db.execute("DELETE FROM meta")
                self.store._set("theme", theme)
                self.store._set("profile_name", "Player")
                self.store._set("profile_tagline", "")
            self.profile_name_input.setText("Player")
            self.profile_tagline_input.clear()
            self.profile_save_status.setText("Profile reset.")
            self.sidebar_profile_name.setText("PLAYER")
            self.avatar.letter = "P"
            self.avatar.update()
            self.dashboard_welcome.setText("Welcome back, Player.")
            self.dashboard_tagline.setText("Keep moving forward, one day at a time.")
            self.notes_edit.blockSignals(True); self.notes_edit.clear(); self.notes_edit.blockSignals(False)
            self.journal_edit.blockSignals(True); self.journal_edit.clear(); self.journal_edit.blockSignals(False)
            self.journal_status.setText("")
            self.event_title_input.clear(); self.event_notes_input.clear(); self.event_yearly_input.setChecked(False)
            self.refresh_all()
            self.rebuild_important_dates_list()
            self.render_calendar()
            QMessageBox.information(self, "VYZN reset complete", f"All data has been cleared. A backup was saved here:\n{backup_path}")
            self.show_page("Dashboard")
        except Exception as exc:
            QMessageBox.critical(self, "Reset failed", f"VYZN could not clear the data safely.\n\nDetails: {exc}")

    def save_profile(self):
        name = self.profile_name_input.text().strip() or "Player"
        tagline = self.profile_tagline_input.text().strip()
        self.store.set("profile_name", name)
        self.store.set("profile_tagline", tagline)
        self.sidebar_profile_name.setText(name.upper())
        self.avatar.letter = name[:1].upper()
        self.avatar.update()
        self.dashboard_welcome.setText(f"Welcome back, {name}.")
        self.dashboard_tagline.setText(tagline or "Keep moving forward, one day at a time.")
        self.profile_save_status.setText("Profile saved.")

    def add_important_date_from_form(self):
        title = self.event_title_input.text().strip()
        if not title:
            QMessageBox.information(self, "Add important date", "Enter a title for this date first.")
            self.event_title_input.setFocus()
            return
        date = self.event_date_input.date().toString("yyyy-MM-dd")
        self.store.add_important_date(title, date, self.event_category_input.currentText(), self.event_notes_input.text(), self.event_yearly_input.isChecked())
        self.event_title_input.clear(); self.event_notes_input.clear(); self.event_yearly_input.setChecked(False)
        self.rebuild_important_dates_list()
        if hasattr(self, "calendar_grid"):
            self.render_calendar()
        self.toast("IMPORTANT DATE ADDED")

    def rebuild_important_dates_list(self):
        if not hasattr(self, "important_dates_list"):
            return
        clear_layout(self.important_dates_list)
        rows = self.store.db.execute("SELECT * FROM important_dates ORDER BY event_date, title").fetchall()
        if not rows:
            self.important_dates_list.addWidget(make_label("No important dates yet. Add one above and it will appear in Calendar.", "muted", True))
            return
        for event in rows:
            row = QFrame(); row.setObjectName("taskRow")
            rl = QHBoxLayout(row); rl.setContentsMargins(12, 10, 12, 10); rl.setSpacing(10)
            event_date = dt.date.fromisoformat(event["event_date"])
            title = f"{event['title']}  ·  {event_date.strftime('%d %b %Y')}"
            if event["recurring_yearly"]:
                title += "  ·  YEARLY"
            details = f"{event['category']}" + (f"  ·  {event['notes']}" if event["notes"] else "")
            text_col = QVBoxLayout(); text_col.addWidget(make_label(title, "cardTitle")); text_col.addWidget(make_label(details, "muted", True))
            rl.addLayout(text_col, 1)
            delete = QPushButton("DELETE"); delete.setCursor(Qt.CursorShape.PointingHandCursor); delete.setObjectName("navButton")
            delete.clicked.connect(lambda checked=False, eid=event["id"], etitle=event["title"]: self.delete_important_date_confirm(eid, etitle))
            rl.addWidget(delete)
            self.important_dates_list.addWidget(row)

    def delete_important_date_confirm(self, event_id, title):
        answer = QMessageBox.question(self, "Delete important date", f"Remove '{title}' from your calendar?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.store.delete_important_date(event_id)
            self.rebuild_important_dates_list()
            self.render_calendar()

    # ---- analysis dashboard
    def build_analysis_page(self):
        page = QWidget()
        self.analysis_layout = QVBoxLayout(page)
        self.analysis_layout.setContentsMargins(0, 6, 8, 6)
        self.analysis_layout.setSpacing(16)
        self.rebuild_analysis()
        return page

    def rebuild_analysis(self):
        if not hasattr(self, "analysis_layout"):
            return
        lay = self.analysis_layout
        clear_layout(lay)
        lay.addLayout(self.page_header("Analysis", "Evidence of your consistency — recent activity, completion patterns, and lifetime totals."))
        a = self.store.analysis_summary()
        cards = QGridLayout(); cards.setSpacing(12)
        metrics = [
            ("CURRENT STREAK", f"{a['current_streak']} days", "Consecutive active days"),
            ("BEST STREAK", f"{a['best_streak']} days", "Your personal record"),
            ("HABIT COMPLETIONS", f"{a['habit_completions']:,}", "All recorded completions"),
            ("TASKS COMPLETED", f"{a['tasks_completed']:,}", "Of all tasks created"),
            ("JOURNAL ENTRIES", f"{a['journal_entries']:,}", "Days with an entry"),
            ("TOTAL XP", f"{a['total_xp']:,}", "Lifetime power earned"),
        ]
        for i, (title, value, desc) in enumerate(metrics):
            c = QFrame(); c.setObjectName("statCard")
            cl = QVBoxLayout(c); cl.setContentsMargins(16, 14, 16, 14); cl.setSpacing(5)
            cl.addWidget(make_label(title, "cardTitle")); cl.addWidget(make_label(value, "cardValue")); cl.addWidget(make_label(desc, "muted", True))
            cards.addWidget(c, i//3, i%3)
        lay.addLayout(cards)

        week = QFrame(); week.setObjectName("contentCard")
        wl = QVBoxLayout(week); wl.setContentsMargins(20, 18, 20, 16); wl.setSpacing(6)
        wl.addWidget(make_label("LAST 7 DAYS · DAILY ACTIVITY", "accentLabel"))
        wl.addWidget(make_label("A day counts when you complete a habit, finish a task, or save a journal entry.", "muted", True))
        self.analysis_week_chart = MiniBarChart(); wl.addWidget(self.analysis_week_chart)
        lay.addWidget(week)

        month = QFrame(); month.setObjectName("contentCard")
        ml = QVBoxLayout(month); ml.setContentsMargins(20, 18, 20, 16); ml.setSpacing(6)
        ml.addWidget(make_label("LAST 30 DAYS · ACTIVITY TREND", "accentLabel"))
        ml.addWidget(make_label("Compare your daily activity points. Habit completions and task completions contribute to the total.", "muted", True))
        self.analysis_month_chart = MiniBarChart(); ml.addWidget(self.analysis_month_chart)
        lay.addWidget(month)

        insight = QFrame(); insight.setObjectName("contentCard")
        il = QVBoxLayout(insight); il.setContentsMargins(20, 18, 20, 18); il.setSpacing(8)
        il.addWidget(make_label("YOUR CURRENT READOUT", "accentLabel"))
        active_days_30 = sum(1 for n in a['last30_activity'] if n > 0)
        avg = sum(a['last30_activity']) / 30
        strongest = max(a['last30_activity'], default=0)
        if active_days_30 >= 24: consistency = "Excellent: you recorded activity on at least 24 of the last 30 days."
        elif active_days_30 >= 14: consistency = "Building momentum: keep your routines small and repeatable."
        elif active_days_30 > 0: consistency = "A starting point: aim for one small, trackable action each day."
        else: consistency = "No recent activity has been recorded yet. Start with one habit today."
        for line in (f"Consistency: {active_days_30}/30 active days.", f"Average activity: {avg:.1f} points per day; highest single-day total: {strongest}.", consistency):
            il.addWidget(make_label("•  " + line, "bodyText", True))
        lay.addWidget(insight)
        lay.addStretch()
        self.analysis_week_chart.set_data(a['last7_labels'], a['last7_activity'], self.P['accent'], self.P['muted'])
        self.analysis_month_chart.set_data(a['last30_labels'], a['last30_activity'], self.P['accent'], self.P['muted'])

    # ---- placeholder
    def build_placeholder(self, name, text):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 6, 0, 0)
        lay.setSpacing(16)
        lay.addLayout(self.page_header(name, f"Your personal {name.lower()} workspace."))
        card = QFrame()
        card.setObjectName("contentCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.addWidget(make_label("COMING SOON", "accentLabel"))
        cl.addWidget(make_label(f"{name} is under construction.", "panelHeading"))
        cl.addWidget(make_label(text, "muted", True))
        cl.addStretch()
        lay.addWidget(card)
        lay.addStretch()
        return page

    # ---- progress page
    def build_progress_page(self):
        page = QWidget()
        self.progress_layout = QVBoxLayout(page)
        self.progress_layout.setContentsMargins(0, 6, 8, 6)
        self.progress_layout.setSpacing(18)
        return page

    def rebuild_progress(self, level):
        P = self.P
        lay = self.progress_layout
        clear_layout(lay)
        lay.addLayout(self.page_header("Progress", "Your forms, achievements and lifetime stats."))

        # lifetime stats
        s = self.store.stats()
        stats_card = QFrame()
        stats_card.setObjectName("contentCard")
        sg = QGridLayout(stats_card)
        sg.setContentsMargins(24, 20, 24, 20)
        sg.setHorizontalSpacing(24)
        items = [
            ("TOTAL XP", f"{s['total_xp']:,}"),
            ("HABITS CLEARED", str(s["habit_checks"])),
            ("TASKS DONE", str(s["tasks_done"])),
            ("BEST STREAK", f"{s['best_streak']} d"),
            ("JOURNAL ENTRIES", str(s["journal"])),
        ]
        for i, (t, v) in enumerate(items):
            box = QVBoxLayout()
            box.setSpacing(4)
            box.addWidget(make_label(t, "cardTitle"))
            box.addWidget(make_label(v, "cardValue"))
            sg.addLayout(box, 0, i)
            sg.setColumnStretch(i, 1)
        lay.addWidget(stats_card)

        # forms ladder
        lay.addWidget(make_label("FORMS  \u00b7  RANK LADDER", "accentLabel"))
        cur = rank_for_level(level)
        for min_lvl, name, series, color in RANKS:
            unlocked = level >= min_lvl
            is_cur = name == cur[1]
            row = QFrame()
            row.setObjectName("rankRow")
            row.setProperty("done", "true" if is_cur else "false")
            if is_cur:
                row.setStyleSheet(f"QFrame#rankRow {{ border: 1px solid {color}; }}")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(16, 10, 16, 10)
            rl.setSpacing(12)
            dot = QLabel("\u25cf" if unlocked else "\U0001F512")
            dot.setStyleSheet(f"color: {color if unlocked else P['muted']}; font-size: 14px;")
            rl.addWidget(dot)
            nm = make_label(name, "habitName")
            nm.setStyleSheet(f"color: {color if unlocked else P['muted']};")
            rl.addWidget(nm)
            rl.addWidget(make_label(series, "muted"))
            rl.addStretch()
            tag = f"LEVEL {min_lvl}" + ("   \u25c4 CURRENT" if is_cur else "")
            rl.addWidget(make_label(tag, "muted"))
            lay.addWidget(row)

        # achievements
        lay.addWidget(make_label("ACHIEVEMENTS", "accentLabel"))
        have = self.store.unlocked()
        grid = QGridLayout()
        grid.setSpacing(12)
        cols = 5
        for i, (key, name, desc, glyph, _) in enumerate(ACHIEVEMENTS):
            on = key in have
            badge = QFrame()
            badge.setObjectName("badge")
            badge.setProperty("unlocked", "true" if on else "false")
            badge.setToolTip(desc)
            bl = QVBoxLayout(badge)
            bl.setContentsMargins(10, 14, 10, 14)
            bl.setSpacing(6)
            g = QLabel(glyph if on else "\U0001F512")
            g.setObjectName("badgeGlyph")
            g.setAlignment(Qt.AlignmentFlag.AlignCenter)
            g.setStyleSheet(f"color: {P['accent'] if on else P['muted']}; font-size: 24px;")
            n = make_label(name, "badgeName")
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            n.setStyleSheet(f"color: {P['text'] if on else P['muted']};")
            d = make_label(desc, "muted", True)
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            d.setStyleSheet(f"color: {P['muted']}; font-size: 11px;")
            bl.addWidget(g)
            bl.addWidget(n)
            bl.addWidget(d)
            grid.addWidget(badge, i // cols, i % cols)
        for c in range(cols):
            grid.setColumnStretch(c, 1)
        lay.addLayout(grid)
        lay.addStretch()

    # ------------------------------------------------------------ toasts / fx
    def float_text(self, text, origin=None):
        lbl = QLabel(text, self.central)
        lbl.setObjectName("floatXP")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setFixedSize(170, 36)
        if text.startswith("-"):
            lbl.setStyleSheet("color: #ff6b6b;")
        if origin is not None and origin.isVisible():
            c = origin.mapTo(self.central, origin.rect().center())
        else:
            c = QPoint(self.central.width() // 2, self.central.height() // 2)
        lbl.move(c.x() - lbl.width() // 2, c.y() - lbl.height() // 2)
        lbl.show()
        lbl.raise_()
        eff = QGraphicsOpacityEffect(lbl)
        lbl.setGraphicsEffect(eff)
        group = QParallelAnimationGroup(lbl)
        a1 = QPropertyAnimation(lbl, b"pos")
        a1.setDuration(1000)
        a1.setStartValue(lbl.pos())
        a1.setEndValue(lbl.pos() + QPoint(0, -64))
        a1.setEasingCurve(QEasingCurve.Type.OutCubic)
        a2 = QPropertyAnimation(eff, b"opacity")
        a2.setDuration(1000)
        a2.setStartValue(1.0)
        a2.setEndValue(0.0)
        a2.setEasingCurve(QEasingCurve.Type.InQuad)
        group.addAnimation(a1)
        group.addAnimation(a2)
        group.finished.connect(lbl.deleteLater)
        self._float_group = group
        group.start()

    def toast(self, text):
        t = QLabel(text, self.central)
        t.setObjectName("toast")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.ensurePolished()
        t.adjustSize()
        y = 52 + 48 * len(self._toasts)
        t.move((self.central.width() - t.width()) // 2, y)
        t.show()
        t.raise_()
        self._toasts.append(t)
        eff = QGraphicsOpacityEffect(t)
        t.setGraphicsEffect(eff)
        seq = QSequentialAnimationGroup(t)
        fade_in = QPropertyAnimation(eff, b"opacity")
        fade_in.setDuration(200)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_out = QPropertyAnimation(eff, b"opacity")
        fade_out.setDuration(450)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        seq.addAnimation(fade_in)
        seq.addAnimation(QPauseAnimation(2400))
        seq.addAnimation(fade_out)

        def done(tt=t):
            if tt in self._toasts:
                self._toasts.remove(tt)
            tt.deleteLater()

        seq.finished.connect(done)
        if not hasattr(self, "_toast_groups"):
            self._toast_groups = []
        self._toast_groups.append(seq)
        seq.start()

    def show_level_up(self, level, old_level):
        rank, old = rank_for_level(level), rank_for_level(old_level)
        if rank[1] != old[1]:
            form = f"NEW FORM UNLOCKED\n{rank[1]}"
        else:
            form = rank[1]
        self.overlay.pop(level, form, rank[3], self.P["accent"])
        play_sound("levelup")

    # ------------------------------------------------------------ game loop
    def process_rewards(self, origin, delta):
        old_level = self._last_level
        if delta:
            self.float_text(f"{delta:+d} XP", origin)
            if delta > 0:
                play_sound("xp")
        day = today_str()
        for title, reward in self.store.claim_quests(day):
            self.toast(f"QUEST COMPLETE  \u00b7  {title}  +{reward} XP")
        for name in self.store.unlock_achievements():
            self.toast(f"ACHIEVEMENT UNLOCKED  \u00b7  {name}")
        self.refresh_all()
        new_level = self.store.level()
        if new_level > old_level:
            self.show_level_up(new_level, old_level)
        self._last_level = new_level

    def refresh_all(self):
        if not self._built:
            return
        P, s = self.P, self.store
        day = today_str()
        habits = s.habits_status(day)
        done = sum(1 for h in habits if h["done"])
        total = len(habits)
        pending, tasks_today = s.task_counts(day)
        streak = s.current_streak()
        total_xp = s.total_xp()
        level, into, need = level_info(total_xp)
        rank = rank_for_level(level)
        nxt = next_rank(level)
        rc = rank[3]

        # stat cards
        self.stat_habits_v.setText(str(total))
        self.stat_habits_d.setText(f"{done} cleared today" if total else "Start building your routine")
        self.stat_tasks_v.setText(str(pending))
        self.stat_tasks_d.setText(f"{tasks_today} done today" if (pending or tasks_today) else "One step at a time")
        self.stat_streak_v.setText(f"{streak} day{'s' if streak != 1 else ''}")
        self.stat_streak_d.setText("Keep the fire alive" if streak else "Consistency starts today")
        if streak > 0:
            add_glow(self.flame, "#ff8a00", 24, 230)
        else:
            eff = QGraphicsOpacityEffect(self.flame)
            eff.setOpacity(0.25)
            self.flame.setGraphicsEffect(eff)

        # mission
        left = total - done
        if total == 0:
            self.mission_title.setText("Build your first habit.")
            self.mission_desc.setText("Add a habit to start earning XP and leveling up.")
            self.mission_btn.setText("+   BUILD YOUR HABITS")
        elif left == 0:
            self.mission_title.setText("All habits cleared.")
            self.mission_desc.setText("Legendary work. Come back tomorrow to keep the streak going.")
            self.mission_btn.setText("VIEW HABITS")
        else:
            self.mission_title.setText("Make today count.")
            self.mission_desc.setText(f"{left} habit{'s' if left != 1 else ''} left to clear today.")
            self.mission_btn.setText("CLEAR YOUR HABITS")
        self.ring.set_texts(f"{done}/{total}" if total else "-", "CLEARED" if total else "NO HABITS")
        self.ring.animate_to(done / total if total else 0)

        # power level
        self.prog_rank.setText(rank[1])
        self.prog_rank.setStyleSheet(f"color: {rc};")
        add_glow(self.prog_rank, rc, 26, 160)
        self.prog_level.setText(f"LEVEL {level:02d}")
        self.prog_xp.setText(f"{into} / {need} XP   \u00b7   {total_xp:,} total")
        if self._bar_level != level:
            self.xp_bar.set_value(0.0)
            self.profile_bar.set_value(0.0)
            self._bar_level = level
        self.xp_bar.animate_to(into / need)
        self.profile_bar.animate_to(into / need)
        if nxt:
            self.prog_next.setText(f"Next form: {nxt[1]} at level {nxt[0]}.")
        else:
            self.prog_next.setText("You have reached the final form. Keep going.")
        self.rank_chip.setText(f"\u26a1  {rank[1]}")
        self.rank_chip.setStyleSheet(f"color: {rc}; border: 1px solid {rc};")
        self.profile_rank.setText(rank[1])
        self.profile_rank.setStyleSheet(f"color: {rc};")
        self.profile_level.setText(f"LEVEL {level:02d}")
        self.avatar.set_ring(rc)

        # quests
        prog = s.quest_progress(day)
        claimed = s.claimed_today(day)
        for key, t, cnt, chip, bar, target, reward in self.quest_widgets:
            p = min(prog[key], target)
            cnt.setText(f"{p}/{target}")
            bar.animate_to(p / target)
            if key in claimed or prog[key] >= target:
                chip.setText(f"\u2713  +{reward} XP")
            else:
                chip.setText(f"+{reward} XP")

        # heatmap
        start = today() - dt.timedelta(days=Heatmap.WEEKS * 7 + 7)
        self.heatmap.set_data(s.activity_map(start))

        # lists
        self.rebuild_habits(habits)
        self.rebuild_tasks()
        self.rebuild_progress(level)
        self.rebuild_analysis()
        if hasattr(self, "calendar_grid"):
            self.render_calendar()

        # journal recent
        clear_layout(self.journal_recent)
        recent = s.recent_journal(4)
        if not recent:
            self.journal_recent.addWidget(make_label("No entries yet.", "muted"))
        for day_s, text in recent:
            row = QFrame()
            row.setObjectName("taskRow")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(16, 10, 16, 10)
            rl.setSpacing(2)
            rl.addWidget(make_label(dt.date.fromisoformat(day_s).strftime("%a, %d %b %Y").upper(), "cardTitle"))
            first = text.strip().splitlines()[0]
            rl.addWidget(make_label(first[:110] + ("..." if len(first) > 110 else ""), "muted"))
            self.journal_recent.addWidget(row)

    # ------------------------------------------------------------ pages / theme
    def show_page(self, name):
        self.pages.fade_to(PAGES.index(name))
        self.active_page = name
        self.breadcrumb.setText(f"WORKSPACE  /  {name.upper()}")
        self.update_nav()
        if name == "Calendar" and hasattr(self, "calendar_grid"):
            self.render_calendar()
        elif name == "Analysis" and hasattr(self, "analysis_layout"):
            self.rebuild_analysis()
        elif name == "Profile" and hasattr(self, "important_dates_list"):
            self.rebuild_important_dates_list()

    def update_nav(self):
        for name, glyph, icon_name in NAV_ITEMS:
            b = self.navigation_buttons[name]
            active = name == getattr(self, "active_page", "Dashboard")
            b.setChecked(active)
            if HAS_QTA:
                color = self.P["accent"] if active else self.P["muted"]
                try:
                    b.setIcon(qta.icon(icon_name, color=color))
                except Exception:
                    pass

    def change_theme(self, name):
        self.current_theme = name
        self.store.set("theme", name)
        self.apply_theme()

    def apply_theme(self):
        self.P = build_palette(self.current_theme, self.head_font)
        P = self.P
        QApplication.instance().setStyleSheet(build_qss(P))
        for w in self.themed:
            w.set_theme(P)
        for w in self.glow_widgets:
            add_glow(w, P["accent"], 30 if w is not self.logo else 26, 150)
        for name, btn in self.theme_buttons.items():
            acc = ACCENTS[name][0]
            sel = name == self.current_theme
            border = "2px solid #ffffff" if sel else "2px solid transparent"
            btn.setStyleSheet(
                f"QPushButton {{ background: {acc}; border-radius: 10px; border: {border}; }}"
                f"QPushButton:hover {{ border: 2px solid {P['text']}; }}"
            )
        self.update_nav()
        self.refresh_all()


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("krishna.vyzn.habittracker")
        except Exception:
            pass
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("VYZN")
    app.setWindowIcon(make_app_icon())
    head = pick_heading_font()
    app.setFont(QFont("Segoe UI", 10))
    window = VYZNWindow(head)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()