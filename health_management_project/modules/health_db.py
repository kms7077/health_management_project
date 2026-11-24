"""건강정보 관리 시스템 (단일 파일 과제)

구성
  1) HealthInfo: 한 명의 건강정보 레코드 및 BMI 계산
  2) HealthManager: 식별번호 발급, CRUD, 검색, 통계
  3) load_file / save_file: JSON, CSV, TXT, Pickle 입출력
  4) tui_* / main: 콘솔 입력과 출력만 처리

실행: python health_db.py
다른 코드에서 사용: from health_db import HealthInfo, HealthManager, load_file, save_file
"""

import csv
import json
import math
import pickle
import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path


# ----------------------------------------------------------------------
# 1. 레코드 모델 (한 사람의 건강정보)
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class HealthInfo:
    """한 환자의 정보를 보관합니다. 수정은 HealthManager를 통해 수행합니다."""

    id: str
    name: str
    birth_year: int
    gender: str
    height: float  # cm
    weight: float  # kg

    def __post_init__(self):
        if not isinstance(self.id, str) or not re.fullmatch(r"P\d{4}-\d{4,}", self.id):
            raise ValueError("식별번호는 P2026-0001 형식이어야 합니다.")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("이름을 입력해야 합니다.")
        if not isinstance(self.gender, str) or not self.gender.strip():
            raise ValueError("성별을 입력해야 합니다.")
        if (isinstance(self.birth_year, bool)
                or not isinstance(self.birth_year, int)
                or not (1900 <= self.birth_year <= date.today().year)):
            raise ValueError("생년은 1900년부터 현재 연도 사이여야 합니다.")
        for label, value in (("키", self.height), ("몸무게", self.weight)):
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value <= 0):
                raise ValueError(f"{label}는 0보다 큰 유한한 숫자여야 합니다.")

    @property
    def bmi(self) -> float:
        """BMI를 소수점 둘째 자리까지 계산합니다."""
        return round(self.weight / ((self.height / 100) ** 2), 2)

    @property
    def status(self) -> str:
        """과제용 성인 BMI 판정 기준을 반환합니다."""
        if self.bmi < 18.5:
            return "저체중"
        if self.bmi < 23:
            return "정상"
        if self.bmi < 25:
            return "과체중"
        return "비만"

    def to_dict(self) -> dict:
        """저장할 수 있는 딕셔너리로 변환합니다."""
        return {
            "id": self.id,
            "name": self.name,
            "birth_year": self.birth_year,
            "gender": self.gender,
            "height": self.height,
            "weight": self.weight,
            "bmi": self.bmi,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, row: dict) -> "HealthInfo":
        """파일에서 읽은 딕셔너리를 객체로 변환합니다 (BMI/상태는 재계산)."""
        if not isinstance(row, dict):
            raise ValueError("환자 레코드는 딕셔너리여야 합니다.")
        required = ("id", "name", "birth_year", "gender", "height", "weight")
        if any(field not in row or row[field] is None for field in required):
            raise ValueError("환자 레코드에 필수 항목이 없습니다.")
        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            birth_year=int(row["birth_year"]),
            gender=str(row["gender"]),
            height=float(row["height"]),
            weight=float(row["weight"]),
        )


# ----------------------------------------------------------------------
# 2. 핵심 비즈니스 로직: CRUD와 통계 (입력/출력/파일 접근 금지)
# ----------------------------------------------------------------------
class HealthManager:
    """레코드와 식별번호를 관리합니다. print(), input(), open()을 사용하지 않습니다."""

    def __init__(self):
        self._records: list[HealthInfo] = []
        self._last_numbers: dict[int, int] = {}

    def _remember_id(self, person_id: str) -> None:
        match = re.fullmatch(r"P(\d{4})-(\d{4,})", person_id)
        if match:
            year, number = map(int, match.groups())
            self._last_numbers[year] = max(self._last_numbers.get(year, 0), number)

    def generate_id(self) -> str:
        """현재 연도에 사용 가능한 다음 식별번호를 계산합니다."""
        year = date.today().year
        number = self._last_numbers.get(year, 0) + 1
        while self.find(f"P{year}-{number:04d}") is not None:
            number += 1
        return f"P{year}-{number:04d}"

    def add(self, record: HealthInfo) -> HealthInfo:
        """생성된 레코드를 등록하고 반환합니다."""
        if not isinstance(record, HealthInfo):
            raise TypeError("HealthInfo 객체만 등록할 수 있습니다.")
        if self.find(record.id) is not None:
            raise ValueError(f"이미 등록된 식별번호입니다: {record.id}")
        self._records.append(record)
        self._remember_id(record.id)
        return record

    def add_patient(self, name: str, birth_year: int, gender: str,
                    height: float, weight: float) -> HealthInfo:
        """식별번호를 자동 생성해 환자를 등록합니다 (Create)."""
        record = HealthInfo(self.generate_id(), name, birth_year, gender, height, weight)
        return self.add(record)

    def all(self) -> list[HealthInfo]:
        """등록된 모든 레코드의 목록을 반환합니다 (Read)."""
        return self._records.copy()

    def find(self, person_id: str) -> HealthInfo | None:
        """식별번호가 일치하는 레코드를 반환합니다 (상세조회)."""
        for record in self._records:
            if record.id == person_id:
                return record
        return None

    def search(self, keyword: str) -> list[HealthInfo]:
        """식별번호 또는 이름에 키워드가 포함된 레코드 목록을 반환합니다."""
        keyword = keyword.strip().casefold()
        if not keyword:
            return []
        return [r for r in self._records
                if keyword in r.id.casefold() or keyword in r.name.casefold()]

    def update_patient(self, person_id: str, *, name: str | None = None,
                       birth_year: int | None = None, gender: str | None = None,
                       height: float | None = None,
                       weight: float | None = None) -> HealthInfo | None:
        """기존 객체를 검증된 새 객체로 교체합니다 (Update). ID는 변경하지 않습니다."""
        old = self.find(person_id)
        if old is None:
            return None
        changes = {key: value for key, value in {
            "name": name, "birth_year": birth_year, "gender": gender,
            "height": height, "weight": weight,
        }.items() if value is not None}
        updated = replace(old, **changes)  # 검증이 실패하면 기존 객체는 그대로 남음
        index = self._records.index(old)
        self._records[index] = updated
        return updated

    def remove(self, person_id: str) -> bool:
        """식별번호로 레코드를 삭제합니다 (Delete)."""
        record = self.find(person_id)
        if record is None:
            return False
        self._records.remove(record)
        return True

    def to_dict_list(self) -> list[dict]:
        """파일 저장용 딕셔너리 목록을 반환합니다."""
        return [record.to_dict() for record in self._records]

    def load_rows(self, rows: list[dict]) -> int:
        """파일에서 읽은 목록으로 전체 데이터를 교체합니다. 실패하면 기존 데이터 유지."""
        if not isinstance(rows, list):
            raise ValueError("불러온 데이터는 리스트여야 합니다.")
        temporary = HealthManager()
        for row in rows:
            temporary.add(HealthInfo.from_dict(row))
        # 현재 실행 중 발급했던 일련번호는 유지합니다.
        for year, number in self._last_numbers.items():
            temporary._last_numbers[year] = max(
                temporary._last_numbers.get(year, 0), number
            )
        self._records = temporary._records
        self._last_numbers = temporary._last_numbers
        return len(self._records)

    def statistics(self) -> dict:
        """전체 인원, BMI·키·몸무게 평균, 비만도별 인원/비율을 계산해 반환합니다."""
        count = len(self._records)
        labels = ("저체중", "정상", "과체중", "비만")
        status_counts = {label: 0 for label in labels}
        gender_counts: dict[str, int] = {}
        for record in self._records:
            status_counts[record.status] += 1
            gender_counts[record.gender] = gender_counts.get(record.gender, 0) + 1
        return {
            "count": count,
            "average_bmi": round(sum(r.bmi for r in self._records) / count, 2) if count else None,
            "average_height": round(sum(r.height for r in self._records) / count, 2) if count else None,
            "average_weight": round(sum(r.weight for r in self._records) / count, 2) if count else None,
            "status_counts": status_counts,
            "status_percent": {
                label: round(n / count * 100, 1) if count else 0.0
                for label, n in status_counts.items()
            },
            "gender_counts": gender_counts,
        }


# ----------------------------------------------------------------------
# 3. 모듈 1의 역할: 파일 저장/불러오기 (파일 I/O만 처리)
# ----------------------------------------------------------------------
FIELDS = ("id", "name", "birth_year", "gender", "height", "weight", "bmi", "status")
SUPPORTED_EXTENSIONS = (".json", ".csv", ".txt", ".pkl", ".pickle")
DEFAULT_FILE = Path(__file__).resolve().parent / "health_data.json"


def save_file(filename: str | Path, rows: list[dict]) -> None:
    """딕셔너리 목록을 지정한 확장자의 파일로 저장합니다."""
    path = Path(filename)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("저장 대상은 딕셔너리 리스트여야 합니다.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if ext == ".json":
        with path.open("w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    elif ext in (".csv", ".txt"):
        # TXT는 '|' 구분자를 사용하며, csv 모듈이 인용부호도 안전하게 처리합니다.
        delimiter = "," if ext == ".csv" else "|"
        encoding = "utf-8-sig" if ext == ".csv" else "utf-8"
        with path.open("w", encoding=encoding, newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows)
    else:
        # 신뢰할 수 있는 파이썬 프로그램에서 생성한 데이터를 저장하는 용도
        with path.open("wb") as f:
            pickle.dump(rows, f)


def load_file(filename: str | Path) -> list[dict]:
    """JSON/CSV/TXT/Pickle 파일을 읽어 딕셔너리 목록을 반환합니다."""
    path = Path(filename)
    ext = path.suffix.lower()
    if ext == ".json":
        with path.open("r", encoding="utf-8") as f:
            rows = json.load(f)
    elif ext in (".csv", ".txt"):
        delimiter = "," if ext == ".csv" else "|"
        encoding = "utf-8-sig" if ext == ".csv" else "utf-8"
        with path.open("r", encoding=encoding, newline="") as f:
            rows = list(csv.DictReader(f, delimiter=delimiter))
    elif ext in (".pkl", ".pickle"):
        # 보안 주의: pickle.load()는 신뢰할 수 없는 파일에는 절대 사용하지 마세요.
        with path.open("rb") as f:
            rows = pickle.load(f)
    else:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("파일 내용은 딕셔너리의 리스트여야 합니다.")
    return rows


# ----------------------------------------------------------------------
# 4. 사용자 인터페이스: input/print는 이 아래의 함수들에서만 사용
# ----------------------------------------------------------------------
def ask_text(message: str, default: str | None = None) -> str:
    """필수 문자열 입력. 수정할 때 기본값을 주면 Enter는 기존 값 유지."""
    while True:
        prompt = f"{message} [{default}]: " if default is not None else f"{message}: "
        value = input(prompt).strip()
        if value:
            return value
        if default is not None:
            return default
        print("값을 입력해주세요.")


def ask_int(message: str, default: int | None = None) -> int:
    while True:
        value = input(f"{message}" + (f" [{default}]" if default is not None else "") + ": ").strip()
        if not value and default is not None:
            return default
        try:
            number = int(value)
            if 1900 <= number <= date.today().year:
                return number
        except ValueError:
            pass
        print(f"1900~{date.today().year} 사이의 연도를 입력해주세요.")


def ask_positive_float(message: str, default: float | None = None) -> float:
    while True:
        value = input(f"{message}" + (f" [{default}]" if default is not None else "") + ": ").strip()
        if not value and default is not None:
            return default
        try:
            number = float(value)
            if math.isfinite(number) and number > 0:
                return number
        except ValueError:
            pass
        print("0보다 큰 숫자를 입력해주세요.")


def ask_yes_no(message: str) -> bool:
    return input(f"{message} (y/N): ").strip().lower() in ("y", "yes", "예")


def print_record(record: HealthInfo) -> None:
    """화면 출력만 담당합니다. HealthInfo 클래스는 출력하지 않습니다."""
    data = record.to_dict()
    print(f"\n식별번호 : {data['id']}")
    print(f"이름     : {data['name']}")
    print(f"생년     : {data['birth_year']}")
    print(f"성별     : {data['gender']}")
    print(f"키       : {data['height']} cm")
    print(f"몸무게   : {data['weight']} kg")
    print(f"BMI      : {data['bmi']}")
    print(f"비만도   : {data['status']}")


def print_list(records: list[HealthInfo]) -> None:
    if not records:
        print("등록된 건강정보가 없습니다.")
        return
    print("\n식별번호 | 이름 | 생년 | 성별 | 키(cm) | 몸무게(kg) | BMI | 비만도")
    print("-" * 75)
    for r in records:
        print(f"{r.id} | {r.name} | {r.birth_year} | {r.gender} | "
              f"{r.height:g} | {r.weight:g} | {r.bmi:.2f} | {r.status}")
    print(f"총 {len(records)}명")


def print_statistics(stats: dict) -> None:
    """계산은 manager.statistics(), 출력은 이 함수에서 담당합니다."""
    print("\n========== 건강정보 통계 ==========")
    print(f"전체 인원: {stats['count']}명")
    if stats["count"] == 0:
        print("통계 낼 데이터가 없습니다.")
        return
    print(f"평균 키: {stats['average_height']:.2f} cm")
    print(f"평균 몸무게: {stats['average_weight']:.2f} kg")
    print(f"평균 BMI: {stats['average_bmi']:.2f}")
    print("\n비만도 분포:")
    for label, count in stats["status_counts"].items():
        print(f"  {label}: {count}명 ({stats['status_percent'][label]:.1f}%)")
    print("성별 분포:")
    for label, count in stats["gender_counts"].items():
        print(f"  {label}: {count}명")


def tui_add(manager: HealthManager) -> bool:
    print("\n[건강정보 추가]")
    name = ask_text("이름")
    birth_year = ask_int("생년")
    gender = ask_text("성별(남/여/기타)")
    height = ask_positive_float("키(cm)")
    weight = ask_positive_float("몸무게(kg)")
    try:
        record = manager.add_patient(name, birth_year, gender, height, weight)
    except (TypeError, ValueError) as exc:
        print(f"추가 실패: {exc}")
        return False
    print(f"추가 완료. 자동 발급 식별번호: {record.id}")
    print_record(record)
    return True


def tui_search(manager: HealthManager) -> None:
    print("\n[검색 및 상세조회]")
    keyword = ask_text("검색할 이름 또는 식별번호")
    matches = manager.search(keyword)
    if not matches:
        print("검색 결과가 없습니다.")
        return
    print_list(matches)
    if len(matches) == 1:
        print_record(matches[0])
        return
    selected = input("상세조회할 식별번호 (Enter: 취소): ").strip()
    if selected:
        record = manager.find(selected)
        if record is not None and record in matches:
            print_record(record)
        else:
            print("검색 결과에 없는 식별번호입니다.")


def tui_edit_delete(manager: HealthManager) -> bool:
    print("\n[수정 및 삭제]")
    print("1. 수정  2. 삭제  0. 이전 메뉴")
    choice = input("선택: ").strip()
    if choice == "0":
        return False
    if choice not in ("1", "2"):
        print("올바른 메뉴를 선택해주세요.")
        return False
    person_id = ask_text("대상 식별번호")
    old = manager.find(person_id)
    if old is None:
        print("해당 식별번호가 없습니다.")
        return False
    print_record(old)
    if choice == "2":
        if not ask_yes_no("정말 삭제하시겠습니까?"):
            print("삭제를 취소했습니다.")
            return False
        manager.remove(person_id)
        print("삭제 완료")
        return True

    print("\n[정보 수정] 변경하지 않을 항목은 Enter를 누르세요.")
    name = ask_text("이름", old.name)
    birth_year = ask_int("생년", old.birth_year)
    gender = ask_text("성별", old.gender)
    height = ask_positive_float("키(cm)", old.height)
    weight = ask_positive_float("몸무게(kg)", old.weight)
    try:
        updated = manager.update_patient(
            person_id, name=name, birth_year=birth_year, gender=gender,
            height=height, weight=weight
        )
    except (TypeError, ValueError) as exc:
        print(f"수정 실패: {exc}")
        return False
    print("수정 완료. BMI와 비만도가 자동으로 다시 계산됩니다.")
    print_record(updated)
    return True


def tui_import(manager: HealthManager) -> bool:
    print("\n[파일에서 가져오기]")
    path = ask_text("파일 경로 (json/csv/txt/pkl, Enter: 기본 파일)", str(DEFAULT_FILE))
    if manager.all() and not ask_yes_no("기존 목록을 불러온 목록으로 교체할까요?"):
        print("불러오기를 취소했습니다.")
        return False
    try:
        rows = load_file(path)  # 모듈 1: 파일에서 목록을 읽음
        count = manager.load_rows(rows)  # 모듈 2: HealthManager에 전달
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            json.JSONDecodeError, csv.Error, pickle.PickleError) as exc:
        print(f"불러오기 실패: {exc}")
        return False
    print(f"불러오기 완료: {count}명")
    return True


def tui_export(manager: HealthManager) -> bool:
    print("\n[파일로 저장]")
    path = ask_text("저장할 파일 경로 (json/csv/txt/pkl, Enter: 기본 파일)", str(DEFAULT_FILE))
    try:
        save_file(path, manager.to_dict_list())
    except (OSError, ValueError, TypeError, UnicodeError, csv.Error) as exc:
        print(f"저장 실패: {exc}")
        return False
    print(f"저장 완료: {Path(path)}")
    return True


def print_menu() -> None:
    print("\n-------------- 건강정보 관리 시스템 --------------")
    print(" 1. 추가")
    print(" 2. 목록 조회")
    print(" 3. 검색 및 상세조회")
    print(" 4. 수정 및 삭제")
    print(" 5. 통계조회")
    print(" 6. 파일에서 가져오기 (모듈 1)")
    print(" 7. 파일로 저장 (모듈 1)")
    print(" 0. 종료")
    print("------------------------------------------------")


def main() -> None:
    """콘솔 응용 프로그램: 메뉴와 입력/출력만 조정합니다."""
    manager = HealthManager()
    unsaved_changes = False

    # 실행 시 기본 JSON 파일이 존재하면 목록을 읽어 관리자에게 전달
    if DEFAULT_FILE.exists():
        try:
            count = manager.load_rows(load_file(DEFAULT_FILE))
            print(f"기본 건강정보 파일에서 {count}명을 불러왔습니다.")
        except (OSError, ValueError, TypeError, KeyError, UnicodeError,
                json.JSONDecodeError) as exc:
            print(f"기본 파일을 읽지 못했습니다: {exc}")
    else:
        print("저장된 기본 파일이 없습니다. 새 목록으로 시작합니다.")

    try:
        while True:
            print_menu()
            choice = input("메뉴 선택: ").strip()
            if choice == "1":
                unsaved_changes |= tui_add(manager)
            elif choice == "2":
                print_list(manager.all())
            elif choice == "3":
                tui_search(manager)
            elif choice == "4":
                unsaved_changes |= tui_edit_delete(manager)
            elif choice == "5":
                print_statistics(manager.statistics())
            elif choice == "6":
                if tui_import(manager):
                    unsaved_changes = False
            elif choice == "7":
                if tui_export(manager):
                    unsaved_changes = False
            elif choice == "0":
                if unsaved_changes and not ask_yes_no("저장하지 않은 변경 사항이 있습니다. 종료할까요?"):
                    continue
                print("건강정보 관리 시스템을 종료합니다.")
                break
            else:
                print("0~7 사이의 메뉴 번호를 입력해주세요.")
    except (EOFError, KeyboardInterrupt):
        print("\n입력이 종료되어 프로그램을 마칩니다.")


if __name__ == "__main__":
    main()
