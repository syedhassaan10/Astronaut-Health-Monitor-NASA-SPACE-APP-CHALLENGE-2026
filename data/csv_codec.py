"""Small CSV encoder and parser (RFC 4180), written out by hand so the behaviour is exact:
CRLF line endings for Excel, a UTF-8 byte-order mark, and a guard against spreadsheet formulas."""

import re

# UTF-8 byte-order mark: makes Excel read the file as UTF-8.
BOM = "﻿"

_NEEDS_QUOTES = re.compile(r'[",\r\n]|^\s|\s$')
_DANGEROUS_START = re.compile(r"^[=+\-@\t\r]")
_GUARDED_START = re.compile(r"^'[=+\-@\t\r]")


def encode_cell(value):
    """Quote a cell when it holds a comma, quote, line break or edge whitespace."""
    if _NEEDS_QUOTES.search(value):
        return '"' + value.replace('"', '""') + '"'
    return value


def encode_csv(rows):
    """Rows of cells -> CSV text with CRLF line endings, ending with one CRLF."""
    lines = []
    for row in rows:
        lines.append(",".join(encode_cell(cell) for cell in row))
    return "\r\n".join(lines) + "\r\n"


def parse_csv(text):
    """CSV text -> rows of cells.

    Handles a leading BOM, quoted cells with commas, line breaks and doubled quotes,
    and CRLF, LF or CR line endings. Fully blank lines are skipped.
    Raises ValueError if a quoted cell is never closed.
    """
    if text.startswith(BOM):
        text = text[1:]
    rows = []
    row = []
    cell = []
    in_quotes = False
    i = 0
    n = len(text)

    def end_cell():
        row.append("".join(cell))
        cell.clear()

    def end_row():
        nonlocal row
        end_cell()
        if not (len(row) == 1 and row[0] == ""):
            rows.append(row)
        row = []

    while i < n:
        ch = text[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < n and text[i + 1] == '"':
                    cell.append('"')
                    i += 2
                    continue
                in_quotes = False
            else:
                cell.append(ch)
        elif ch == '"' and not cell:
            in_quotes = True
        elif ch == ",":
            end_cell()
        elif ch == "\r":
            if i + 1 < n and text[i + 1] == "\n":
                i += 1
            end_row()
        elif ch == "\n":
            end_row()
        else:
            cell.append(ch)
        i += 1

    if in_quotes:
        raise ValueError("Malformed CSV: a quoted cell was never closed.")
    if cell or row:
        end_row()
    return rows


def guard_text(value):
    """Spreadsheet formula guard for TEXT cells: a value starting with = + - @ (or tab/CR)
    gets an apostrophe in front, so Excel shows it as text and never runs it."""
    if _DANGEROUS_START.match(value):
        return "'" + value
    return value


def unguard_text(value):
    """Undo guard_text when reading a file back."""
    if _GUARDED_START.match(value):
        return value[1:]
    return value
