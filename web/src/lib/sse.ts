/** Incremental Server-Sent-Events parser. Feed it arbitrary text chunks; it returns complete `data:` payloads. */
export class SSEParser {
  private buf = "";
  push(chunk: string): string[] {
    this.buf += chunk;
    const out: string[] = [];
    let idx: number;
    while ((idx = this.buf.search(/\r?\n\r?\n/)) !== -1) {
      const block = this.buf.slice(0, idx);
      this.buf = this.buf.slice(idx).replace(/^\r?\n\r?\n/, "");
      const data = block.split(/\r?\n/).filter((l) => l.startsWith("data:")).map((l) => l.slice(5).replace(/^ /, "")).join("\n");
      if (data) out.push(data);
    }
    return out;
  }
}
