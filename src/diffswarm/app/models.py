"""
shared, non-api-endpoint-specific models
"""

from enum import StrEnum
from typing import ClassVar, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class DiffSwarmBaseModel(BaseModel):
    model_config = ConfigDict(
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


class Hunk(DiffSwarmBaseModel):
    from_start: int = Field(..., ge=0)
    from_count: int = Field(..., ge=0)
    to_start: int = Field(..., ge=0)
    to_count: int = Field(..., ge=0)
    lines: list[Line]

    @field_validator("lines")
    @classmethod
    def validate_line_counts(cls, v, info):
        if "from_count" not in info.data or "to_count" not in info.data:
            return v
        from_count = info.data["from_count"]
        to_count = info.data["to_count"]
        delete_count = sum(1 for line in v if line.type == LineType.DELETE)
        add_count = sum(1 for line in v if line.type == LineType.ADD)
        context_count = sum(1 for line in v if line.type == LineType.CONTEXT)
        if from_count != delete_count + context_count:
            raise ValueError(
                f"Hunk line count mismatch: expected {from_count} from-lines, got {delete_count + context_count}"
            )
        if to_count != add_count + context_count:
            raise ValueError(
                f"Hunk line count mismatch: expected {to_count} to-lines, got {add_count + context_count}"
            )
        return v


class Diff(DiffSwarmBaseModel):
    """
    # Diff

    # References
    - https://www.gnu.org/software/diffutils/manual/html_node/Unified-Format.html
    - https://www.gnu.org/software/diffutils/manual/html_node/Example-Unified.html
    - https://www.gnu.org/software/diffutils/manual/html_node/Detailed-Unified.html

    # Examples
    >>> diff = Diff.parse(Diff.HELLO_WORLD)
    >>> len(diff.hunks)
    1
    >>> len(diff.hunks[0].lines)
    2
    >>> diff.hunks[0].lines[1]
    Line(type=<LineType.ADD: 'ADD'>, content='world')
    """

    HELLO_WORLD: ClassVar = """\
--- /dev/fd/14	2025-07-26 17:33:15
+++ /dev/fd/16	2025-07-26 17:33:15
@@ -1 +1,2 @@
 hello
+world
    """.strip()

    raw: str = Field(..., examples=[HELLO_WORLD], min_length=1)
    from_filename: str = Field(..., min_length=1)
    from_timestamp: str | None = None
    to_filename: str = Field(..., min_length=1)
    to_timestamp: str | None = None
    hunks: list[Hunk] = Field(..., min_length=1)

    @classmethod
    def parse(cls, raw: str | bytes) -> Self:
        if isinstance(raw, bytes):
            raw = raw.decode()
        lines = raw.strip().split("\n")
        from_file_line = None
        to_file_line = None
        from_filename = None
        to_filename = None
        from_timestamp = None
        to_timestamp = None
        hunks = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("--- "):
                from_file_line = line
                parts = line[4:].split("\t", 1)
                from_filename = parts[0]
                from_timestamp = parts[1] if len(parts) > 1 else None
            elif line.startswith("+++ "):
                to_file_line = line
                parts = line[4:].split("\t", 1)
                to_filename = parts[0]
                to_timestamp = parts[1] if len(parts) > 1 else None
            elif line.startswith("@@ "):
                if not from_file_line or not to_file_line:
                    raise ValueError("Hunk found before file headers")
                hunk_match = line.split(" ")
                if len(hunk_match) < 3:
                    raise ValueError(f"Invalid hunk header: {line}")
                from_range = hunk_match[1][1:]
                to_range = hunk_match[2][1:]
                from_start, from_count = (from_range.split(",") + ["1"])[:2]
                to_start, to_count = (to_range.split(",") + ["1"])[:2]
                try:
                    from_start = int(from_start)
                    from_count = int(from_count)
                    to_start = int(to_start)
                    to_count = int(to_count)
                except ValueError:
                    raise ValueError(f"Invalid line numbers in hunk header: {line}")
                hunk_lines = []
                i += 1
                while i < len(lines) and not lines[i].startswith("@@"):
                    hunk_line = lines[i]
                    if hunk_line.startswith(" "):
                        hunk_lines.append(
                            Line(
                                type=LineType.CONTEXT,
                                content=hunk_line[1:],
                            )
                        )
                    elif hunk_line.startswith("-"):
                        hunk_lines.append(
                            Line(
                                type=LineType.DELETE,
                                content=hunk_line[1:],
                            )
                        )
                    elif hunk_line.startswith("+"):
                        hunk_lines.append(
                            Line(
                                type=LineType.ADD,
                                content=hunk_line[1:],
                            )
                        )
                    else:
                        hunk_lines.append(
                            Line(
                                type=LineType.CONTEXT,
                                content=hunk_line,
                            )
                        )
                    i += 1

                hunks.append(
                    Hunk(
                        from_start=from_start,
                        from_count=from_count,
                        to_start=to_start,
                        to_count=to_count,
                        lines=hunk_lines,
                    )
                )
                continue
            i += 1
        if not from_file_line or not to_file_line:
            raise ValueError("Missing file headers (--- and +++)")
        return cls(
            raw=raw,
            from_filename=from_filename or "",
            to_filename=to_filename or "",
            from_timestamp=from_timestamp,
            to_timestamp=to_timestamp,
            hunks=hunks,
        )
