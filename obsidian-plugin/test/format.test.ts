// Run with `npm test` (Node runs TypeScript directly; no Obsidian needed).
import assert from "node:assert/strict";
import { test } from "node:test";
import { label, linktext, segments } from "../src/format.ts";

test("segments splits text, bold, and citations", () => {
  assert.deepEqual(segments("Use **0.001** with Adam [1][2].", 2), [
    { kind: "text", text: "Use " },
    { kind: "bold", text: "0.001" },
    { kind: "text", text: " with Adam " },
    { kind: "cite", n: 1 },
    { kind: "cite", n: 2 },
    { kind: "text", text: "." },
  ]);
});

test("segments leaves citations to missing sources as plain text", () => {
  assert.deepEqual(segments("See [3] and [0].", 2), [
    { kind: "text", text: "See " },
    { kind: "text", text: "[3]" },
    { kind: "text", text: " and " },
    { kind: "text", text: "[0]" },
    { kind: "text", text: "." },
  ]);
});

test("linktext opens the deepest heading of the section", () => {
  assert.equal(linktext({ note: "AI/Gradient Descent.md", heading: "Learning rate" }), "AI/Gradient Descent#Learning rate");
  assert.equal(linktext({ note: "Scala/Implicits and Givens.md", heading: "Scala 3 > given / using" }), "Scala/Implicits and Givens#given / using");
  assert.equal(linktext({ note: "Reading List.md", heading: "" }), "Reading List");
});

test("label shows the title and heading path", () => {
  assert.equal(label({ title: "Gradient Descent", heading: "Learning rate" }), "Gradient Descent › Learning rate");
  assert.equal(label({ title: "Notes", heading: "A > B" }), "Notes › A › B");
  assert.equal(label({ title: "Reading List", heading: "" }), "Reading List");
});
