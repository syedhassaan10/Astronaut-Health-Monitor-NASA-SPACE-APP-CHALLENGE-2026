// gzip helpers built on the browser's own CompressionStream (no library, no network).

export async function gzipText(text: string): Promise<Blob> {
  const stream = new Blob([text]).stream().pipeThrough(new CompressionStream('gzip'))
  return new Response(stream).blob()
}

/** Reads a stream into text, aborting if more than `maxBytes` come out (guards against gzip bombs). */
async function readCapped(stream: ReadableStream<Uint8Array>, maxBytes: number): Promise<string> {
  const reader = stream.getReader()
  const chunks: Uint8Array[] = []
  let total = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    total += value.byteLength
    if (total > maxBytes) {
      await reader.cancel()
      throw new Error('File is too large once decompressed.')
    }
    chunks.push(value)
  }
  // ignoreBOM keeps a leading BOM in the text so the round-trip is exact (parseCsv strips it).
  return new TextDecoder('utf-8', { ignoreBOM: true }).decode(await new Blob(chunks as BlobPart[]).arrayBuffer())
}

/** Reads a CSV or gzipped CSV (detected by the gzip magic bytes 1f 8b, not the file name). */
export async function readTextMaybeGzip(file: Blob, maxBytes = 60_000_000): Promise<string> {
  const head = new Uint8Array(await file.slice(0, 2).arrayBuffer())
  if (head[0] === 0x1f && head[1] === 0x8b) {
    return readCapped(file.stream().pipeThrough(new DecompressionStream('gzip')), maxBytes)
  }
  if (file.size > maxBytes) throw new Error('File is too large to import.')
  return readCapped(file.stream(), maxBytes)
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}
