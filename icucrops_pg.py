"""A sqlite3-shaped adapter over PostgreSQL, for the Supabase backend.

main.py holds ~160 hand-written SQL statements against SQLite, reached through
`with connect_database() as connection:` and read back as `row["column"]`.
Rewriting every one of those by hand to psycopg's dialect would be a large
change with a lot of places to get quietly wrong.

Instead this module presents the slice of the sqlite3 API that main.py
actually uses, and translates on the way through. The survey behind the
translation list:

    ? placeholders          383   -> %s
    INSERT OR IGNORE          5   -> ON CONFLICT DO NOTHING
    strftime('%s', col)       1   -> FLOOR(EXTRACT(EPOCH FROM col))
    cursor.lastrowid          4   -> RETURNING id
    PRAGMA                    6   -> no-op (or skipped entirely)
    LIKE / % in SQL           0   -> nothing to escape
    julianday, IFNULL,        0
    GROUP_CONCAT, substr

Everything else in those statements - COALESCE, LIMIT, OFFSET, ON CONFLICT,
CHECK, the joins - is already standard SQL that both engines accept.

Transaction semantics follow sqlite3: `with connection:` commits when the
block succeeds and rolls back when it raises. Unlike sqlite3 the connection
is also closed on exit, because on a serverless host every request that
leaked one would hold a pooler slot.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Sequence

import psycopg
from psycopg import sql as _sql  # noqa: F401  (re-exported for callers)

# Tables whose primary key is named `id`. An INSERT into one of these gets
# `RETURNING id` appended so cursor.lastrowid can be answered; an INSERT into
# any other table must not, because there is no such column to return.
TABLES_WITH_ID = frozenset({
    "users",
    "cultivations",
    "irrigation_runs",
    "sensor_backends",
    "sensor_definitions",
    "sensor_registry",
    "sensor_readings",
    "notifications",
    "notification_reads",
})

# Columns that are boolean in Postgres and were INTEGER in SQLite. Python code
# written against SQLite passes 1/0 for these, and Postgres will not read an
# integer as a boolean - it raises DatatypeMismatch rather than coercing. The
# literals in the SQL were fixed at the call sites; these are the ones that
# arrive as bound parameters, where the call site cannot see the column type.
# Handled here so a query written later does not have to remember.
BOOLEAN_COLUMNS = frozenset({
    "is_active",
    "is_enabled",
    "automatic_enabled",
    "schedule_enabled",
    # cultivation_harvests.on_schedule. Missing here, every ending of a crop
    # failed on the hosted site with a bare 500 -- both the check button and
    # the bin, because a removal records a harvest row too. It worked on the
    # Pi throughout, which is what made it look like a sync fault.
    "on_schedule",
})

_INSERT_TABLE = re.compile(r"^\s*INSERT\s+(?:OR\s+\w+\s+)?INTO\s+([A-Za-z_][A-Za-z0-9_]*)", re.I)
_INSERT_COLUMNS = re.compile(
    r"^\s*INSERT\s+(?:OR\s+\w+\s+)?INTO\s+[A-Za-z_][A-Za-z0-9_]*\s*\(([^)]*)\)", re.I | re.S
)
_ASSIGNED_COLUMN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*$")
_INSERT_OR_IGNORE = re.compile(r"^(\s*)INSERT\s+OR\s+IGNORE\s+INTO", re.I)
_STRFTIME_EPOCH = re.compile(r"strftime\(\s*'%s'\s*,\s*([^)]+?)\s*\)", re.I)
_PRAGMA = re.compile(r"^\s*PRAGMA\b", re.I)
_RETURNING = re.compile(r"\bRETURNING\b", re.I)
_ON_CONFLICT = re.compile(r"\bON\s+CONFLICT\b", re.I)

_translation_cache: dict[str, tuple[str, bool, tuple[int, ...]]] = {}


def _swap_placeholders(statement: str) -> str:
    """Turn SQLite's ? into psycopg's %s, leaving quoted text alone.

    A naive replace would also rewrite any ? that appears inside a string
    literal, so this walks the statement tracking quote state.
    """
    out: list[str] = []
    in_string = False
    index = 0
    length = len(statement)
    while index < length:
        character = statement[index]
        if character == "%":
            # psycopg scans for % regardless of SQL string context, so a
            # literal one has to be doubled even inside quotes. (No statement
            # needs this today, but a future one would fail obscurely.)
            out.append("%%")
        elif character == "'":
            # '' inside a string literal is an escaped quote, not a close.
            if in_string and index + 1 < length and statement[index + 1] == "'":
                out.append("''")
                index += 2
                continue
            in_string = not in_string
            out.append(character)
        elif character == "?" and not in_string:
            out.append("%s")
        else:
            out.append(character)
        index += 1
    return "".join(out)


def boolean_parameter_positions(statement: str) -> tuple[int, ...]:
    """Which bound parameters land on a boolean column.

    Two shapes cover every statement in main.py. `SET flag = %s` and
    `WHERE flag = %s` are found by looking at what sits immediately before
    each placeholder, which also correctly ignores the ones that do not follow
    an assignment. `INSERT INTO t (a, b) VALUES (%s, %s)` is matched by
    position against the column list.

    Anything else is left alone: a wrong guess here would corrupt a value,
    while a missed one only reproduces today's behaviour.
    """
    offsets = [match.start() for match in re.finditer(r"%s", statement)]
    if not offsets:
        return ()

    columns_match = _INSERT_COLUMNS.match(statement)
    if columns_match:
        columns = [name.strip().lower() for name in columns_match.group(1).split(",")]
        values_at = statement.upper().find("VALUES", columns_match.end())
        if values_at != -1:
            in_values = [offset for offset in offsets if offset > values_at]
            if len(in_values) == len(columns):
                return tuple(
                    index for index, name in enumerate(columns) if name in BOOLEAN_COLUMNS
                )
        return ()

    found: list[int] = []
    previous_placeholder_end = 0
    for index, offset in enumerate(offsets):
        # Only the SQL between the preceding placeholder and this one can name
        # the column receiving this value. Slicing from the start for every
        # placeholder made this O(n²): the report sampler has hundreds of
        # small indexed UNION branches and spent ~15 seconds in this adapter
        # before PostgreSQL even received the query.
        assigned = _ASSIGNED_COLUMN.search(
            statement[previous_placeholder_end:offset]
        )
        if assigned and assigned.group(1).lower() in BOOLEAN_COLUMNS:
            found.append(index)
        previous_placeholder_end = offset + 2
    return tuple(found)


def translate(statement: str) -> tuple[str, bool, tuple[int, ...]]:
    """Return the PostgreSQL statement, whether it returns an id, and which
    bound parameters need coercing to bool."""
    cached = _translation_cache.get(statement)
    if cached is not None:
        return cached

    if _PRAGMA.match(statement):
        # PRAGMA foreign_keys is the default in PostgreSQL, and PRAGMA
        # table_info only ever ran inside the SQLite schema migrator, which
        # this backend skips.
        result = ("SELECT 1 WHERE false", False, ())
        _translation_cache[statement] = result
        return result

    # FLOOR, because SQLite's strftime('%s') is whole seconds, truncated.
    # EXTRACT keeps the fraction, and Postgres's CAST(... AS INTEGER) then
    # rounds it: a reading at 14:59:59.7 landed in the 15:00 hourly bucket on
    # Supabase and in the 14:00 one on the Pi, so the website and the kiosk
    # picked different readings for the same hour of the dashboard graph.
    translated = _STRFTIME_EPOCH.sub(r"FLOOR(EXTRACT(EPOCH FROM (\1)::timestamptz))", statement)

    conflict_free = _INSERT_OR_IGNORE.sub(r"\1INSERT INTO", translated)
    ignoring = conflict_free != translated
    translated = conflict_free

    translated = _swap_placeholders(translated)

    if ignoring and not _ON_CONFLICT.search(translated):
        translated = translated.rstrip().rstrip(";") + "\nON CONFLICT DO NOTHING"

    returns_id = False
    match = _INSERT_TABLE.match(statement)
    if match and match.group(1).lower() in TABLES_WITH_ID and not _RETURNING.search(translated):
        translated = translated.rstrip().rstrip(";") + "\nRETURNING id"
        returns_id = True

    result = (translated, returns_id, boolean_parameter_positions(translated))
    _translation_cache[statement] = result
    return result


def coerce_booleans(
    parameters: Sequence[Any], positions: tuple[int, ...]
) -> tuple[Any, ...]:
    """Turn the 1/0 a SQLite-era call site passes into a real bool."""
    values = list(parameters)
    for index in positions:
        if index < len(values) and values[index] is not None:
            values[index] = bool(values[index])
    return tuple(values)


class Row(dict):
    """A mapping that also answers positional access, the way sqlite3.Row does."""

    __slots__ = ("_order",)

    def __init__(self, mapping: dict[str, Any], order: Sequence[str]) -> None:
        super().__init__(mapping)
        self._order = order

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return super().__getitem__(self._order[key])
        if isinstance(key, slice):
            return [super(Row, self).__getitem__(name) for name in self._order[key]]
        return super().__getitem__(key)

    def keys(self) -> list[str]:  # type: ignore[override]
        return list(self._order)


def _row_factory(cursor: Any) -> Any:
    description = cursor.description
    if description is None:
        return lambda values: values
    order = [column.name for column in description]

    def make(values: Sequence[Any]) -> Row:
        return Row(dict(zip(order, values)), order)

    return make


class Cursor:
    """Wraps a psycopg cursor so it answers .lastrowid like sqlite3 does."""

    def __init__(self, cursor: psycopg.Cursor) -> None:
        self._cursor = cursor
        self.lastrowid: Any = None

    def execute(self, statement: str, parameters: Sequence[Any] = ()) -> "Cursor":
        translated, returns_id, boolean_positions = translate(statement)
        self._cursor.execute(translated, coerce_booleans(parameters, boolean_positions))
        if returns_id:
            row = self._cursor.fetchone()
            if row is not None:
                self.lastrowid = row["id"] if isinstance(row, dict) else row[0]
        return self

    def executemany(self, statement: str, sequence: Iterable[Sequence[Any]]) -> "Cursor":
        translated, _, boolean_positions = translate(statement)
        self._cursor.executemany(
            translated, [coerce_booleans(item, boolean_positions) for item in sequence]
        )
        return self

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return self._cursor.fetchall()

    def fetchmany(self, size: int | None = None) -> list[Any]:
        return self._cursor.fetchmany(size) if size is not None else self._cursor.fetchmany()

    def __iter__(self) -> Any:
        return iter(self._cursor)

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self) -> Any:
        return self._cursor.description

    def close(self) -> None:
        self._cursor.close()


class Connection:
    """The sqlite3.Connection surface that main.py relies on."""

    def __init__(self, dsn: str, *, timeout: float = 30.0) -> None:
        self._connection = psycopg.connect(
            dsn,
            connect_timeout=int(timeout),
            row_factory=_row_factory,
            autocommit=False,
            # psycopg promotes a statement to a server-side prepared one after
            # it has been executed a few times. Supabase's transaction pooler
            # hands each transaction whatever backend is free, so the next
            # execution can land on a connection that has never seen the
            # prepare - or worse, on one where that name is already taken,
            # which raises DuplicatePreparedStatement. The failure is
            # intermittent and load-dependent, so it would not show up until
            # production. None disables the promotion entirely.
            prepare_threshold=None,
        )
        # Assigned by callers that expect sqlite3; harmless here because rows
        # always come back as Row.
        self.row_factory: Any = None

    def execute(self, statement: str, parameters: Sequence[Any] = ()) -> Cursor:
        cursor = Cursor(self._connection.cursor())
        return cursor.execute(statement, parameters)

    def executemany(self, statement: str, sequence: Iterable[Sequence[Any]]) -> Cursor:
        cursor = Cursor(self._connection.cursor())
        return cursor.executemany(statement, sequence)

    def executescript(self, script: str) -> None:
        """Run a multi-statement schema script, as sqlite3 does."""
        for chunk in script.split(";"):
            if chunk.strip():
                self.execute(chunk)

    def cursor(self) -> Cursor:
        return Cursor(self._connection.cursor())

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        if not self._connection.closed:
            self._connection.close()

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        # sqlite3 commits a clean block and rolls back a failed one. The close
        # is this adapter's addition: a pooled Postgres connection left open
        # holds a slot that a serverless host cannot spare.
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self.close()


def connect(dsn: str, *, timeout: float = 30.0) -> Connection:
    return Connection(dsn, timeout=timeout)
