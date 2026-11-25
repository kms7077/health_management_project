

import json
import csv
import pickle
from pathlib import Path
from dataclasses import dataclass


# 1. 건강정보 레코드
@dataclass
class HealthInfo:
   

    id: str
    name: str
    birth_year: int
    gender: str
    height: float  # cm
    weight: float  # kg

    def __post_init__(self):
        if not self.id.strip() or not self.name.strip():
            raise ValueError("ID와 이름은 비워둘 수 없습니다.")
        if self.height <= 0 or self.weight <= 0:
            raise ValueError("키와 몸무게는 0보다 커야 합니다.")

    @property
    def bmi(self) -> float:
        return round(self.weight / ((self.height / 100) ** 2), 2)

    @property
    def status(self) -> str:
        # 이 예제에서 사용하는 BMI 분류 기준
        if self.bmi < 18.5:
            return "저체중"
        if self.bmi < 23:
            return "정상"
        if self.bmi < 25:
            return "과체중"
        return "비만"

    def to_dict(self) -> dict:
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
    def from_dict(cls, row: dict):
        # CSV/TXT는 숫자도 문자열로 읽기 때문에 명시적으로 자료형을 변환합니다.
        # bmi와 status는 입력된 값을 신뢰하지 않고 다시 계산합니다.
        return cls(
            id=str(row["id"]),
            name=str(row["name"]),
            birth_year=int(row["birth_year"]),
            gender=str(row["gender"]),
            height=float(row["height"]),
            weight=float(row["weight"]),
        )


# 2. 건강정보 관리자
class HealthManager:
    """여러 건강정보 레코드를 관리하는 클래스."""

    def __init__(self):
        self._records: list[HealthInfo] = []

    def add(self, record: HealthInfo):
        if self.find(record.id) is not None:
            raise ValueError(f"중복된 ID입니다: {record.id}")
        self._records.append(record)

    def find(self, person_id: str) -> HealthInfo | None:
        for record in self._records:
            if record.id == person_id:
                return record
        return None

    def remove(self, person_id: str) -> bool:
        record = self.find(person_id)
        if record is None:
            return False
        self._records.remove(record)
        return True

    def all(self) -> list[HealthInfo]:
        return self._records.copy()

    def to_dict_list(self) -> list[dict]:
        return [record.to_dict() for record in self._records]

    def save(self, filename):
        save_file(filename, self.to_dict_list())

    def load(self, filename):
        # 파일의 레코드를 모두 검증한 후 기존 목록을 교체합니다.
        restored = HealthManager()
        for row in load_file(filename):
            restored.add(HealthInfo.from_dict(row))
        self._records = restored._records


# 3. 파일 입출력
FIELDS = ["id", "name", "birth_year", "gender", "height", "weight", "bmi", "status"]


def save_file(filename: str, rows: list[dict]):
    path = Path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    ext = path.suffix.lower()

    if ext == ".json":
        with path.open("w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)

    elif ext == ".csv":
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    elif ext == ".txt":
        # 학습용: 한 줄에 한 레코드, 필드 구분자는 | 입니다.
        with path.open("w", encoding="utf-8") as f:
            f.write("|".join(FIELDS) + "\n")
            for row in rows:
                values = [str(row[key]) for key in FIELDS]
                if any("|" in v or "\n" in v or "\r" in v for v in values):
                    raise ValueError("TXT 필드에는 | 또는 줄바꿈을 넣을 수 없습니다.")
                f.write("|".join(values) + "\n")

    elif ext == ".pkl":
        with path.open("wb") as f:
            pickle.dump(rows, f)

    else:
        raise ValueError(f"지원하지 않는 확장자입니다: {ext}")


def load_file(filename: str) -> list[dict]:
    path = Path(filename)
    ext = path.suffix.lower()

    if ext == ".json":
        with path.open("r", encoding="utf-8") as f:
            rows = json.load(f)

    elif ext == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))

    elif ext == ".txt":
        with path.open("r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        if not lines:
            return []
        if lines[0].split("|") != FIELDS:
            raise ValueError("TXT 파일의 첫 줄(헤더)이 올바르지 않습니다.")
        rows = []
        for line in lines[1:]:
            if not line:
                continue
            parts = line.split("|")
            if len(parts) != len(FIELDS):
                raise ValueError(f"TXT 데이터 열 개수가 잘못되었습니다: {line}")
            rows.append(dict(zip(FIELDS, parts)))

    elif ext == ".pkl":
        # 주의: pickle.load는 임의 코드 실행 위험이 있으므로
        # 출처가 불분명한 파일에는 절대로 사용하지 마세요.
        with path.open("rb") as f:
            rows = pickle.load(f)

    else:
        raise ValueError(f"지원하지 않는 확장자입니다: {ext}")

    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("저장 파일의 데이터는 사전(dict)의 리스트여야 합니다.")
    return rows


# 4. 실행 테스트
def main():
    manager = HealthManager()
    manager.add(HealthInfo("P2026-0001", "홍길동", 1995, "남", 175.0, 72.5))
    manager.add(HealthInfo("P2026-0002", "김영희", 1998, "여", 162.0, 52.0))

    # health_db.py가 있는 폴더를 기준으로 저장합니다.
    output = Path(__file__).resolve().parent / "output"
    for ext in ("json", "csv", "txt", "pkl"):
        filename = output / f"health_data.{ext}"
        manager.save(filename)
        print(f"저장 완료: {filename.name}")

        restored = HealthManager()
        restored.load(filename)
        assert restored.to_dict_list() == manager.to_dict_list()

    print("\n불러온 건강정보:")
    for record in restored.all():
        print(record.name, record.bmi, record.status)


if __name__ == "__main__":
    main()
