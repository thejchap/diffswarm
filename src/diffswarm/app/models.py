"""Shared, non-api-endpoint-specific models."""

from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar, Self

from dateutil import parser as dateutil_parser
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
)
from ulid import ULID


class DiffSwarmBaseModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )


class LineType(StrEnum):
    ADD = "ADD"
    DELETE = "DELETE"
    CONTEXT = "CONTEXT"


class Line(BaseModel):
    type: LineType
    content: str
    line_number_old: int | None = None
    line_number_new: int | None = None


class Hunk(DiffSwarmBaseModel):
    from_start: int = Field(..., ge=0)
    from_count: int = Field(..., ge=0)
    to_start: int = Field(..., ge=0)
    to_count: int = Field(..., ge=0)
    lines: list[Line]

    @field_validator("lines")
    @classmethod
    def validate_line_counts(cls, v: Any, info: ValidationInfo) -> Any:  # noqa: ANN401
        if "from_count" not in info.data or "to_count" not in info.data:
            return v
        from_count = info.data["from_count"]
        to_count = info.data["to_count"]
        delete_count = sum(1 for line in v if line.type == LineType.DELETE)
        add_count = sum(1 for line in v if line.type == LineType.ADD)
        context_count = sum(1 for line in v if line.type == LineType.CONTEXT)
        del_context_count = delete_count + context_count
        if from_count != del_context_count:
            msg = f"Expected {from_count} from-lines, got {del_context_count}"
            raise ValueError(msg)
        if to_count != add_count + context_count:
            msg = f"Expected {to_count} to-lines, got {add_count + context_count}"
            raise ValueError(msg)
        return v


class DiffBase(DiffSwarmBaseModel):
    """
    A structured representation of a diff.

    # References
    - https://www.gnu.org/software/diffutils/manual/html_node/Unified-Format.html
    - https://www.gnu.org/software/diffutils/manual/html_node/Example-Unified.html
    - https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html

    # Examples
    >>> diff = DiffBase.parse_str(DiffBase.HELLO_WORLD)
    >>> diff.from_filename
    '/dev/fd/14'
    >>> diff.to_filename
    '/dev/fd/16'
    >>> diff.from_timestamp.isoformat()
    '2025-07-26T17:33:15'
    >>> diff.to_timestamp.isoformat()
    '2025-07-26T17:33:15'
    >>> len(diff.hunks)
    1
    >>> len(diff.hunks[0].lines)
    2
    >>> diff.hunks[0].lines[0]
    Line(type=<LineType.CONTEXT: 'CONTEXT'>, content='hello', line_number_old=1, line_number_new=1)
    >>> diff.hunks[0].lines[1]
    Line(type=<LineType.ADD: 'ADD'>, content='world', line_number_old=None, line_number_new=2)
    """  # noqa: E501

    HELLO_WORLD: ClassVar[str] = """\
--- /dev/fd/14	2025-07-26 17:33:15
+++ /dev/fd/16	2025-07-26 17:33:15
@@ -1 +1,2 @@
 hello
+world
    """.strip()

    raw: str = Field(..., examples=[HELLO_WORLD], min_length=1)
    from_filename: str = Field(..., min_length=1)
    from_timestamp: datetime | None = None
    to_filename: str = Field(..., min_length=1)
    to_timestamp: datetime | None = None
    hunks: list[Hunk] = Field(..., min_length=1)

    @classmethod
    def parse_bytes(cls, raw: bytes) -> Self:
        return cls.parse_str(raw.decode())

    @classmethod
    def parse_str(cls, raw: str) -> Self:
        """Parse a unified diff string using recursive descent parsing."""
        lines = raw.strip().split("\n")
        parser = UnifiedDiffParser(lines)
        return cls.model_validate(parser.parse_diff(raw))


class UnifiedDiffParser:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.pos = 0

    @property
    def current_line(self) -> str | None:
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    def advance(self) -> None:
        self.pos += 1

    def parse_diff(self, raw: str) -> DiffBase:
        from_info = self._parse_from_header()
        to_info = self._parse_to_header()
        hunks = self._parse_hunks()
        if not hunks:
            msg = "No hunks found in diff"
            raise ValueError(msg)
        return DiffBase(
            raw=raw,
            from_filename=from_info["filename"],
            from_timestamp=from_info["timestamp"],
            to_filename=to_info["filename"],
            to_timestamp=to_info["timestamp"],
            hunks=hunks,
        )

    def _parse_from_header(self) -> dict[str, Any]:
        """Parse '--- filename [timestamp]' header."""
        while self.current_line and not self.current_line.startswith("--- "):
            self.advance()

        if not self.current_line or not self.current_line.startswith("--- "):
            msg = "Missing '---' header"
            raise ValueError(msg)

        return self._parse_file_header(self.current_line, "---")

    def _parse_to_header(self) -> dict[str, Any]:
        """Parse '+++ filename [timestamp]' header."""
        self.advance()  # Move past from header

        if not self.current_line or not self.current_line.startswith("+++ "):
            msg = "Missing '+++' header"
            raise ValueError(msg)

        return self._parse_file_header(self.current_line, "+++")

    def _parse_file_header(self, line: str, prefix: str) -> dict[str, Any]:
        """Parse file header line extracting filename and optional timestamp."""
        content = line[len(prefix) + 1 :]  # Remove prefix and space
        parts = content.split("\t", 1)
        filename = parts[0]
        timestamp = None

        if len(parts) > 1:
            try:
                timestamp = dateutil_parser.parse(parts[1])
            except (ValueError, TypeError):
                timestamp = None

        return {"filename": filename, "timestamp": timestamp}

    def _parse_hunks(self) -> list[Hunk]:
        """Parse all hunks in the diff."""
        hunks: list[Hunk] = []
        self.advance()
        while self.current_line:
            if self.current_line.startswith("@@ "):
                hunks.append(self._parse_hunk())
            else:
                self.advance()
        return hunks

    def _parse_hunk(self) -> Hunk:
        """Parse single hunk: header + lines."""
        if not self.current_line:
            msg = "Expected hunk header, but reached end of input"
            raise ValueError(msg)
        header = self._parse_hunk_header(self.current_line)
        self.advance()  # Move past hunk header
        lines = self._parse_hunk_lines(header["from_start"], header["to_start"])
        return Hunk(
            from_start=header["from_start"],
            from_count=header["from_count"],
            to_start=header["to_start"],
            to_count=header["to_count"],
            lines=lines,
        )

    def _parse_hunk_header(self, line: str) -> dict[str, int]:
        """Parse '@@ -from_range +to_range @@' header."""
        parts = line.split(" ")
        min_parts = 3
        if len(parts) < min_parts:
            msg = f"Invalid hunk header: {line}"
            raise ValueError(msg)
        from_range = parts[1][1:]  # Remove '-' prefix
        to_range = parts[2][1:]  # Remove '+' prefix
        try:
            from_start, from_count = self._parse_range(from_range)
            to_start, to_count = self._parse_range(to_range)
        except ValueError as err:
            msg = f"Invalid line numbers in hunk header: {line}"
            raise ValueError(msg) from err
        return {
            "from_start": from_start,
            "from_count": from_count,
            "to_start": to_start,
            "to_count": to_count,
        }

    def _parse_range(self, range_str: str) -> tuple[int, int]:
        """Parse range like '1' or '1,3' returning (start, count)."""
        parts = range_str.split(",")
        start = int(parts[0])
        count = int(parts[1]) if len(parts) > 1 else 1
        return start, count

    def _parse_hunk_lines(self, from_start: int, to_start: int) -> list[Line]:
        """Parse lines within a hunk until next hunk or end."""
        lines: list[Line] = []
        old_line_num = from_start
        new_line_num = to_start

        while self.current_line and not self.current_line.startswith("@@"):
            line = self._parse_hunk_line(self.current_line, old_line_num, new_line_num)
            lines.append(line)

            # Update line numbers based on line type
            if line.type == LineType.CONTEXT:
                old_line_num += 1
                new_line_num += 1
            elif line.type == LineType.DELETE:
                old_line_num += 1
            elif line.type == LineType.ADD:
                new_line_num += 1

            self.advance()
        return lines

    def _parse_hunk_line(self, line: str, old_line_num: int, new_line_num: int) -> Line:
        """Parse single line within hunk based on prefix."""
        if line.startswith(" "):
            return Line(
                type=LineType.CONTEXT,
                content=line[1:],
                line_number_old=old_line_num,
                line_number_new=new_line_num,
            )
        if line.startswith("-"):
            return Line(
                type=LineType.DELETE,
                content=line[1:],
                line_number_old=old_line_num,
                line_number_new=None,
            )
        if line.startswith("+"):
            return Line(
                type=LineType.ADD,
                content=line[1:],
                line_number_old=None,
                line_number_new=new_line_num,
            )
        return Line(
            type=LineType.CONTEXT,
            content=line,
            line_number_old=old_line_num,
            line_number_new=new_line_num,
        )


class Diff(DiffSwarmBaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_: ULID = Field(..., alias="id")
    raw: str
