"""Параллельные запросы (двойной клик, две вкладки): проигравший не падает с 500."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.errors import Conflict
from app.security import hash_password
from app.services import registration, testing
from tests.helpers import assign


def _rival(session: Session) -> Session:
    return sessionmaker(bind=session.get_bind(), expire_on_commit=False)()


def test_start_attempt_returns_attempt_created_meanwhile(
    admin: TestClient, session: Session, monkeypatch
):
    assignment_id = assign(admin, ["ПК-2"])["assignment"]["id"]
    student = session.scalar(select(models.Student).where(models.Student.full_name.like("Иванов%")))
    choose = testing._choose_variant

    def choose_after_rival_started(sess, assignment):
        variant = choose(sess, assignment)
        with _rival(session) as rival:  # параллельный запрос успел раньше
            rival.add(
                models.Attempt(assignment_id=assignment.id, student_id=student.id, variant=variant)
            )
            rival.commit()
        return variant

    monkeypatch.setattr(testing, "_choose_variant", choose_after_rival_started)
    attempt, questions = testing.start_attempt(session, assignment_id, student)

    assert questions
    assert session.scalar(select(func.count()).select_from(models.Attempt)) == 1
    assert attempt.student_id == student.id


def test_register_twice_at_once_gives_conflict_not_500(
    admin: TestClient, session: Session, monkeypatch
):
    group = session.scalar(select(models.Group))
    session.add(models.Student(full_name="Гонкин Гонка Гонкович", group_id=group.id))
    session.commit()
    student = session.scalar(
        select(models.Student).where(models.Student.full_name == "Гонкин Гонка Гонкович")
    )

    def hash_after_rival_registered(password):
        with _rival(session) as rival:  # параллельный запрос успел раньше
            rival.add(
                models.User(
                    username="Гонкин Гонка Гонкович",
                    password_hash="x",
                    role=models.Role.STUDENT,
                    student_id=student.id,
                )
            )
            rival.commit()
        return hash_password(password)

    monkeypatch.setattr(registration, "hash_password", hash_after_rival_registered)
    with pytest.raises(Conflict, match="уже зарегистрирован"):
        registration.register_student(
            session, group.id, "Гонкин Гонка Гонкович", "Свой-пароль-2026", "127.0.0.1"
        )
