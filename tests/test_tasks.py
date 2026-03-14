from pathlib import Path

from tasks.task_definition import load_task_file, TaskValidationError


def test_load_task_file(tmp_path: Path) -> None:
    content = """
name: "Test Task"
schedule: "0 0 * * *"
goal: "Test goal"
tools:
  - "crypto_price"
inputs:
  coin_id: "bitcoin"
"""
    path = tmp_path / "task.yaml"
    path.write_text(content)
    task = load_task_file(path)
    assert task.name == "Test Task"
    assert task.schedule == "0 0 * * *"
    assert task.inputs["coin_id"] == "bitcoin"


def test_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "task.yaml"
    path.write_text("name: 'Bad Task'")
    try:
        load_task_file(path)
        assert False, "Expected validation error"
    except TaskValidationError:
        assert True
