"""Демо-банк проходит те же проверки, что вопрос, созданный через API.

seed пишет вопросы в базу напрямую, поэтому без этого теста некорректное задание (например,
соответствие с одной парой) попало бы в демо-данные и всплыло бы только в случайном варианте.
"""

import pytest

from app import schemas
from scripts.demo_questions import QUESTIONS


def as_question_in(spec: dict) -> schemas.QuestionIn:
    if spec["kind"] == "open":
        options = [{"text": a} for a in spec["answers"]]
    elif spec["kind"] == "sequence":
        options = [{"text": t} for t in spec["items"]]
    else:
        pairs, extra = spec["pairs"], spec.get("extra", [])
        options = [
            {"text": left, "match_index": len(pairs) + i} for i, (left, _) in enumerate(pairs)
        ]
        options += [{"text": right} for _, right in pairs] + [{"text": t} for t in extra]
    return schemas.QuestionIn(
        competency_id=1, text=spec["text"], kind=spec["kind"], options=options
    )


@pytest.mark.parametrize("spec", QUESTIONS, ids=lambda s: s["text"][:40])
def test_demo_question_is_valid(spec):
    as_question_in(spec)
    if spec["kind"] == "matching":
        rights = [r for _, r in spec["pairs"]] + spec.get("extra", [])
        assert len(set(rights)) == len(rights), "в правом столбце повторяются элементы"
