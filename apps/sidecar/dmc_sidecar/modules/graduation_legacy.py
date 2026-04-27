from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeAlias
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
from playwright.sync_api import Error, Locator, Page, TimeoutError, sync_playwright
from rapidfuzz import fuzz


LevelRule: TypeAlias = dict[str, str | int | bool | None]
RowInfo: TypeAlias = dict[str, Any]
FillResult: TypeAlias = dict[str, Any]


TARGET_URL_TEMPLATE = (
    "https://portal.bopp-obec.info/obec68/studentpendingupl/add"
    "?schoolCode=81012017&studentNo=&cifNo=&cifType=&educationYear=2568"
    "&levelDtlCode={level_code}&classroom=&firstNameTh=&lastNameTh=&action=search"
)
LOGIN_URL = "https://portal.bopp-obec.info/obec68/auth/login"

DATA_GLOB = "*-obec-study-form.xlsx"
STANDARD_FINAL_FILE = "m6-obec-study-form.xlsx"
PROFILE_DIR = Path(".playwright-obec-profile")
REPORT_JSON = Path("obec-fill-report.json")
REPORT_CSV = Path("obec-fill-report.csv")
REVIEW_CSV = Path("obec-fill-review.csv")

LEVEL_RULES: dict[str, LevelRule] = {
    "ม.3": {
        "level_code": "12",
        "default_missing_code": "207",
        "ambiguity_floor": 45,
        "require_exact_student_no": True,
    },
    "ม.6": {
        "level_code": "15",
        "default_missing_code": None,
        "ambiguity_floor": None,
        "require_exact_student_no": False,
    },
}

STATUS_CODE_MAP: dict[str, str] = {
    "(ม.3) ศึกษาต่อ ม.4 โรงเรียนเดิม": "201",
    "(ม.3) ศึกษาต่อ ม.4 โรงเรียนอื่น ในจังหวัดเดิม": "202",
    "(ม.3) ศึกษาต่อ ม.4 โรงเรียนอื่น ในต่างจังหวัด": "203",
    "(ม.3) ศึกษาต่อ ม.4 โรงเรียนอื่น ใน กทม.": "204",
    "(ม.3) สถาบันอาชีวศึกษาของรัฐบาล": "205",
    "(ม.3) สถาบันอาชีวศึกษาของเอกชน": "206",
    "(ม.3) ศึกษาต่อสถาบันอื่น ๆ": "207",
    "(ม.3) ไม่ศึกษาต่อ ทำงานภาคอุตสาหกรรม": "208",
    "(ม.3) ไม่ศึกษาต่อ ทำงานภาคการเกษตร": "209",
    "(ม.3) ไม่ศึกษาต่อ ทำงานการประมง": "210",
    "(ม.3) ไม่ศึกษาต่อ ทำงานค้าขาย ธุรกิจ": "211",
    "(ม.3) ไม่ศึกษาต่อ ทำงานบริการ": "212",
    "(ม.3) ไม่ศึกษาต่อ ทำงานรับจ้างทั่วไป": "213",
    "(ม.3) ไม่ศึกษาต่อ ทำงานอื่น ๆ": "214",
    "(ม.3) บวชในศาสนา": "215",
    "(ม.3) ไม่ประกอบอาชีพและไม่ศึกษาต่อ": "216",
    "(ม.3) ศึกษาต่อต่างประเทศ": "217",
    "(ม.6) ศึกษาต่อมหาวิทยาลัยของรัฐ": "301",
    "(ม.6) ศึกษาต่อมหาวิทยาลัยเปิดของรัฐ": "302",
    "(ม.6) ศึกษาต่อมหาวิทยาลัยของเอกชน": "303",
    "(ม.6) ศึกษาต่อสถาบันอาชีวศึกษาของรัฐบาล": "304",
    "(ม.6) ศึกษาต่อสถาบันอาชีวศึกษาของเอกชน": "305",
    "(ม.6) ศึกษาต่อสถาบันพยาบาล": "306",
    "(ม.6) ศึกษาต่อสถาบันทหาร": "307",
    "(ม.6) ศึกษาต่อสถาบันตำรวจ": "308",
    "(ม.6) ศึกษาต่อสถาบันอื่น ๆ": "309",
    "(ม.6) ไม่ศึกษาต่อ รับราชการ": "310",
    "(ม.6) ไม่ศึกษาต่อ ทำงานรัฐวิสาหกิจ": "311",
    "(ม.6) ไม่ศึกษาต่อ ภาคอุตสาหกรรม": "312",
    "(ม.6) ไม่ศึกษาต่อ ภาคการเกษตร": "313",
    "(ม.6) ไม่ศึกษาต่อ การประมง": "314",
    "(ม.6) ไม่ศึกษาต่อ ค้าขาย ธุรกิจ": "315",
    "(ม.6) ไม่ศึกษาต่อ งานบริการ": "316",
    "(ม.6) ไม่ศึกษาต่อ รับจ้างทั่วไป": "317",
    "(ม.6) ไม่ศึกษาต่อ บวชในศาสนา": "318",
    "(ม.6) ไม่ประกอบอาชีพและไม่ศึกษาต่อ": "309",
    "(ม.6) ศึกษาต่อต่างประเทศ": "320",
    "ไม่ประกอบอาชีพและไม่ศึกษาต่อ": "309",
    "ไม่มีประกอบอาชีพและไม่ศึกษาต่อ": "309",
}


@dataclass
class SourceStudent:
    order: int
    level_label: str
    room: int | None
    student_no: str
    first_name: str
    last_name: str
    status_text: str
    status_code: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def normalized_first_name(self) -> str:
        return normalize_name(self.first_name)

    @property
    def normalized_last_name(self) -> str:
        return normalize_name(self.last_name)

    @property
    def normalized_full_name(self) -> str:
        return normalize_name(self.full_name)


def normalize_text(text: str) -> str:
    text = (text or "").strip()
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", "", text)


def normalize_digits(text: str) -> str:
    return re.sub(r"\D+", "", text or "")


def normalize_name(text: str) -> str:
    text = normalize_text(text)
    thai_mark_translation: dict[str, str | int | None] = {
        "\u0E4D": "",
        "\u0E4C": "",
        "\u0E47": "",
        "\u0E31": "",
        "\u0E34": "",
        "\u0E35": "",
        "\u0E36": "",
        "\u0E37": "",
        "\u0E38": "",
        "\u0E39": "",
        "\u0E48": "",
        "\u0E49": "",
        "\u0E4A": "",
        "\u0E4B": "",
    }
    text = text.translate(
        str.maketrans(thai_mark_translation)
    )
    return text


def similarity(a: str, b: str) -> int:
    if not a or not b:
        return 0
    return max(
        int(fuzz.ratio(a, b)),
        int(fuzz.partial_ratio(a, b)),
        int(fuzz.token_sort_ratio(a, b)),
    )


def build_target_url(level_code: str) -> str:
    return TARGET_URL_TEMPLATE.format(level_code=level_code)


def resolve_status_code(level_label: str, status_text: str) -> str:
    status_text = (status_text or "").strip()
    if not status_text:
        return ""

    direct = STATUS_CODE_MAP.get(status_text)
    if direct:
        return direct

    if not status_text.startswith("("):
        prefixed = STATUS_CODE_MAP.get(f"({level_label}) {status_text}")
        if prefixed:
            return prefixed

    return ""


def resolve_single_input_file(
    explicit_path: str | None,
    standard_filename: str,
    glob_pattern: str,
) -> Path | None:
    if explicit_path:
        path = Path(explicit_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"input file not found: {path}")
        return path

    standard_path = Path(standard_filename).resolve()
    if standard_path.exists():
        return standard_path

    data_files = sorted(Path(".").glob(glob_pattern))
    if not data_files:
        return None
    if len(data_files) > 1:
        raise ValueError(
            f"multiple files match {glob_pattern}; specify the file explicitly"
        )
    return data_files[0].resolve()


def load_source_data(final_file: Path) -> tuple[list[SourceStudent], str]:
    df = pd.read_excel(final_file, dtype=str).fillna("")
    if len(df.columns) < 7:
        raise ValueError("form file does not have the expected 7 columns")

    students: list[SourceStudent] = []
    detected_level = ""

    for row in df.itertuples(index=False):
        order_text = str(row[0]).strip()
        level_label = str(row[1]).strip()
        room_text = str(row[2]).strip()
        student_no = normalize_digits(str(row[3]))
        first_name = str(row[4]).strip()
        last_name = str(row[5]).strip()
        status_text = str(row[6]).strip()

        if not level_label or level_label not in LEVEL_RULES:
            continue

        if not detected_level:
            detected_level = level_label

        if not first_name:
            continue

        students.append(
            SourceStudent(
                order=int(order_text or "0"),
                level_label=level_label,
                room=int(float(room_text)) if room_text else None,
                student_no=student_no,
                first_name=first_name,
                last_name=last_name,
                status_text=status_text,
                status_code=resolve_status_code(level_label, status_text),
            )
        )

    if not detected_level:
        raise ValueError("could not detect level from the form file")
    if detected_level not in LEVEL_RULES:
        raise ValueError(f"unsupported level in form file: {detected_level}")

    return students, detected_level


def wait_for_user_ready(level_label: str) -> None:
    print("")
    print("Browser opened.")
    print("1. Login at the DMC login page.")
    print(f"2. After login, return here and press Enter. The script will open the {level_label} target page for you.")
    print("3. By default the script will jump to page 1 before processing.")
    input("Press Enter after login is complete: ")


def wait_for_student_table(page: Page) -> None:
    page.wait_for_selector("tr[id^='tr-']", timeout=60000)


def open_target_page_after_login(page: Page, target_url: str) -> None:
    last_error: Error | None = None

    for _ in range(4):
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except TimeoutError:
            pass

        page.wait_for_timeout(1500)

        try:
            page.goto(target_url, wait_until="domcontentloaded", timeout=90000)
            return
        except Error as exc:
            last_error = exc
            if "interrupted by another navigation" not in str(exc):
                raise

    if last_error is not None:
        raise last_error


def get_current_page_number(page: Page) -> int:
    active = page.locator("div.pagination li.active a")
    if active.count():
        text = active.first.inner_text().strip()
        if text.isdigit():
            return int(text)

    parsed = urlparse(page.url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    page_value = params.get("page.page", "").strip()
    if page_value.isdigit():
        return int(page_value)
    return 1


def get_total_pages(page: Page) -> int:
    links = page.locator("div.pagination li a")
    max_page = 1
    for idx in range(links.count()):
        text = links.nth(idx).inner_text().strip()
        if text.isdigit():
            max_page = max(max_page, int(text))
    return max_page


def set_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params[key] = value
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def get_page_url(base_url: str, page_number: int) -> str:
    return set_query_param(base_url, "page.page", str(page_number))


def find_row_select(row: Locator) -> Locator:
    return row.locator("select[name$='.studyTypeCode']").first


def extract_row_info(row: Locator) -> RowInfo | None:
    row_id = row.get_attribute("id") or ""
    cells = row.locator("td")
    if not row_id.startswith("tr-") or cells.count() < 11:
        return None

    select = find_row_select(row)
    if select.count() == 0:
        return None

    cell_texts = [cells.nth(idx).inner_text().strip() for idx in range(cells.count())]
    index_digits = re.findall(r"\d+", row_id)
    if not index_digits:
        return None

    room_digits = re.findall(r"\d+", cell_texts[3])
    return {
        "row_id": row_id,
        "row_index": int(index_digits[0]),
        "seq_no": cell_texts[1],
        "room": int(room_digits[0]) if room_digits else None,
        "student_no": normalize_digits(cell_texts[4]),
        "title": cell_texts[5],
        "first_name": cell_texts[6],
        "last_name": cell_texts[7],
        "full_name": f"{cell_texts[6]} {cell_texts[7]}".strip(),
        "normalized_first_name": normalize_name(cell_texts[6]),
        "normalized_last_name": normalize_name(cell_texts[7]),
        "normalized_full_name": normalize_name(f"{cell_texts[6]} {cell_texts[7]}"),
        "normalized_joined_name": normalize_name(f"{cell_texts[6]}{cell_texts[7]}"),
        "select": select,
    }


def score_match(row_info: RowInfo, student: SourceStudent) -> int:
    room_bonus = 0
    if (
        student.room is not None
        and row_info["room"] is not None
        and student.room == row_info["room"]
    ):
        room_bonus = 8

    first_score = similarity(
        row_info["normalized_first_name"], student.normalized_first_name
    )
    last_score = similarity(
        row_info["normalized_last_name"], student.normalized_last_name
    )
    full_score = similarity(
        row_info["normalized_full_name"], student.normalized_full_name
    )
    joined_score = similarity(
        row_info["normalized_joined_name"], student.normalized_full_name
    )

    best_name_score = max(full_score, joined_score)
    if student.normalized_last_name:
        split_score = int(last_score * 0.45 + first_score * 0.35 + best_name_score * 0.20)
        return min(100, split_score + room_bonus)

    return min(100, best_name_score + room_bonus)


def choose_best_match(
    row_info: RowInfo,
    students: list[SourceStudent],
    used_orders: set[int],
) -> tuple[SourceStudent | None, int]:
    remaining = [student for student in students if student.order not in used_orders]
    if not remaining:
        return None, 0

    if row_info["student_no"]:
        exact = [
            student for student in remaining if student.student_no == row_info["student_no"]
        ]
        if len(exact) == 1:
            return exact[0], 100
        if len(exact) > 1:
            scored_exact = [(score_match(row_info, student), student) for student in exact]
            scored_exact.sort(key=lambda item: item[0], reverse=True)
            return scored_exact[0][1], 100

    candidates = remaining
    if row_info["room"] is not None:
        same_room = [
            student
            for student in remaining
            if student.room is not None and student.room == row_info["room"]
        ]
        if same_room:
            candidates = same_room

    scored = [(score_match(row_info, student), student) for student in candidates]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1], scored[0][0]


def option_exists(select_locator: Locator, value: str) -> bool:
    return bool(select_locator.locator(f"option[value='{value}']").count() > 0)


def needs_review(note: str) -> bool:
    return str(note).startswith("low_confidence") or note in {
        "no_match",
        "status_code_not_mapped",
        "option_value_not_found",
    }


def fill_current_page(
    page: Page,
    students: list[SourceStudent],
    used_orders: set[int],
    min_score: int,
    dry_run: bool,
    stop_on_review: bool,
    level_label: str,
    before_row: Callable[[], None] | None = None,
    after_row: Callable[[FillResult], None] | None = None,
) -> tuple[list[FillResult], FillResult | None]:
    rows = page.locator("tr[id^='tr-']")
    page_number = get_current_page_number(page)
    results: list[FillResult] = []
    stop_item: FillResult | None = None
    rules = LEVEL_RULES[level_label]
    default_missing_code = rules["default_missing_code"]
    require_exact_student_no = bool(rules["require_exact_student_no"])
    ambiguity_floor_value = rules["ambiguity_floor"]
    ambiguity_floor = ambiguity_floor_value if isinstance(ambiguity_floor_value, int) else None

    for idx in range(rows.count()):
        row = rows.nth(idx)
        row_info = extract_row_info(row)
        if not row_info:
            continue
        if before_row is not None:
            # Hook after row extraction so progress/cancel checks only apply to usable rows.
            before_row()

        if require_exact_student_no and row_info["student_no"]:
            exact_student = next(
                (
                    item
                    for item in students
                    if item.order not in used_orders
                    and item.student_no == row_info["student_no"]
                ),
                None,
            )
            if exact_student is None:
                result: FillResult = {
                    "page": page_number,
                    "level": level_label,
                    "portal_row_index": row_info["row_index"],
                    "portal_seq_no": row_info["seq_no"],
                    "portal_student_no": row_info["student_no"],
                    "portal_room": row_info["room"],
                    "portal_name": row_info["full_name"],
                    "matched_order": None,
                    "matched_room": None,
                    "matched_student_no": None,
                    "matched_name": None,
                    "matched_status_text": None,
                    "matched_status_code": default_missing_code,
                    "score": 0,
                    "applied": False,
                    "note": "",
                }
                if not dry_run:
                    if isinstance(default_missing_code, str):
                        row_info["select"].select_option(value=default_missing_code)
                    page.wait_for_timeout(80)
                result["applied"] = not dry_run
                result["note"] = "default_missing_dry_run" if dry_run else "default_missing_filled"
                results.append(result)
                if after_row is not None:
                    after_row(result)
                continue

        student, score = choose_best_match(row_info, students, used_orders)
        result = {
            "page": page_number,
            "level": level_label,
            "portal_row_index": row_info["row_index"],
            "portal_seq_no": row_info["seq_no"],
            "portal_student_no": row_info["student_no"],
            "portal_room": row_info["room"],
            "portal_name": row_info["full_name"],
            "matched_order": student.order if student else None,
            "matched_room": student.room if student else None,
            "matched_student_no": student.student_no if student else None,
            "matched_name": student.full_name if student else None,
            "matched_status_text": student.status_text if student else None,
            "matched_status_code": student.status_code if student else None,
            "score": score,
            "applied": False,
            "note": "",
        }

        if not student:
            if isinstance(default_missing_code, str) and default_missing_code:
                if not dry_run:
                    row_info["select"].select_option(value=default_missing_code)
                    page.wait_for_timeout(80)
                result["matched_status_code"] = default_missing_code
                result["applied"] = not dry_run
                result["note"] = "default_missing_dry_run" if dry_run else "default_missing_filled"
                results.append(result)
                if after_row is not None:
                    after_row(result)
                continue

            result["note"] = "no_match"
            results.append(result)
            if after_row is not None:
                after_row(result)
            if stop_on_review:
                stop_item = result
                break
            continue

        if score < min_score:
            if (
                isinstance(default_missing_code, str)
                and default_missing_code
                and ambiguity_floor is not None
                and score < ambiguity_floor
            ):
                if not dry_run:
                    row_info["select"].select_option(value=default_missing_code)
                    page.wait_for_timeout(80)
                result["matched_status_code"] = default_missing_code
                result["applied"] = not dry_run
                result["note"] = "default_missing_dry_run" if dry_run else "default_missing_filled"
                results.append(result)
                if after_row is not None:
                    after_row(result)
                continue

            result["note"] = f"low_confidence_below_{min_score}"
            results.append(result)
            if after_row is not None:
                after_row(result)
            if stop_on_review:
                stop_item = result
                break
            continue

        if not student.status_code:
            result["note"] = "status_code_not_mapped"
            results.append(result)
            if after_row is not None:
                after_row(result)
            if stop_on_review:
                stop_item = result
                break
            continue

        if not option_exists(row_info["select"], student.status_code):
            result["note"] = "option_value_not_found"
            results.append(result)
            if after_row is not None:
                after_row(result)
            if stop_on_review:
                stop_item = result
                break
            continue

        if not dry_run:
            row_info["select"].select_option(value=student.status_code)
            page.wait_for_timeout(80)

        used_orders.add(student.order)
        result["applied"] = not dry_run
        result["note"] = "dry_run" if dry_run else "filled"
        results.append(result)
        if after_row is not None:
            after_row(result)

    return results, stop_item


def save_current_page(page: Page) -> None:
    save_button = page.locator(
        "form.form-horizontal.form-condensed button[name='action'][value='confirm']"
    ).first
    if save_button.count() == 0:
        raise RuntimeError("save button not found")

    try:
        with page.expect_navigation(wait_until="domcontentloaded", timeout=60000):
            save_button.click()
    except TimeoutError:
        page.wait_for_load_state("domcontentloaded", timeout=60000)

    page.wait_for_timeout(1200)


def goto_page_number(page: Page, page_number: int, base_url: str) -> None:
    page.goto(get_page_url(base_url, page_number), wait_until="domcontentloaded", timeout=90000)
    wait_for_student_table(page)
    page.wait_for_timeout(500)


def print_summary(results: list[FillResult], min_score: int) -> None:
    total_rows = len(results)
    filled = sum(1 for item in results if item["note"] == "filled")
    dry_run_rows = sum(1 for item in results if item["note"] == "dry_run")
    default_missing = sum(
        1
        for item in results
        if item["note"] in {"default_missing_dry_run", "default_missing_filled"}
    )
    low_conf = [item for item in results if item["note"].startswith("low_confidence")]
    no_match = [item for item in results if item["note"] == "no_match"]
    unmapped = [item for item in results if item["note"] == "status_code_not_mapped"]
    option_missing = [item for item in results if item["note"] == "option_value_not_found"]

    print("")
    print(f"rows seen: {total_rows}")
    print(f"filled: {filled}")
    print(f"dry-run matched: {dry_run_rows}")
    print(f"default missing applied: {default_missing}")
    print(f"low confidence (< {min_score}): {len(low_conf)}")
    print(f"no match: {len(no_match)}")
    print(f"status code not mapped: {len(unmapped)}")
    print(f"option value not found: {len(option_missing)}")

    review_items = low_conf[:15] + no_match[:15] + unmapped[:15] + option_missing[:15]
    if review_items:
        print("")
        print("items to review:")
        for item in review_items:
            print(
                f"- page {item['page']} row {item['portal_seq_no']}"
                f" | room {item['portal_room']}"
                f" | student_no {item['portal_student_no']}"
                f" | portal={item['portal_name']}"
                f" | matched={item['matched_name']}"
                f" | note={item['note']}"
                f" | score={item['score']}"
            )


def save_reports(
    results: list[FillResult],
    report_json: Path | None = None,
    report_csv: Path | None = None,
    review_csv: Path | None = None,
) -> tuple[Path, Path, Path]:
    report_json = report_json or REPORT_JSON
    report_csv = report_csv or REPORT_CSV
    review_csv = review_csv or REVIEW_CSV

    report_json.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    df = pd.DataFrame(results)
    df.to_csv(report_csv, index=False, encoding="utf-8-sig")

    review_mask = df["note"].astype(str).apply(needs_review)
    df.loc[review_mask].to_csv(review_csv, index=False, encoding="utf-8-sig")
    return report_json.resolve(), report_csv.resolve(), review_csv.resolve()


def run(
    page: Page,
    students: list[SourceStudent],
    min_score: int,
    dry_run: bool,
    resume_current: bool,
    stop_on_review: bool,
    level_label: str,
    base_url: str,
    ) -> tuple[list[FillResult], FillResult | None]:
    wait_for_student_table(page)
    if not resume_current:
        print("navigating to page 1 ...")
        goto_page_number(page, 1, base_url)

    start_page = get_current_page_number(page)
    total_pages = get_total_pages(page)
    used_orders: set[int] = set()
    all_results: list[FillResult] = []
    stopped_item: FillResult | None = None

    print(f"start page: {start_page}")
    print(f"total pages: {total_pages}")

    current_page = start_page
    while True:
        wait_for_student_table(page)
        print(f"processing page {current_page}/{total_pages} ...")
        page_results, stop_item = fill_current_page(
            page,
            students,
            used_orders,
            min_score,
            dry_run,
            stop_on_review,
            level_label,
        )
        all_results.extend(page_results)

        page_filled = sum(
            1
            for item in page_results
            if item["note"] in {
                "filled",
                "dry_run",
                "default_missing_dry_run",
                "default_missing_filled",
            }
        )
        page_low = sum(
            1 for item in page_results if str(item["note"]).startswith("low_confidence")
        )
        page_review = sum(1 for item in page_results if needs_review(item["note"]))
        print(
            f"page {current_page}: matched={page_filled}"
            f" low_conf={page_low}"
            f" missing={page_review}"
        )

        if stop_item is not None:
            stopped_item = stop_item
            print(
                f"stopping on review item at page {stop_item['page']}"
                f" row {stop_item['portal_seq_no']}"
                f" | portal={stop_item['portal_name']}"
                f" | note={stop_item['note']}"
                f" | score={stop_item['score']}"
            )
            break

        if not dry_run:
            print(f"saving page {current_page} ...")
            save_current_page(page)

        if current_page >= total_pages:
            break

        current_page += 1
        print(f"moving to page {current_page} ...")
        goto_page_number(page, current_page, base_url)

    return all_results, stopped_item


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fill 'ศึกษาต่อหรือไม่' for every page in DMC, save each page,"
            " and move to the next page automatically."
        )
    )
    parser.add_argument(
        "--final-file",
        help=f"path to the form xlsx file used for statuses (default: .\\{STANDARD_FINAL_FILE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="match and navigate through pages without changing dropdowns or saving",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=72,
        help="minimum fuzzy-match score required before a row is filled",
    )
    parser.add_argument(
        "--resume-current",
        action="store_true",
        help="resume from the currently open page instead of forcing page 1",
    )
    parser.add_argument(
        "--stop-on-review",
        action="store_true",
        help="stop immediately when a row needs manual review and do not save that page",
    )
    args = parser.parse_args()

    final_file = resolve_single_input_file(
        args.final_file,
        STANDARD_FINAL_FILE,
        DATA_GLOB,
    )
    if final_file is None:
        raise FileNotFoundError(
            f"missing input file; expected .\\{STANDARD_FINAL_FILE} or one file matching {DATA_GLOB}"
        )

    print(f"final file: {final_file}")
    students, level_label = load_source_data(final_file)
    level_rules = LEVEL_RULES[level_label]
    base_url = build_target_url(str(level_rules["level_code"]))
    PROFILE_DIR.mkdir(exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR.resolve()),
            headless=False,
            viewport={"width": 1600, "height": 1000},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=90000)
            wait_for_user_ready(level_label)
            open_target_page_after_login(page, base_url)
            page.wait_for_timeout(1200)
            results, stopped_item = run(
                page,
                students,
                args.min_score,
                args.dry_run,
                args.resume_current,
                args.stop_on_review,
                level_label,
                base_url,
            )
            json_path, csv_path, review_csv_path = save_reports(results)
            print_summary(results, args.min_score)
            print("")
            print(f"report saved: {json_path}")
            print(f"csv saved: {csv_path}")
            print(f"review csv saved: {review_csv_path}")
            if stopped_item is not None:
                print(
                    "stopped on review item. current page was not saved."
                    " check the review csv before continuing."
                )
            elif args.dry_run:
                print("dry-run completed. nothing was submitted.")
            else:
                print("completed. every processed page was submitted automatically.")
            input("Press Enter to close the browser...")
        except KeyboardInterrupt:
            print("cancelled by user")
            return 1
        except Error as exc:
            print(f"playwright error: {exc}")
            input("Press Enter to close the browser...")
            return 1
        finally:
            context.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
