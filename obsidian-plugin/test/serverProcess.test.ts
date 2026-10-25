import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import type { ServerCommand } from "../src/serverConfig.ts";
import { ServerProcess, type ServerState } from "../src/serverProcess.ts";

/** A folder that passes the "is this the Oracle folder" check; `sh -c script` stands in for the server. */
function fakeServer(script: string): ServerCommand {
  const dir = mkdtempSync(join(tmpdir(), "oracle-"));
  mkdirSync(join(dir, "src"));
  writeFileSync(join(dir, "src", "server.py"), "");
  return { command: "/bin/sh", args: ["-c", script], cwd: dir, dbDir: join(dir, "db"), port: 8000 };
}

function recorder(startTimeoutMs?: number) {
  const states: ServerState[] = [];
  return { states, server: new ServerProcess((state) => states.push(state), startTimeoutMs) };
}

const neverUp = async () => false;

test("a wrong Oracle folder fails once, naming the folder", async () => {
  const { states, server } = recorder();
  await server.start({ ...fakeServer("exit 0"), cwd: "/no/such/oracle" }, neverUp);
  assert.equal(states.length, 1);
  assert.equal(states[0].kind, "failed");
  assert.match((states[0] as { message: string }).message, /\/no\/such\/oracle/);
});

test("a server that exits on its own fails once, with its exit code and output", async () => {
  const { states, server } = recorder();
  await server.start(fakeServer("echo 'Traceback: boom' >&2; exit 3"), neverUp);
  assert.deepEqual(states.map((s) => s.kind), ["starting", "failed"]);
  const failed = states[1] as { message: string; log: string };
  assert.match(failed.message, /exit code 3/);
  assert.match(failed.log, /boom/);
});

test("stopping a starting server is not reported as a failure", async () => {
  const { states, server } = recorder();
  const starting = server.start(fakeServer("sleep 30"), neverUp);
  while (server.state.kind !== "starting") await new Promise((resolve) => setTimeout(resolve, 10));
  server.stop();
  await starting;
  assert.deepEqual(states.map((s) => s.kind), ["starting", "stopped"]);
});

test("a server that never becomes ready fails once, saying so", async () => {
  const { states, server } = recorder(500);
  await server.start(fakeServer("sleep 30"), neverUp);
  await new Promise((resolve) => setTimeout(resolve, 200)); // let the killed process's exit arrive
  assert.deepEqual(states.map((s) => s.kind), ["starting", "stopped", "failed"]);
  assert.match((states[2] as { message: string }).message, /didn't become ready in time/);
});

test("a server that is already running is reused, not started", async () => {
  const { states, server } = recorder();
  await server.start(fakeServer("exit 1"), async () => true);
  assert.deepEqual(states, [{ kind: "running", startedByPlugin: false }]);
});
