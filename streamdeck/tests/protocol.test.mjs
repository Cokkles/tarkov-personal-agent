import assert from "node:assert/strict";
import test from "node:test";

import {
  consumeServerFrames,
  encodeClientFrame,
} from "../com.cokkles.tarkov-personal-agent.sdPlugin/bin/protocol.js";

test("masked client frames round-trip through the parser", () => {
  const encoded = encodeClientFrame(JSON.stringify({ event: "showOk" }));
  const { frames, rest } = consumeServerFrames(encoded);
  assert.equal(rest.length, 0);
  assert.equal(frames.length, 1);
  assert.equal(frames[0].opcode, 1);
  assert.deepEqual(JSON.parse(frames[0].payload.toString("utf8")), {
    event: "showOk",
  });
});

test("the parser preserves incomplete frames", () => {
  const encoded = encodeClientFrame("marker");
  const split = Math.floor(encoded.length / 2);
  const first = consumeServerFrames(encoded.subarray(0, split));
  assert.equal(first.frames.length, 0);
  assert.equal(first.rest.length, split);

  const second = consumeServerFrames(Buffer.concat([first.rest, encoded.subarray(split)]));
  assert.equal(second.frames.length, 1);
  assert.equal(second.frames[0].payload.toString("utf8"), "marker");
  assert.equal(second.rest.length, 0);
});
