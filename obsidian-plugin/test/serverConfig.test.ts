import assert from "node:assert/strict";
import { test } from "node:test";
import { localPort, serverCommand, slug, type StartOptions } from "../src/serverConfig.ts";

const options: StartOptions = {
  oracleDir: "/home/me/Projects/oracle/",
  pythonPath: "",
  serverUrl: "http://localhost:8000",
  vaultPath: "/home/me/Notes/My Vault",
  vaultName: "My Vault",
  parentPid: 4242,
  platform: "linux",
};

test("slug makes vault names safe for folder names", () => {
  assert.equal(slug("My Vault"), "my-vault");
  assert.equal(slug("LISA"), "lisa");
  assert.equal(slug("  Notes (2026)!  "), "notes-2026");
  assert.equal(slug("!!!"), "vault");
});

test("localPort only accepts local http addresses", () => {
  assert.equal(localPort("http://localhost:8000"), 8000);
  assert.equal(localPort("http://127.0.0.1:9001/"), 9001);
  assert.equal(localPort("http://localhost"), 80);
  assert.equal(localPort("https://localhost:8000"), null);
  assert.equal(localPort("http://192.168.1.5:8000"), null);
  assert.equal(localPort("not a url"), null);
});

test("serverCommand builds the start command with one index per vault", () => {
  assert.deepEqual(serverCommand(options), {
    command: "/home/me/Projects/oracle/.venv/bin/python",
    args: [
      "src/server.py",
      "--vault", "/home/me/Notes/My Vault",
      "--db", "/home/me/Projects/oracle/chroma-my-vault",
      "--port", "8000",
      "--exit-with-parent", "4242",
    ],
    cwd: "/home/me/Projects/oracle",
    dbDir: "/home/me/Projects/oracle/chroma-my-vault",
    port: 8000,
  });
});

test("serverCommand uses a custom Python and Windows paths", () => {
  const custom = serverCommand({ ...options, pythonPath: "/usr/bin/python3" });
  assert.ok(!("error" in custom) && custom.command === "/usr/bin/python3");

  const windows = serverCommand({ ...options, oracleDir: "C:\\code\\oracle", platform: "win32" });
  assert.ok(!("error" in windows));
  assert.equal(windows.command, "C:\\code\\oracle\\.venv\\Scripts\\python.exe");
  assert.equal(windows.dbDir, "C:\\code\\oracle\\chroma-my-vault");
});

test("serverCommand explains what's missing", () => {
  assert.match((serverCommand({ ...options, oracleDir: " " }) as { error: string }).error, /Oracle folder/);
  assert.match((serverCommand({ ...options, serverUrl: "http://example.com:8000" }) as { error: string }).error, /local/);
});
