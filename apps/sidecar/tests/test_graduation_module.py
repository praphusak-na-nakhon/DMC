from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from dmc_sidecar.modules import graduation_legacy as legacy


M3 = "\u0e21.3"
M6 = "\u0e21.6"


class FakeCell:
    def __init__(self, text: str) -> None:
        self._text = text

    def inner_text(self) -> str:
        return self._text


class FakeListLocator:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def count(self) -> int:
        return len(self._items)

    def nth(self, index: int) -> Any:
        return self._items[index]

    @property
    def first(self) -> Any:
        return self._items[0] if self._items else EmptyLocator()


class EmptyLocator:
    def count(self) -> int:
        return 0


class FakeOptionLocator:
    def __init__(self, exists: bool) -> None:
        self._exists = exists

    def count(self) -> int:
        return 1 if self._exists else 0


class FakeSelect:
    def __init__(self, values: set[str]) -> None:
        self.values = values
        self.selected: list[str] = []

    def count(self) -> int:
        return 1

    def locator(self, selector: str) -> FakeOptionLocator:
        marker = "option[value='"
        value = selector[len(marker) : -2]
        return FakeOptionLocator(value in self.values)

    def select_option(self, *, value: str) -> None:
        self.selected.append(value)


class FakeRow:
    def __init__(
        self,
        *,
        row_id: str,
        seq_no: str,
        room: str,
        student_no: str,
        first_name: str,
        last_name: str,
        option_values: set[str],
    ) -> None:
        self.row_id = row_id
        self.select = FakeSelect(option_values)
        texts = [""] * 11
        texts[1] = seq_no
        texts[3] = room
        texts[4] = student_no
        texts[5] = "\u0e14.\u0e0a."
        texts[6] = first_name
        texts[7] = last_name
        self.cells = [FakeCell(text) for text in texts]

    def get_attribute(self, name: str) -> str | None:
        return self.row_id if name == "id" else None

    def locator(self, selector: str) -> FakeListLocator:
        if selector == "td":
            return FakeListLocator(self.cells)
        if selector == "select[name$='.studyTypeCode']":
            return FakeListLocator([self.select])
        return FakeListLocator([])


class FakePage:
    def __init__(self, rows: list[FakeRow], *, page_number: int = 1) -> None:
        self.rows = rows
        self.url = f"https://portal.example.test/add?page.page={page_number}"
        self.waits: list[int] = []

    def locator(self, selector: str) -> FakeListLocator:
        if selector == "tr[id^='tr-']":
            return FakeListLocator(self.rows)
        return FakeListLocator([])

    def wait_for_timeout(self, millis: int) -> None:
        self.waits.append(millis)


def _student(
    *,
    order: int = 1,
    level_label: str = M6,
    room: int | None = 1,
    student_no: str = "1001",
    first_name: str = "\u0e2a\u0e21\u0e0a\u0e32\u0e22",
    last_name: str = "\u0e43\u0e08\u0e14\u0e35",
    status_code: str = "317",
) -> legacy.SourceStudent:
    return legacy.SourceStudent(
        order=order,
        level_label=level_label,
        room=room,
        student_no=student_no,
        first_name=first_name,
        last_name=last_name,
        status_text="\u0e23\u0e31\u0e1a\u0e08\u0e49\u0e32\u0e07\u0e17\u0e31\u0e48\u0e27\u0e44\u0e1b",
        status_code=status_code,
    )


def test_resolve_status_code_accepts_prefixed_and_unprefixed_text() -> None:
    prefixed = next(key for key, value in legacy.STATUS_CODE_MAP.items() if value == "317")
    unprefixed = prefixed.split(") ", 1)[1]

    assert legacy.resolve_status_code(M6, prefixed) == "317"
    assert legacy.resolve_status_code(M6, unprefixed) == "317"
    assert legacy.resolve_status_code(M6, "\u0e2a\u0e16\u0e32\u0e19\u0e30\u0e44\u0e21\u0e48\u0e23\u0e39\u0e49\u0e08\u0e31\u0e01") == ""


def test_load_source_data_detects_level_and_skips_blank_names(monkeypatch: pytest.MonkeyPatch) -> None:
    status_text = next(key for key, value in legacy.STATUS_CODE_MAP.items() if value == "317")
    dataframe = pd.DataFrame(
        [
            [1, M6, 1, "1001", "\u0e2a\u0e21\u0e0a\u0e32\u0e22", "\u0e43\u0e08\u0e14\u0e35", status_text],
            [2, M6, 1, "1002", "", "\u0e43\u0e08\u0e14\u0e35", status_text],
        ]
    )
    monkeypatch.setattr(legacy.pd, "read_excel", lambda *args, **kwargs: dataframe)

    students, detected_level = legacy.load_source_data(Path("ignored.xlsx"))

    assert detected_level == M6
    assert len(students) == 1
    assert students[0].status_code == "317"
    assert students[0].student_no == "1001"


def test_load_source_data_rejects_missing_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(legacy.pd, "read_excel", lambda *args, **kwargs: pd.DataFrame([[1, M6]]))

    with pytest.raises(ValueError, match="expected 7 columns"):
        legacy.load_source_data(Path("bad.xlsx"))


def test_choose_best_match_prefers_exact_student_number() -> None:
    portal_row = {
        "student_no": "1002",
        "room": 2,
        "normalized_first_name": legacy.normalize_name("\u0e2a\u0e21\u0e0a\u0e32\u0e22"),
        "normalized_last_name": legacy.normalize_name("\u0e43\u0e08\u0e14\u0e35"),
        "normalized_full_name": legacy.normalize_name("\u0e2a\u0e21\u0e0a\u0e32\u0e22 \u0e43\u0e08\u0e14\u0e35"),
        "normalized_joined_name": legacy.normalize_name("\u0e2a\u0e21\u0e0a\u0e32\u0e22\u0e43\u0e08\u0e14\u0e35"),
    }
    students = [
        _student(order=1, student_no="1001", room=2),
        _student(order=2, student_no="1002", room=9, first_name="\u0e2a\u0e21\u0e0a\u0e31\u0e22"),
    ]

    student, score = legacy.choose_best_match(portal_row, students, used_orders=set())

    assert student is students[1]
    assert score == 100


def test_fill_current_page_dry_run_does_not_select_option() -> None:
    row = FakeRow(
        row_id="tr-1",
        seq_no="1",
        room="1",
        student_no="1001",
        first_name="\u0e2a\u0e21\u0e0a\u0e32\u0e22",
        last_name="\u0e43\u0e08\u0e14\u0e35",
        option_values={"317"},
    )
    page = FakePage([row])

    results, stopped_item = legacy.fill_current_page(
        page,
        students=[_student()],
        used_orders=set(),
        min_score=72,
        dry_run=True,
        stop_on_review=False,
        level_label=M6,
    )

    assert stopped_item is None
    assert results[0]["note"] == "dry_run"
    assert results[0]["applied"] is False
    assert row.select.selected == []


def test_fill_current_page_uses_m3_default_when_exact_student_number_missing() -> None:
    row = FakeRow(
        row_id="tr-1",
        seq_no="1",
        room="1",
        student_no="9999",
        first_name="\u0e44\u0e21\u0e48\u0e1e\u0e1a",
        last_name="\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25",
        option_values={"207"},
    )
    page = FakePage([row])

    results, stopped_item = legacy.fill_current_page(
        page,
        students=[_student(level_label=M3, student_no="1001", status_code="201")],
        used_orders=set(),
        min_score=72,
        dry_run=False,
        stop_on_review=False,
        level_label=M3,
    )

    assert stopped_item is None
    assert results[0]["note"] == "default_missing_filled"
    assert results[0]["matched_status_code"] == "207"
    assert row.select.selected == ["207"]


def test_fill_current_page_stops_on_unmapped_status_without_selecting() -> None:
    row = FakeRow(
        row_id="tr-1",
        seq_no="1",
        room="1",
        student_no="1001",
        first_name="\u0e2a\u0e21\u0e0a\u0e32\u0e22",
        last_name="\u0e43\u0e08\u0e14\u0e35",
        option_values={"317"},
    )
    page = FakePage([row])

    results, stopped_item = legacy.fill_current_page(
        page,
        students=[_student(status_code="")],
        used_orders=set(),
        min_score=72,
        dry_run=False,
        stop_on_review=True,
        level_label=M6,
    )

    assert results[0]["note"] == "status_code_not_mapped"
    assert stopped_item == results[0]
    assert row.select.selected == []


def test_fill_current_page_marks_missing_dropdown_option_for_review() -> None:
    row = FakeRow(
        row_id="tr-1",
        seq_no="1",
        room="1",
        student_no="1001",
        first_name="\u0e2a\u0e21\u0e0a\u0e32\u0e22",
        last_name="\u0e43\u0e08\u0e14\u0e35",
        option_values={"301"},
    )
    page = FakePage([row])

    results, stopped_item = legacy.fill_current_page(
        page,
        students=[_student(status_code="317")],
        used_orders=set(),
        min_score=72,
        dry_run=False,
        stop_on_review=True,
        level_label=M6,
    )

    assert results[0]["note"] == "option_value_not_found"
    assert stopped_item == results[0]
    assert row.select.selected == []
