// Minimal RFC 4180 CSV encoder/decoder (no dependencies).

/** UTF-8 byte-order mark: makes Excel read the file as UTF-8 instead of the system code page. */
export const BOM = '﻿'

/** Quotes a cell when it contains a comma, quote, CR/LF or edge whitespace. */
export function encodeCell(value: string): string {
  return /[",\r\n]|^\s|\s$/.test(value) ? `"${value.replace(/"/g, '""')}"` : value
}

/** Rows to CSV text with CRLF line endings (what Excel expects). */
export function encodeCsv(rows: string[][]): string {
  return rows.map((r) => r.map(encodeCell).join(',')).join('\r\n') + '\r\n'
}

/**
 * Parses CSV text into rows of cells. Handles a leading BOM, quoted cells with embedded
 * commas / newlines / doubled quotes, and CRLF, LF or CR line endings. Fully blank lines are skipped.
 */
export function parseCsv(input: string): string[][] {
  const text = input.charCodeAt(0) === 0xfeff ? input.slice(1) : input
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let inQuotes = false
  let i = 0
  const endCell = () => {
    row.push(cell)
    cell = ''
  }
  const endRow = () => {
    endCell()
    if (!(row.length === 1 && row[0] === '')) rows.push(row)
    row = []
  }
  while (i < text.length) {
    const ch = text[i]
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cell += '"'
          i += 2
          continue
        }
        inQuotes = false
      } else {
        cell += ch
      }
    } else if (ch === '"' && cell === '') {
      inQuotes = true
    } else if (ch === ',') {
      endCell()
    } else if (ch === '\r') {
      if (text[i + 1] === '\n') i++
      endRow()
    } else if (ch === '\n') {
      endRow()
    } else {
      cell += ch
    }
    i++
  }
  if (inQuotes) throw new Error('Malformed CSV: a quoted cell was never closed.')
  if (cell !== '' || row.length > 0) endRow()
  return rows
}

/**
 * Spreadsheet formula-injection guard for TEXT cells: a value starting with = + - @ (or a
 * tab / CR) is prefixed with an apostrophe so Excel treats it as text, never as a formula.
 */
export function guardText(s: string): string {
  return /^[=+\-@\t\r]/.test(s) ? `'${s}` : s
}

/** Reverses guardText when reading a file back in. */
export function unguardText(s: string): string {
  return /^'[=+\-@\t\r]/.test(s) ? s.slice(1) : s
}
