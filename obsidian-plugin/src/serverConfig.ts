// Pure helpers for starting the Oracle server from the plugin (no Obsidian or Node imports, so they
// can be unit tested with `node --test`).

export interface StartOptions {
  oracleDir: string; // the cloned oracle repository
  pythonPath: string; // "" = the repository's .venv
  serverUrl: string;
  vaultPath: string;
  vaultName: string;
  parentPid: number; // Obsidian's process; the server exits when it does
  platform: string; // process.platform
}

export interface ServerCommand {
  command: string;
  args: string[];
  cwd: string;
  dbDir: string;
  port: number;
}

/** "My Notes!" -> "my-notes": safe for a folder name. */
export function slug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "vault";
}

/** Port of a localhost http URL, or null if the URL isn't a local server the plugin could start. */
export function localPort(url: string): number | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname);
  if (parsed.protocol !== "http:" || !local) return null;
  return parsed.port ? Number(parsed.port) : 80;
}

/** The command that starts the server for this vault, or an explanation of what's missing. */
export function serverCommand(options: StartOptions): ServerCommand | { error: string } {
  const sep = options.platform === "win32" ? "\\" : "/";
  const dir = options.oracleDir.trim().replace(/[\\/]+$/, "");
  if (!dir) return { error: "Set the Oracle folder in the plugin settings to start the server automatically." };
  const port = localPort(options.serverUrl);
  if (port === null) return { error: "Automatic start only works with a local server address (http://localhost:PORT)." };

  const defaultPython = options.platform === "win32" ? `${dir}\\.venv\\Scripts\\python.exe` : `${dir}/.venv/bin/python`;
  // One index per vault, so switching vaults never mixes or deletes another vault's index.
  const dbDir = `${dir}${sep}chroma-${slug(options.vaultName)}`;
  return {
    command: options.pythonPath.trim() || defaultPython,
    args: [
      `src${sep}server.py`,
      "--vault", options.vaultPath,
      "--db", dbDir,
      "--port", String(port),
      "--exit-with-parent", String(options.parentPid),
    ],
    cwd: dir,
    dbDir,
    port,
  };
}
