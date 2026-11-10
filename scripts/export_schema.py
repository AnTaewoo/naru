"""naru_contracts → JSON Schema → FE 타입 — `make schema` (ROADMAP T2.1, CONVENTIONS §2).

산출
  packages/fe/src/types/contracts.schema.json   pydantic json_schema (FE용 모델 전부, $defs 공유)
  packages/fe/src/types/contracts.d.ts          json-schema-to-typescript (npx 필요). 수정 금지
Flask는 OpenAPI를 안 만드니 이게 계약 동기화의 유일한 경로다.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pydantic import TypeAdapter

from naru_contracts import (
    CandidateBatch,
    CandidateBatchResponse,
    ClosureCandidate,
    ClosureEventsQuery,
    ClosureEventsResponse,
    ClosuresQuery,
    ClosureState,
    ErrorBody,
    FeatureCollection,
    GeocodeReverseQuery,
    GeocodeReverseResponse,
    GeocodeSearchQuery,
    GeocodeSearchResponse,
    NearestCrosswalkQuery,
    NearestCrosswalkResponse,
    RecentReportsQuery,
    RecentReportsResponse,
    ReportRequest,
    ReportResponse,
    RouteQuery,
    RouteResponse,
)

MODELS = (
    ClosureCandidate,
    CandidateBatch,
    CandidateBatchResponse,
    ClosureState,
    RouteQuery,
    RouteResponse,
    ClosuresQuery,
    FeatureCollection,
    ClosureEventsQuery,
    ClosureEventsResponse,
    GeocodeSearchQuery,
    GeocodeSearchResponse,
    GeocodeReverseQuery,
    GeocodeReverseResponse,
    NearestCrosswalkQuery,
    NearestCrosswalkResponse,
    ReportRequest,
    ReportResponse,
    RecentReportsQuery,
    RecentReportsResponse,
    ErrorBody,
)
OUT_DIR = Path("packages/fe/src/types")
J2TS = "json-schema-to-typescript@15"


def build_schema() -> dict[str, object]:
    """모델마다 스키마를 뽑고 $defs 를 한 사전으로 합친다 (이름이 같으면 내용도 같아야 한다)."""
    defs: dict[str, object] = {}
    for model in MODELS:
        schema = TypeAdapter(model).json_schema(ref_template="#/$defs/{model}")
        for name, body in schema.pop("$defs", {}).items():
            if name in defs and defs[name] != body:
                raise SystemExit(f"$defs 충돌: {name}")
            defs[name] = body
        if model.__name__ in defs and defs[model.__name__] != schema:
            raise SystemExit(f"$defs 충돌: {model.__name__}")
        defs[model.__name__] = schema
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "naru_contracts",
        "title": "NaruContracts",
        "description": "docs/INTERFACE.md v0.5 — scripts/export_schema.py 생성물. 수정 금지",
        "type": "object",
        "properties": {name: {"$ref": f"#/$defs/{name}"} for name in defs},
        "$defs": defs,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="naru_contracts JSON Schema + TypeScript 타입")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--no-ts", action="store_true", help="JSON Schema만")
    args = ap.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    schema_path = args.out_dir / "contracts.schema.json"
    schema_path.write_text(json.dumps(build_schema(), ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"{schema_path} ({len(MODELS)} 모델)")
    if args.no_ts:
        return 0
    npx = shutil.which("npx")
    if not npx:
        print("npx 없음 — contracts.d.ts 는 못 만든다 (node 설치 후 make schema)", file=sys.stderr)
        return 1
    ts_path = args.out_dir / "contracts.d.ts"
    banner = "/* 생성물 — scripts/export_schema.py (naru_contracts). 손으로 고치지 않는다 */"
    cmd = [npx, "--yes", J2TS, str(schema_path), "-o", str(ts_path), "--bannerComment", banner]
    subprocess.run(cmd, check=True)
    print(f"{ts_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
