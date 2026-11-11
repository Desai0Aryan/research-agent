import { test } from "node:test";
import assert from "node:assert/strict";
import { SSEParser } from "./sse.ts";

test("parses events split across arbitrary chunk boundaries", () => {
  const p = new SSEParser();
  const got: string[] = [];
  for (const piece of ['data: {"a"', ":1}\n", "\ndata: {\"b\":2}\n\nda", 'ta: {"c":3}\n\n']) got.push(...p.push(piece));
  assert.deepEqual(got.map((s) => JSON.parse(s)), [{ a: 1 }, { b: 2 }, { c: 3 }]);
});

test("handles CRLF and ignores comments / blank frames", () => {
  const p = new SSEParser();
  assert.deepEqual(p.push(": keepalive\r\n\r\ndata: x\r\n\r\n"), ["x"]);
});
