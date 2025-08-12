"""
Shared, non-api-endpoint-specific models.

These are generally the business logic/API layer models, and should
be mapped to and from database models in `database.py`
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, ClassVar, NamedTuple, Self

from dateutil import parser as dateutil_parser
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    field_validator,
)
from ulid import ULID

from .database import DBComment, DBDiff, DBHunk, DBLine


def validate_prefixed_ulid(raw: str) -> str:
    prefix, ulid = raw.split("-")
    return f"{prefix}-{ULID.parse(ulid.upper())}".lower()


def generate_prefixed_ulid(prefix: str) -> str:
    return f"{prefix}-{ULID()}".lower()


PrefixedULID = Annotated[
    str,
    StringConstraints(
        to_lower=True,
        strip_whitespace=True,
        pattern=r"^[A-Za-z]-[0-9A-Ha-hJKMNP-TV-Zjkmnp-tv-z]{26}$",
    ),
    AfterValidator(validate_prefixed_ulid),
]


class DiffSwarmBaseModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        populate_by_name=True,
    )


class LineType(StrEnum):
    ADD = "ADD"
    DELETE = "DELETE"
    CONTEXT = "CONTEXT"


class HunkHeader(NamedTuple):
    """Header information parsed from a unified diff hunk."""

    from_start: int
    from_count: int
    to_start: int
    to_count: int
    has_header_context: bool


class LineBase(BaseModel):
    """Base Line model without ID column for parsing."""

    type: LineType
    content: str
    line_number_old: int | None = None
    line_number_new: int | None = None


class Line(BaseModel):
    """Line model with ID column for database persistence."""

    id_: PrefixedULID | None = Field(None, alias="id")
    type: LineType
    content: str
    line_number_old: int | None = None
    line_number_new: int | None = None

    @classmethod
    def from_db(cls, db_line: DBLine) -> Self:
        """Create a Line from a database model."""
        return cls(
            id=db_line.id,
            type=LineType(db_line.type),
            content=db_line.content,
            line_number_old=db_line.line_number_old,
            line_number_new=db_line.line_number_new,
        )


class HunkBase(DiffSwarmBaseModel):
    """Base Hunk model without ID column for parsing."""

    from_start: int = Field(..., ge=0)
    from_count: int = Field(..., ge=0)
    to_start: int = Field(..., ge=0)
    to_count: int = Field(..., ge=0)
    lines: list[LineBase]

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


class Hunk(DiffSwarmBaseModel):
    """Hunk model with ID column for database persistence."""

    model_config = ConfigDict(from_attributes=True)
    id_: PrefixedULID | None = Field(None, alias="id")
    name: str | None = None  # Display name, defaults to id
    from_start: int = Field(..., ge=0)
    from_count: int = Field(..., ge=0)
    to_start: int = Field(..., ge=0)
    to_count: int = Field(..., ge=0)
    completed_at: datetime | None = None
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

    @classmethod
    def from_db(cls, db_hunk: DBHunk) -> Self:
        """Create a Hunk from a database model."""
        return cls(
            id=db_hunk.id,
            name=db_hunk.name or db_hunk.id,  # Use name if available, fallback to id
            from_start=db_hunk.from_start,
            from_count=db_hunk.from_count,
            to_start=db_hunk.to_start,
            to_count=db_hunk.to_count,
            completed_at=db_hunk.completed_at,
            lines=[Line.from_db(db_line) for db_line in db_hunk.lines],
        )


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
    LineBase(type=<LineType.CONTEXT: 'CONTEXT'>, content='hello', line_number_old=1, line_number_new=1)
    >>> diff.hunks[0].lines[1]
    LineBase(type=<LineType.ADD: 'ADD'>, content='world', line_number_old=None, line_number_new=2)
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
    hunks: list[HunkBase] = Field(..., min_length=1)

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
        # Convert HunkBase to Hunk for the Diff model compatibility
        # Since DiffBase uses list[HunkBase], we need to handle this properly
        diff_hunks = hunks  # These are already HunkBase instances
        return DiffBase(
            raw=raw,
            from_filename=from_info["filename"],
            from_timestamp=from_info["timestamp"],
            to_filename=to_info["filename"],
            to_timestamp=to_info["timestamp"],
            hunks=diff_hunks,
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

    def _parse_hunks(self) -> list[HunkBase]:
        """Parse all hunks in the diff."""
        hunks: list[HunkBase] = []
        self.advance()
        while self.current_line:
            if self.current_line.startswith("@@ "):
                hunks.append(self._parse_hunk())
            else:
                self.advance()
        return hunks

    def _parse_hunk(self) -> HunkBase:
        """Parse single hunk: header + lines."""
        if not self.current_line:
            msg = "Expected hunk header, but reached end of input"
            raise ValueError(msg)
        header = self._parse_hunk_header(self.current_line)
        self.advance()  # Move past hunk header
        lines = self._parse_hunk_lines(
            header.from_start,
            header.to_start,
            header.from_count,
            header.to_count,
        )

        # If there's context in the header that's not included in the body,
        # add a virtual context line to account for the line count
        if header.has_header_context and lines:
            expected_from_lines = header.from_count
            actual_from_lines = sum(
                1 for line in lines if line.type in (LineType.DELETE, LineType.CONTEXT)
            )
            if actual_from_lines < expected_from_lines:
                # Add virtual context line at the beginning
                virtual_line = LineBase(
                    type=LineType.CONTEXT,
                    content="",  # Empty content for virtual header context
                    line_number_old=header.from_start,
                    line_number_new=header.to_start,
                )
                lines.insert(0, virtual_line)
                # Adjust line numbers for all subsequent lines
                for line in lines[1:]:
                    if (
                        line.type in (LineType.CONTEXT, LineType.DELETE)
                        and line.line_number_old is not None
                    ):
                        line.line_number_old += 1
                    if (
                        line.type in (LineType.CONTEXT, LineType.ADD)
                        and line.line_number_new is not None
                    ):
                        line.line_number_new += 1

        return HunkBase(
            from_start=header.from_start,
            from_count=header.from_count,
            to_start=header.to_start,
            to_count=header.to_count,
            lines=lines,
        )

    def _parse_hunk_header(self, line: str) -> HunkHeader:
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

        # Check if there's context after the closing @@
        # Format: @@ -from +to @@ [context]
        at_at_index = 3
        context_start_index = 4
        has_header_context = (
            len(parts) > at_at_index
            and parts[at_at_index] == "@@"
            and len(parts) > context_start_index
        )

        return HunkHeader(
            from_start=from_start,
            from_count=from_count,
            to_start=to_start,
            to_count=to_count,
            has_header_context=has_header_context,
        )

    def _parse_range(self, range_str: str) -> tuple[int, int]:
        """Parse range like '1' or '1,3' returning (start, count)."""
        parts = range_str.split(",")
        start = int(parts[0])
        count = int(parts[1]) if len(parts) > 1 else 1
        return start, count

    def _parse_hunk_lines(
        self, from_start: int, to_start: int, from_count: int, to_count: int
    ) -> list[LineBase]:
        """Parse lines within a hunk until next hunk or end."""
        lines: list[LineBase] = []
        old_line_num = from_start
        new_line_num = to_start

        # Track processed line counts to respect hunk header limits
        # from_count = DELETE + CONTEXT lines
        # to_count = ADD + CONTEXT lines
        delete_count = 0
        add_count = 0
        context_count = 0

        while self.current_line and not self.current_line.startswith("@@"):
            # Skip "\ No newline at end of file" markers
            if self.current_line.startswith("\\ "):
                self.advance()
                continue

            line = self._parse_hunk_line(self.current_line, old_line_num, new_line_num)

            # Count the line type before adding to check limits
            temp_delete_count = delete_count
            temp_add_count = add_count
            temp_context_count = context_count

            if line.type == LineType.CONTEXT:
                temp_context_count += 1
            elif line.type == LineType.DELETE:
                temp_delete_count += 1
            elif line.type == LineType.ADD:
                temp_add_count += 1

            # Check if adding this line would exceed the limits
            from_lines = temp_delete_count + temp_context_count
            to_lines = temp_add_count + temp_context_count

            if from_lines > from_count or to_lines > to_count:
                break

            # Update the actual counts and add the line
            delete_count = temp_delete_count
            add_count = temp_add_count
            context_count = temp_context_count
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

    def _parse_hunk_line(
        self, line: str, old_line_num: int, new_line_num: int
    ) -> LineBase:
        """Parse single line within hunk based on prefix."""
        if line.startswith(" "):
            return LineBase(
                type=LineType.CONTEXT,
                content=line[1:],
                line_number_old=old_line_num,
                line_number_new=new_line_num,
            )
        if line.startswith("-"):
            return LineBase(
                type=LineType.DELETE,
                content=line[1:],
                line_number_old=old_line_num,
                line_number_new=None,
            )
        if line.startswith("+"):
            return LineBase(
                type=LineType.ADD,
                content=line[1:],
                line_number_old=None,
                line_number_new=new_line_num,
            )
        return LineBase(
            type=LineType.CONTEXT,
            content=line,
            line_number_old=old_line_num,
            line_number_new=new_line_num,
        )


class Diff(DiffSwarmBaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_: PrefixedULID = Field(..., alias="id")
    name: str  # Display name, defaults to id
    raw: str
    from_filename: str
    from_timestamp: datetime | None = None
    to_filename: str
    to_timestamp: datetime | None = None
    hunks: list[Hunk]

    @classmethod
    def from_db(cls, db_diff: DBDiff) -> Self:
        """Create a Diff from a database model."""
        from_timestamp = None
        if db_diff.from_timestamp:
            from_timestamp = dateutil_parser.parse(db_diff.from_timestamp)

        to_timestamp = None
        if db_diff.to_timestamp:
            to_timestamp = dateutil_parser.parse(db_diff.to_timestamp)

        return cls(
            id=db_diff.id,
            name=db_diff.name or str(db_diff.id),  # Default to id if name is None
            raw=db_diff.raw,
            from_filename=db_diff.from_filename,
            from_timestamp=from_timestamp,
            to_filename=db_diff.to_filename,
            to_timestamp=to_timestamp,
            hunks=[Hunk.from_db(db_hunk) for db_hunk in db_diff.hunks],
        )


class Comment(DiffSwarmBaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_: PrefixedULID = Field(..., alias="id")
    text: str
    author: str
    timestamp: datetime
    hunk_id: PrefixedULID
    diff_id: PrefixedULID
    line_index: int
    start_offset: int
    end_offset: int
    in_reply_to: PrefixedULID | None = None

    @classmethod
    def from_db(cls, db_comment: DBComment) -> Self:
        """Create a Comment from a database model."""
        return cls(
            id=db_comment.id,
            text=db_comment.text,
            author=db_comment.author,
            timestamp=db_comment.timestamp,
            hunk_id=db_comment.hunk_id,
            diff_id=db_comment.diff_id,
            line_index=db_comment.line_index,
            start_offset=db_comment.start_offset,
            end_offset=db_comment.end_offset,
            in_reply_to=db_comment.in_reply_to if db_comment.in_reply_to else None,
        )
