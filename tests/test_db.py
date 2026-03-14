from pathlib import Path

from database.db import Database
from tasks.task_definition import TaskDefinition


def test_db_lifecycle(tmp_path: Path) -> None:
    db = Database(tmp_path / "test.db")
    db.init_db()

    task = TaskDefinition(
        name="Task",
        schedule="0 0 * * *",
        goal="Goal",
        tools=["crypto_price"],
        inputs={},
        enabled=True,
    )
    db.upsert_task(task)
    run_id = db.start_run("Task", None)
    db.save_result(run_id, "summary", {"summary": "summary"}, {}, {})
    db.finish_run(run_id, "success")

    results = db.get_last_results()
    assert results
    assert results[0]["name"] == "Task"
