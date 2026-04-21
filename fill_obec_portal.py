from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd
from playwright.sync_api import Error, TimeoutError, sync_playwright
from rapidfuzz import fuzz


TARGET_URL = (
    "https://portal.bopp-obec.info/obec68/studentpendingupl/add"
    "?schoolCode=81012017&studentNo=&cifNo=&cifType=&educationYear=2568"
    "&levelDtlCode=15&classroom=&firstNameTh=&lastNameTh=&action=search"
)

DATA_GLOB = "*-final.xlsx"
STANDARD_FINAL_FILE = "obec-study-form.xlsx"
PROFILE_DIR = Path(".playwright-obec-profile")
REPORT_JSON = Path("obec-fill-report.json")
REPORT_CSV = Path("obec-fill-report.csv")
REVIEW_CSV = Path("obec-fill-review.csv")

STATUS_CODE_MAP = {
    "ศึกษาต่อมหาวิทยาลัยของรัฐ": "301",
    "ศึกษาต่อมหาวิทยาลัยเปิดของรัฐ": "302",
    "ศึกษาต่อมหาวิทยาลัยของเอกชน": "303",
    "ศึกษาต่อสถาบันอาชีวศึกษาของรัฐบาล": "304",
    "ศึกษาต่อสถาบันอาชีวศึกษาของเอกชน": "305",
    "ศึกษาต่อสถาบันพยาบาล": "306",
    "ศึกษาต่อสถาบันทหาร": "307",
    "ศึกษาต่อสถาบันตำรวจ": "308",
    "ศึกษาต่อสถาบันอื่น ๆ": "309",
    "ไม่ศึกษาต่อ รับราชการ": "310",
    "ไม่ศึกษาต่อ ทำงานรัฐวิสาหกิจ": "311",
    "ไม่ศึกษาต่อ ทำนาบุรีสุราสินค้า": "311",
    "ไม่ศึกษาต่อ ภาคอุตสาหกรรม": "312",
    "ไม่ศึกษาต่อ ภาคการเกษตร": "313",
    "ไม่ศึกษาต่อ การประมง": "314",
    "ไม่ศึกษาต่อ ค้าขาย ธุรกิจ": "315",
    "ไม่ศึกษาต่อ งานบริการ": "316",
    "ไม่ศึกษาต่อ รับจ้างทั่วไป": "317",
    "ไม่ศึกษาต่อ บวชในศาสนา": "318",
    "ไม่มีประกอบอาชีพและไม่ศึกษาต่อ": "309",
    "ไม่ประกอบอาชีพและไม่ศึกษาต่อ": "309",
    "ศึกษาต่อต่างประเทศ": "320",
}


@dataclass
class SourceStudent:
    order: int
    room: int
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
    text = re.sub(r"\s+", "", text)
    return text


def normalize_name(text: str) -> str:
    text = normalize_text(text)
    text = text.translate(
        str.maketrans(
            {
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
                "\u0E11": "\u0E17",
                "\u0E24": "\u0E23",
            }
        )
    )
    return text


def similarity(a: str, b: str) -> int:
    if not a or not b:
        return 0
    return max(
        fuzz.ratio(a, b),
        fuzz.partial_ratio(a, b),
        fuzz.token_sort_ratio(a, b),
    )


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


def load_source_data(final_file: Path) -> list[SourceStudent]:
    df = pd.read_excel(final_file, dtype=str).fillna("")
    if len(df.columns) < 7:
        raise ValueError("final input file does not have the expected 7 columns")

    students: list[SourceStudent] = []
    for row in df.itertuples(index=False):
        order_text = str(row[0]).strip()
        room_text = str(row[2]).strip()
        first_name = str(row[4]).strip()
        last_name = str(row[5]).strip()
        status_text = str(row[6]).strip()

        if not room_text:
            continue

        order = int(order_text or "0")
        status_code = STATUS_CODE_MAP.get(status_text, "")
        students.append(
            SourceStudent(
                order=order,
                room=int(float(room_text)),
                first_name=first_name,
                last_name=last_name,
                status_text=status_text,
                status_code=status_code,
            )
        )

    return students


def wait_for_user_ready(page) -> None:
    print("")
    print("Browser opened.")
    print("1. Login if needed.")
    print("2. Open the DMC page that lists students for 'สอบได้ จบการศึกษา'.")
    print("3. By default the script will jump to page 1 before processing.")
    input("Press Enter when the page is ready: ")
    page.wait_for_timeout(1200)


def wait_for_student_table(page) -> None:
    page.wait_for_selector("tr[id^='tr-']", timeout=60000)


def get_current_page_number(page) -> int:
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


def get_total_pages(page) -> int:
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


def get_page_url(page_number: int) -> str:
    return set_query_param(TARGET_URL, "page.page", str(page_number))


def find_row_select(row):
    return row.locator("select[name$='.studyTypeCode']").first


def extract_row_info(row) -> dict | None:
    row_id = row.get_attribute("id") or ""
    cells = row.locator("td")
    if not row_id.startswith("tr-") or cells.count() < 11:
        return None

    select = find_row_select(row)
    if select.count() == 0:
        return None

    cell_texts = [cells.nth(idx).inner_text().strip() for idx in range(cells.count())]
    room_digits = re.findall(r"\d+", cell_texts[3])
    index_digits = re.findall(r"\d+", row_id)
    if not room_digits or not index_digits:
        return None

    return {
        "row_id": row_id,
        "row_index": int(index_digits[0]),
        "seq_no": cell_texts[1],
        "room": int(room_digits[0]),
        "student_no": cell_texts[4],
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


def score_match(row_info: dict, student: SourceStudent) -> int:
    room_bonus = 8 if student.room == row_info["room"] else 0
    first_score = similarity(row_info["normalized_first_name"], student.normalized_first_name)
    last_score = similarity(row_info["normalized_last_name"], student.normalized_last_name)
    full_score = similarity(row_info["normalized_full_name"], student.normalized_full_name)
    joined_source_score = similarity(
        row_info["normalized_joined_name"], student.normalized_full_name
    )

    best_name_score = max(full_score, joined_source_score)
    if student.normalized_last_name:
        split_score = int(last_score * 0.45 + first_score * 0.35 + best_name_score * 0.20)
        return min(100, split_score + room_bonus)

    return min(100, int(best_name_score + room_bonus))


def choose_best_match(
    row_info: dict,
    students: Iterable[SourceStudent],
    used_orders: set[int],
) -> tuple[SourceStudent | None, int]:
    remaining = [student for student in students if student.order not in used_orders]
    room_candidates = [student for student in remaining if student.room == row_info["room"]]
    candidates = room_candidates or remaining
    if not candidates:
        return None, 0

    scored = [(score_match(row_info, student), student) for student in candidates]
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1], scored[0][0]


def option_exists(select_locator, value: str) -> bool:
    return select_locator.locator(f"option[value='{value}']").count() > 0


def needs_review(note: str) -> bool:
    return str(note).startswith("low_confidence") or note in {
        "no_match",
        "status_code_not_mapped",
        "option_value_not_found",
    }


def fill_current_page(
    page,
    students: list[SourceStudent],
    used_orders: set[int],
    min_score: int,
    dry_run: bool,
    stop_on_review: bool,
) -> tuple[list[dict], dict | None]:
    rows = page.locator("tr[id^='tr-']")
    page_number = get_current_page_number(page)
    results: list[dict] = []
    stop_item: dict | None = None

    for idx in range(rows.count()):
        row = rows.nth(idx)
        row_info = extract_row_info(row)
        if not row_info:
            continue

        student, score = choose_best_match(row_info, students, used_orders)
        result = {
            "page": page_number,
            "portal_row_index": row_info["row_index"],
            "portal_seq_no": row_info["seq_no"],
            "portal_student_no": row_info["student_no"],
            "portal_room": row_info["room"],
            "portal_name": row_info["full_name"],
            "matched_order": student.order if student else None,
            "matched_room": student.room if student else None,
            "matched_name": student.full_name if student else None,
            "matched_status_text": student.status_text if student else None,
            "matched_status_code": student.status_code if student else None,
            "score": score,
            "applied": False,
            "note": "",
        }

        if not student:
            result["note"] = "no_match"
            results.append(result)
            if stop_on_review:
                stop_item = result
                break
            continue

        if score < min_score:
            result["note"] = f"low_confidence_below_{min_score}"
            results.append(result)
            if stop_on_review:
                stop_item = result
                break
            continue

        if not student.status_code:
            result["note"] = "status_code_not_mapped"
            results.append(result)
            if stop_on_review:
                stop_item = result
                break
            continue

        if not option_exists(row_info["select"], student.status_code):
            result["note"] = "option_value_not_found"
            results.append(result)
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

    return results, stop_item


def save_current_page(page) -> None:
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


def goto_page_number(page, page_number: int) -> None:
    target = get_page_url(page_number)
    page.goto(target, wait_until="domcontentloaded", timeout=90000)
    wait_for_student_table(page)
    page.wait_for_timeout(500)


def print_summary(results: list[dict], min_score: int) -> None:
    total_rows = len(results)
    filled = sum(1 for item in results if item["note"] == "filled")
    dry_run_rows = sum(1 for item in results if item["note"] == "dry_run")
    low_conf = [item for item in results if item["note"].startswith("low_confidence")]
    no_match = [item for item in results if item["note"] == "no_match"]
    unmapped = [item for item in results if item["note"] == "status_code_not_mapped"]
    option_missing = [item for item in results if item["note"] == "option_value_not_found"]

    print("")
    print(f"rows seen: {total_rows}")
    print(f"filled: {filled}")
    print(f"dry-run matched: {dry_run_rows}")
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
                f"- page {item['page']} row {item['portal_seq_no']} "
                f"| room {item['portal_room']} "
                f"| portal={item['portal_name']} "
                f"| matched={item['matched_name']} "
                f"| note={item['note']} "
                f"| score={item['score']}"
            )


def save_reports(results: list[dict]) -> tuple[Path, Path, Path]:
    REPORT_JSON.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    df = pd.DataFrame(results)
    df.to_csv(REPORT_CSV, index=False, encoding="utf-8-sig")

    review_mask = df["note"].astype(str).apply(needs_review)
    df.loc[review_mask].to_csv(REVIEW_CSV, index=False, encoding="utf-8-sig")
    return REPORT_JSON.resolve(), REPORT_CSV.resolve(), REVIEW_CSV.resolve()


def run(
    page,
    students: list[SourceStudent],
    min_score: int,
    dry_run: bool,
    resume_current: bool,
    stop_on_review: bool,
) -> tuple[list[dict], dict | None]:
    wait_for_student_table(page)
    if not resume_current:
        print("navigating to page 1 ...")
        goto_page_number(page, 1)

    start_page = get_current_page_number(page)
    total_pages = get_total_pages(page)
    used_orders: set[int] = set()
    all_results: list[dict] = []
    stopped_item: dict | None = None

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
        )
        all_results.extend(page_results)

        page_filled = sum(1 for item in page_results if item["note"] in {"filled", "dry_run"})
        page_low = sum(
            1 for item in page_results if str(item["note"]).startswith("low_confidence")
        )
        page_missing = sum(1 for item in page_results if needs_review(item["note"]))
        print(
            f"page {current_page}: matched={page_filled} "
            f"low_conf={page_low} missing={page_missing}"
        )

        if stop_item is not None:
            stopped_item = stop_item
            print(
                f"stopping on review item at page {stop_item['page']} "
                f"row {stop_item['portal_seq_no']} | portal={stop_item['portal_name']} "
                f"| note={stop_item['note']} | score={stop_item['score']}"
            )
            break

        if not dry_run:
            print(f"saving page {current_page} ...")
            save_current_page(page)

        if current_page >= total_pages:
            break

        current_page += 1
        print(f"moving to page {current_page} ...")
        goto_page_number(page, current_page)

    return all_results, stopped_item


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fill 'ศึกษาต่อหรือไม่' for every page in DMC, save each page, "
            "and move to the next page automatically."
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

    students = load_source_data(final_file)
    PROFILE_DIR.mkdir(exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR.resolve()),
            headless=False,
            viewport={"width": 1600, "height": 1000},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=90000)
            wait_for_user_ready(page)
            results, stopped_item = run(
                page,
                students,
                args.min_score,
                args.dry_run,
                args.resume_current,
                args.stop_on_review,
            )
            json_path, csv_path, review_csv_path = save_reports(results)
            print_summary(results, args.min_score)
            print("")
            print(f"report saved: {json_path}")
            print(f"csv saved: {csv_path}")
            print(f"review csv saved: {review_csv_path}")
            if stopped_item is not None:
                print(
                    "stopped on review item. current page was not saved. "
                    "check the review csv before continuing."
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
            return 1
        finally:
            context.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
