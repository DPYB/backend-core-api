#!/usr/bin/env python3
"""하네스 문서 규격 및 비대화 방지 공통 검증 스크립트.

DPYB 전 레포 공통 하네스 규칙 검증:
1. HANDOFF.md: 세션 수 <= 5개, 전체 라인 수 <= 200줄, 타 레포 침범 방지 (PR 번호/링크 참조는 허용)
2. PLAN.md: 타 레포 전용 구현 태스크 미포함 (자동 감지)
3. STATE.md: 전체 라인 수 <= 150줄 (마일스톤 스냅샷 원칙)
4. DECISIONS.md: 전체 라인 수 <= 150줄, 크기 <= 20KB (3단 압축 원칙)
5. archive/ 디렉토리: 파일명 규칙 `^(HANDOFF|STATE|DECISIONS)_\\d{4}-\\d{2}\\.md$` 준수
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HARNESS_DIR = Path(".harness")
ARCHIVE_DIR = HARNESS_DIR / "archive"
HANDOFF_FILE = HARNESS_DIR / "HANDOFF.md"
PLAN_FILE = HARNESS_DIR / "PLAN.md"
STATE_FILE = HARNESS_DIR / "STATE.md"
DECISIONS_FILE = HARNESS_DIR / "DECISIONS.md"

MAX_HANDOFF_SESSIONS = 5
MAX_HANDOFF_LINES = 200
MAX_STATE_LINES = 150
MAX_DECISIONS_LINES = 150
MAX_DECISIONS_BYTES = 20 * 1024  # 20KB 상한

# DPYB 서비스 전 레포 목록
DPYB_REPOS = [
    "backend-ai-agent",
    "backend-core-api",
    "frontend-reader-web",
    "backend-record-api",
]

ARCHIVE_FILE_PATTERN = re.compile(r"^(HANDOFF|STATE|DECISIONS)_\d{4}-\d{2}\.md$")


def get_current_repo_name() -> str:
    """Git 최상위 디렉토리명 또는 현재 작업 폴더명으로 현재 레포 식별."""
    try:
        git_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        repo_name = Path(git_root).name
        if repo_name in DPYB_REPOS:
            return repo_name
    except Exception:
        pass
    cwd_name = Path.cwd().name
    if cwd_name in DPYB_REPOS:
        return cwd_name
    return "backend-core-api"


def get_other_repos(current_repo: str) -> list[str]:
    """현재 레포를 제외한 나머지 DPYB 레포명 반환."""
    return [repo for repo in DPYB_REPOS if repo != current_repo]


def check_archive_filenames() -> list[str]:
    errors: list[str] = []
    if not ARCHIVE_DIR.exists():
        return errors

    for path in ARCHIVE_DIR.iterdir():
        if path.is_file() and path.suffix == ".md":
            if not ARCHIVE_FILE_PATTERN.match(path.name):
                errors.append(
                    f"❌ archive 파일명 규격 위반: '{path.name}' "
                    f"(표준 형식: '^(HANDOFF|STATE|DECISIONS)_YYYY-MM.md')"
                )
    return errors


def check_handoff(other_repos: list[str]) -> list[str]:
    errors: list[str] = []
    if not HANDOFF_FILE.exists():
        return [f"❌ {HANDOFF_FILE} 파일이 존재하지 않습니다."]

    lines = HANDOFF_FILE.read_text(encoding="utf-8").splitlines()
    line_count = len(lines)
    if line_count > MAX_HANDOFF_LINES:
        errors.append(
            f"❌ HANDOFF.md 라인 수 초과: 현재 {line_count}줄 (상한: {MAX_HANDOFF_LINES}줄). "
            f"오래된 세션을 .harness/archive/ 로 롤링하세요."
        )

    # '## 세션 N' 또는 '## YYYY-MM-DD:' 두 가지 세션 헤더 패턴 지원
    sessions = [
        line
        for line in lines
        if re.match(r"^##\s+(?:세션\s+\d+|\d{4}-\d{2}-\d{2}:?)", line)
    ]
    if len(sessions) > MAX_HANDOFF_SESSIONS:
        errors.append(
            f"❌ HANDOFF.md 세션 수 초과: 현재 {len(sessions)}개 (상한: {MAX_HANDOFF_SESSIONS}개). "
            f"오래된 세션을 .harness/archive/ 로 롤링하세요."
        )

    # 타 레포 내부 코드/작업 침범 검사 (단, PR 링크/참조는 허용)
    for idx, line in enumerate(lines, start=1):
        for repo in other_repos:
            if repo in line:
                is_pr_reference = bool(
                    re.search(rf"(?:[\w-]+/)?{repo}(?:/pull/|#)\d+", line)
                    or re.search(rf"github\.com/[^/\s]+/{repo}/pull/\d+", line)
                    or re.search(rf"https?://\S*{repo}\S*", line)
                )
                if not is_pr_reference:
                    errors.append(
                        f"❌ HANDOFF.md L{idx}: 타 레포 내부 작업 침범 감지 ('{repo}'). "
                        f"타 레포 작업은 해당 레포에 작성하고, 본 레포에서는 PR 링크 1줄로만 참조하세요."
                    )
                    break

    return errors


def check_plan(other_repos: list[str]) -> list[str]:
    errors: list[str] = []
    if not PLAN_FILE.exists():
        return errors

    content = PLAN_FILE.read_text(encoding="utf-8")
    for repo in other_repos:
        if re.search(rf"\b{repo}\b", content):
            errors.append(
                f"❌ PLAN.md에 타 레포 키워드 감지 ('{repo}'): "
                f"타 레포 구현 태스크는 해당 레포의 PLAN.md에 작성해야 합니다."
            )
            break

    return errors


def check_state() -> list[str]:
    errors: list[str] = []
    if not STATE_FILE.exists():
        return errors

    lines = STATE_FILE.read_text(encoding="utf-8").splitlines()
    if len(lines) > MAX_STATE_LINES:
        errors.append(
            f"❌ STATE.md 라인 수 초과: 현재 {len(lines)}줄 (상한: {MAX_STATE_LINES}줄). "
            f"장황한 코드 diff를 걷어내고 마일스톤 1~3줄 요약 스냅샷으로 정돈하세요."
        )

    return errors


def check_decisions() -> list[str]:
    errors: list[str] = []
    if not DECISIONS_FILE.exists():
        return errors

    content = DECISIONS_FILE.read_text(encoding="utf-8")
    lines = content.splitlines()
    line_count = len(lines)
    byte_count = len(content.encode("utf-8"))

    if line_count > MAX_DECISIONS_LINES:
        errors.append(
            f"❌ DECISIONS.md 라인 수 초과: 현재 {line_count}줄 (상한: {MAX_DECISIONS_LINES}줄)."
        )

    if byte_count > MAX_DECISIONS_BYTES:
        errors.append(
            f"❌ DECISIONS.md 용량 초과: 현재 {byte_count / 1024:.1f}KB "
            f"(상한: {MAX_DECISIONS_BYTES / 1024:.0f}KB). [결정/이유/영향] 3단 압축을 적용하세요."
        )

    return errors


def main() -> int:
    current_repo = get_current_repo_name()
    other_repos = get_other_repos(current_repo)

    all_errors: list[str] = []
    all_errors.extend(check_archive_filenames())
    all_errors.extend(check_handoff(other_repos))
    all_errors.extend(check_plan(other_repos))
    all_errors.extend(check_state())
    all_errors.extend(check_decisions())

    if all_errors:
        print(f"❌ [{current_repo}] 하네스 규격 검증 실패 ({len(all_errors)}건):")
        for err in all_errors:
            print(f"   {err}")
        return 1

    print(
        f"✅ [{current_repo}] 하네스 규격 검증 통과 (HANDOFF, PLAN, STATE, DECISIONS, archive 정상)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
