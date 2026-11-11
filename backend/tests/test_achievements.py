import os

os.environ.setdefault("BASEROW_URL", "http://example.invalid")
os.environ.setdefault("BASEROW_API_TOKEN", "test")
os.environ.setdefault("APP_USERNAME", "test")
os.environ.setdefault("APP_PASSWORD", "test")
os.environ.setdefault("SESSION_SECRET", "test")

from app.schemas import AchievementOut, mythic_status


def make(unlocked, required):
    return AchievementOut(id=1, name="x", game_id=1, unlocked=unlocked, required_for_mythic=required, notes="")


def test_mythic_achieved_when_all_required_unlocked():
    status = mythic_status(1, [make(True, True), make(True, True), make(False, False)])
    assert status.achieved is True
    assert status.required_total == 2
    assert status.required_unlocked == 2
    assert status.total == 3
    assert status.unlocked == 2


def test_mythic_not_achieved_with_locked_required():
    status = mythic_status(1, [make(True, True), make(False, True)])
    assert status.achieved is False
    assert status.required_unlocked == 1


def test_mythic_not_achieved_with_no_required_achievements():
    status = mythic_status(1, [make(True, False), make(False, False)])
    assert status.achieved is False
    assert status.required_total == 0


def test_mythic_with_no_achievements():
    status = mythic_status(1, [])
    assert status.achieved is False
    assert status.total == 0
