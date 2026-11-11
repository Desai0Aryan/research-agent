import { test } from "node:test";
import assert from "node:assert/strict";
import { locateQuote } from "./text.ts";

test("finds quote ignoring case and whitespace differences", () => {
  const r = locateQuote("Intro.  The cat\n sat on the MAT. Outro", "the cat sat on the mat");
  assert.ok(r);
  assert.equal(r![1], "The cat\n sat on the MAT");
  assert.equal(r![0], "Intro.  ");
});

test("returns null when absent or empty, and escapes regex characters", () => {
  assert.equal(locateQuote("abc", "xyz"), null);
  assert.equal(locateQuote("abc", ""), null);
  assert.ok(locateQuote("sum 1/(k+rank) here", "1/(k+rank)"));
});
