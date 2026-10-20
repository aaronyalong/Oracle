// Starts and stops the Oracle server as a child process of Obsidian (desktop only).
import { type ChildProcess, spawn } from "child_process";
import { existsSync } from "fs";
import { join } from "path";
import type { ServerCommand } from "./serverConfig.ts";

export type ServerState =
  | { kind: "stopped" }
  | { kind: "starting" }
  | { kind: "running"; startedByPlugin: boolean }
  | { kind: "failed"; message: string; log: string };

const POLL_MS = 1000;
// The first start indexes the whole vault, which can take minutes for a large one.
const START_TIMEOUT_MS = 15 * 60 * 1000;
const LOG_LINES = 20;

export class ServerProcess {
  state: ServerState = { kind: "stopped" };
  private child: ChildProcess | null = null;
  private log: string[] = [];

  private readonly onChange: (state: ServerState) => void;

  // Written out (not `constructor(private onChange)`) so Node can run this file directly in tests.
  constructor(onChange: (state: ServerState) => void) {
    this.onChange = onChange;
  }

  private setState(state: ServerState) {
    this.state = state;
    this.onChange(state);
  }

  private fail(message: string) {
    this.setState({ kind: "failed", message, log: this.log.join("\n") });
  }

  /** Start the server unless one is already answering; resolves once it's ready or has failed. */
  async start(command: ServerCommand, isUp: () => Promise<boolean>): Promise<void> {
    if (this.child || this.state.kind === "starting") return;
    if (await isUp()) {
      this.setState({ kind: "running", startedByPlugin: false });
      return;
    }
    this.log = [];
    if (!existsSync(join(command.cwd, "src", "server.py"))) {
      return this.fail(`No src/server.py in "${command.cwd}". Check the Oracle folder in the plugin settings.`);
    }
    if (!existsSync(command.command)) {
      return this.fail(`Python not found at "${command.command}". Create the virtual environment or set the Python path.`);
    }

    this.setState({ kind: "starting" });
    const child = spawn(command.command, command.args, {
      cwd: command.cwd,
      env: { ...process.env, PYTHONUNBUFFERED: "1", PYTHONWARNINGS: "ignore::DeprecationWarning" },
    });
    this.child = child;

    const capture = (data: Buffer) => {
      this.log.push(...data.toString().split("\n").filter((line) => line.trim()));
      this.log = this.log.slice(-LOG_LINES);
    };
    child.stdout?.on("data", capture);
    child.stderr?.on("data", capture);
    child.on("error", (err) => this.log.push(String(err)));

    let exitCode: number | null | undefined;
    child.on("exit", (code) => {
      exitCode = code;
      if (this.child === child) this.child = null;
      // Exiting after stop() is expected; exiting on its own is a failure worth showing.
      if (this.state.kind !== "stopped") this.fail(`The server stopped (exit code ${code}).`);
    });

    const deadline = Date.now() + START_TIMEOUT_MS;
    while (exitCode === undefined && Date.now() < deadline) {
      if (await isUp()) {
        this.setState({ kind: "running", startedByPlugin: true });
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    }
    if (exitCode === undefined) {
      this.stop();
      this.fail("The server didn't become ready in time.");
    }
  }

  /** Stop the server if this plugin started it. A server you started yourself is left running. */
  stop() {
    const child = this.child;
    this.child = null;
    if (!child) return;
    this.setState({ kind: "stopped" });
    child.kill("SIGTERM");
  }
}
