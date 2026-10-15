import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vyzn.main import Store, today_str, TASK_XP


def make_store(tmp_path):
    return Store(tmp_path / "test.db")


def test_habit_archive_preserves_history(tmp_path):
    store = make_store(tmp_path)
    try:
        store.add_habit("Read", 20)
        habit = store.habits_status(today_str())[0]
        assert store.toggle_habit(habit["id"], today_str()) == 20
        assert store.archive_habit(habit["id"]) is True
        assert store.habits_status(today_str()) == []
        assert store.db.execute("SELECT COUNT(*) FROM habit_log WHERE habit_id=?", (habit["id"],)).fetchone()[0] == 1
        assert store.restore_habit(habit["id"]) is True
        assert len(store.habits_status(today_str())) == 1
    finally:
        store.close()


def test_habit_completion_xp_is_atomic_and_reversible(tmp_path):
    store = make_store(tmp_path)
    try:
        store.add_habit("Read", 20)
        habit_id = store.habits_status(today_str())[0]["id"]
        assert store.toggle_habit(habit_id, today_str()) == 20
        assert store.total_xp() == 20
        assert store.toggle_habit(habit_id, today_str()) == -20
        assert store.total_xp() == 0
    finally:
        store.close()


def test_task_completion_xp_and_activity(tmp_path):
    store = make_store(tmp_path)
    try:
        store.add_task("Study")
        task_id = store.db.execute("SELECT id FROM tasks").fetchone()[0]
        assert store.toggle_task(task_id, today_str()) == TASK_XP
        assert store.total_xp() == TASK_XP
        assert store.toggle_task(task_id, today_str()) == -TASK_XP
        assert store.total_xp() == 0
    finally:
        store.close()


def test_journal_edit_does_not_increment_activity_twice(tmp_path):
    store = make_store(tmp_path)
    try:
        day = today_str()
        assert store.save_journal(day, "First entry") is True
        assert store.save_journal(day, "Edited entry") is False
        assert store.db.execute("SELECT count FROM activity WHERE day=?", (day,)).fetchone()[0] == 1
        store.save_journal(day, "")
        assert store.get_journal(day) == ""
        assert store.db.execute("SELECT count FROM activity WHERE day=?", (day,)).fetchone()[0] == 0
    finally:
        store.close()


def test_quest_cannot_be_claimed_twice(tmp_path):
    store = make_store(tmp_path)
    try:
        day = today_str()
        for i in range(3):
            store.add_habit(f"Habit {i}", 1)
            habit_id = store.db.execute("SELECT id FROM habits ORDER BY id DESC LIMIT 1").fetchone()[0]
            store.toggle_habit(habit_id, day)
        before = store.total_xp()
        first = store.claim_quests(day)
        after_first = store.total_xp()
        second = store.claim_quests(day)
        assert first
        assert second == []
        assert store.total_xp() == after_first
        assert after_first >= before
    finally:
        store.close()


def test_task_deadline_priority_and_details_persist(tmp_path):
    store = make_store(tmp_path)
    try:
        due = ( __import__("datetime").date.today() + __import__("datetime").timedelta(days=2)).isoformat()
        store.add_task("Submit project", due, "High", "Upload report and source code")
        task = dict(store.db.execute("SELECT * FROM tasks").fetchone())
        assert task["due_date"] == due
        assert task["priority"] == "High"
        assert task["description"] == "Upload report and source code"
        assert store.day_details(due)["due_tasks"][0]["title"] == "Submit project"
        store.update_task(task["id"], "Submit final project", None, "Low", "Updated details")
        updated = dict(store.db.execute("SELECT * FROM tasks WHERE id=?", (task["id"],)).fetchone())
        assert updated["title"] == "Submit final project"
        assert updated["due_date"] is None
        assert updated["priority"] == "Low"
    finally:
        store.close()


def test_important_dates_are_saved_and_recurring_dates_show_each_year(tmp_path):
    import datetime as dt

    store = make_store(tmp_path)
    try:
        store.add_important_date("Birthday", "2000-05-14", "Birthday", "Family day", True)
        store.add_important_date("Exam", "2026-10-20", "Exam", "Bring ID", False)

        birthday = store.important_dates_on(dt.date(2027, 5, 14))
        assert len(birthday) == 1
        assert birthday[0]["title"] == "Birthday"
        assert birthday[0]["notes"] == "Family day"

        exam = store.important_dates_on(dt.date(2026, 10, 20))
        assert [event["title"] for event in exam] == ["Exam"]
        assert store.important_dates_on(dt.date(2027, 10, 20)) == []

        may_events = store.important_dates_for_month(2027, 5)
        assert any(event["title"] == "Birthday" and event["display_date"] == "2027-05-14" for event in may_events)
    finally:
        store.close()


def test_important_date_can_be_deleted(tmp_path):
    store = make_store(tmp_path)
    try:
        store.add_important_date("Interview", "2026-11-02", "Interview")
        event_id = store.db.execute("SELECT id FROM important_dates").fetchone()[0]
        store.delete_important_date(event_id)
        assert store.db.execute("SELECT COUNT(*) FROM important_dates").fetchone()[0] == 0
    finally:
        store.close()
