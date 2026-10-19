// Oracle for Obsidian: a sidebar panel that asks questions of (and searches) this vault through the
// local Oracle server, plus automatic re-indexing when notes change.
import {
  App,
  FileSystemAdapter,
  ItemView,
  Keymap,
  Notice,
  Plugin,
  PluginSettingTab,
  Setting,
  TAbstractFile,
  TFile,
  WorkspaceLeaf,
  setIcon,
} from "obsidian";
import { OracleClient } from "./api.ts";
import { type AskResult, type Hit, label, linktext, segments } from "./format.ts";

const VIEW_TYPE = "oracle-view";
const SEARCH_DELAY_MS = 250;

interface OracleSettings {
  serverUrl: string;
  autoReindex: boolean;
  reindexDelaySeconds: number;
}

const DEFAULT_SETTINGS: OracleSettings = {
  serverUrl: "http://localhost:8000",
  autoReindex: true,
  reindexDelaySeconds: 5,
};

export default class OraclePlugin extends Plugin {
  settings: OracleSettings = DEFAULT_SETTINGS;
  client = new OracleClient(() => this.settings.serverUrl);
  private reindexTimer: number | undefined;

  async onload() {
    this.settings = { ...DEFAULT_SETTINGS, ...(await this.loadData()) };

    this.registerView(VIEW_TYPE, (leaf) => new OracleView(leaf, this));
    this.addRibbonIcon("message-square", "Open Oracle", () => this.activateView());
    this.addCommand({ id: "open", name: "Open panel", callback: () => this.activateView() });
    this.addCommand({ id: "reindex", name: "Re-index vault", callback: () => this.reindex(true) });
    this.addSettingTab(new OracleSettingTab(this.app, this));

    // Obsidian reports every existing file as "created" while it loads, so only listen once that's done.
    this.app.workspace.onLayoutReady(() => {
      const onChange = (file: TAbstractFile) => {
        if (file instanceof TFile && file.extension === "md") this.scheduleReindex();
      };
      this.registerEvent(this.app.vault.on("modify", onChange));
      this.registerEvent(this.app.vault.on("create", onChange));
      this.registerEvent(this.app.vault.on("delete", onChange));
      this.registerEvent(this.app.vault.on("rename", onChange));
    });
  }

  onunload() {
    window.clearTimeout(this.reindexTimer);
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  async activateView() {
    const { workspace } = this.app;
    let leaf = workspace.getLeavesOfType(VIEW_TYPE)[0];
    if (!leaf) {
      const right = workspace.getRightLeaf(false);
      if (!right) return;
      await right.setViewState({ type: VIEW_TYPE, active: true });
      leaf = right;
    }
    await workspace.revealLeaf(leaf);
  }

  /** Re-index after edits settle, so typing doesn't trigger a re-index per keystroke. */
  private scheduleReindex() {
    if (!this.settings.autoReindex) return;
    window.clearTimeout(this.reindexTimer);
    this.reindexTimer = window.setTimeout(() => this.reindex(false), this.settings.reindexDelaySeconds * 1000);
  }

  async reindex(announce: boolean) {
    try {
      const result = await this.client.reindex();
      if (announce) new Notice(`Oracle: ${result.updated} notes re-indexed, ${result.chunks} chunks.`);
      this.app.workspace.getLeavesOfType(VIEW_TYPE).forEach((leaf) => {
        if (leaf.view instanceof OracleView) leaf.view.refreshStatus();
      });
    } catch {
      if (announce) new Notice("Oracle: server not reachable, so nothing was re-indexed.");
    }
  }

  /** Command to start the server for this vault, shown when it isn't running. */
  startCommand(): string {
    const adapter = this.app.vault.adapter;
    const path = adapter instanceof FileSystemAdapter ? adapter.getBasePath() : "<path to this vault>";
    return `python src/server.py --vault "${path}"`;
  }
}

class OracleView extends ItemView {
  private mode: "ask" | "search" = "ask";
  private cancelAsk: (() => void) | null = null;
  private searchTimer: number | undefined;

  private statusEl!: HTMLElement;
  private tabButtons!: Record<"ask" | "search", HTMLButtonElement>;
  private inputEl!: HTMLInputElement;
  private submitEl!: HTMLButtonElement;
  private answerEl!: HTMLElement;
  private warningEl!: HTMLElement;
  private metaEl!: HTMLElement;
  private listEl!: HTMLOListElement;

  constructor(leaf: WorkspaceLeaf, private readonly plugin: OraclePlugin) {
    super(leaf);
  }

  getViewType() {
    return VIEW_TYPE;
  }

  getDisplayText() {
    return "Oracle";
  }

  getIcon() {
    return "message-square";
  }

  async onOpen() {
    const root = this.contentEl;
    root.empty();
    root.addClass("oracle-view");

    const header = root.createDiv({ cls: "oracle-header" });
    this.statusEl = header.createSpan({ cls: "oracle-status", text: "Connecting…" });
    const reindexButton = header.createEl("button", { cls: "clickable-icon", attr: { "aria-label": "Re-index vault" } });
    setIcon(reindexButton, "refresh-cw");
    reindexButton.onclick = () => this.plugin.reindex(true);

    const tabs = root.createDiv({ cls: "oracle-tabs" });
    this.tabButtons = {
      ask: tabs.createEl("button", { text: "Ask" }),
      search: tabs.createEl("button", { text: "Search" }),
    };
    this.tabButtons.ask.onclick = () => this.setMode("ask");
    this.tabButtons.search.onclick = () => this.setMode("search");

    const form = root.createEl("form", { cls: "oracle-form" });
    this.inputEl = form.createEl("input", { type: "text" });
    this.submitEl = form.createEl("button", { cls: "mod-cta", attr: { type: "submit" } });
    form.onsubmit = (e) => {
      e.preventDefault();
      this.submit();
    };
    this.inputEl.oninput = () => this.onType();

    this.answerEl = root.createDiv({ cls: "oracle-answer" });
    this.warningEl = root.createDiv({ cls: "oracle-warning" });
    this.metaEl = root.createDiv({ cls: "oracle-meta" });
    this.listEl = root.createEl("ol", { cls: "oracle-results" });

    this.setMode("ask");
    await this.refreshStatus();
  }

  async onClose() {
    this.cancelAsk?.();
    window.clearTimeout(this.searchTimer);
  }

  async refreshStatus() {
    try {
      const health = await this.plugin.client.health();
      const thisVault = this.app.vault.getName();
      if (health.vault !== thisVault) {
        this.statusEl.setText(`⚠ Server is indexing "${health.vault}", not "${thisVault}"`);
      } else {
        this.statusEl.setText(`${health.chunks} chunks · ${health.llm_model}`);
      }
    } catch {
      this.statusEl.setText("Server not running");
      this.reset();
      this.metaEl.setText(`Start the Oracle server from the oracle folder:\n${this.plugin.startCommand()}`);
    }
  }

  private setMode(mode: "ask" | "search") {
    this.mode = mode;
    for (const [name, button] of Object.entries(this.tabButtons)) button.toggleClass("is-active", name === mode);
    this.submitEl.setText(mode === "ask" ? "Ask" : "Search");
    this.inputEl.placeholder = mode === "ask" ? "Ask about your notes…" : "Search by meaning and keywords…";
    this.reset();
    this.inputEl.focus();
  }

  private reset() {
    this.cancelAsk?.();
    this.cancelAsk = null;
    this.answerEl.empty();
    this.warningEl.empty();
    this.metaEl.empty();
    this.listEl.empty();
    this.submitEl.disabled = false;
  }

  private submit() {
    const q = this.inputEl.value.trim();
    if (!q) return;
    if (this.mode === "ask") this.ask(q);
    else void this.search(q);
  }

  private onType() {
    if (this.mode !== "search") return;
    window.clearTimeout(this.searchTimer);
    const q = this.inputEl.value.trim();
    if (q) this.searchTimer = window.setTimeout(() => void this.search(q), SEARCH_DELAY_MS);
  }

  private ask(q: string) {
    this.reset();
    this.submitEl.disabled = true;
    this.metaEl.setText("Searching your notes and writing an answer…");
    const started = performance.now();

    this.cancelAsk = this.plugin.client.ask(q, {
      onToken: (piece) => this.answerEl.appendText(piece),
      onDone: (result) => {
        this.cancelAsk = null;
        this.submitEl.disabled = false;
        this.showAnswer(result, (performance.now() - started) / 1000);
      },
      onError: () => {
        this.cancelAsk = null;
        this.submitEl.disabled = false;
        void this.refreshStatus();
        this.metaEl.setText("Lost connection to the Oracle server. Is it still running?");
      },
    });
  }

  private showAnswer(result: AskResult, seconds: number) {
    // Replace the streamed plain text with the final text: bold, and clickable [n] citations.
    this.answerEl.empty();
    for (const part of segments(result.text, result.sources.length)) {
      if (part.kind === "text") this.answerEl.appendText(part.text);
      else if (part.kind === "bold") this.answerEl.createEl("strong", { text: part.text });
      else {
        const hit = result.sources[part.n - 1];
        const cite = this.answerEl.createEl("a", { cls: "oracle-cite", text: String(part.n), attr: { title: label(hit) } });
        cite.onclick = (e) => this.openHit(hit, e);
      }
    }
    if (result.unsupported.length) {
      this.warningEl.setText(
        `⚠ Not found in your notes (may come from the model's own knowledge): ${result.unsupported.join(", ")}`,
      );
    }
    this.metaEl.setText(`${seconds.toFixed(1)}s · ${result.cited.length} of ${result.sources.length} sources cited`);
    result.sources.forEach((hit, i) => this.addResult(hit, i + 1, result.cited.includes(i + 1)));
  }

  private async search(q: string) {
    const started = performance.now();
    try {
      const results = await this.plugin.client.search(q);
      if (this.mode !== "search" || this.inputEl.value.trim() !== q) return; // a newer search is coming
      this.reset();
      this.metaEl.setText(`${results.length} results · ${Math.round(performance.now() - started)} ms`);
      results.forEach((hit) => this.addResult(hit));
    } catch {
      await this.refreshStatus();
    }
  }

  private addResult(hit: Hit, number?: number, cited = false) {
    const item = this.listEl.createEl("li", { cls: cited ? "oracle-cited" : "" });
    const title = item.createEl("a", { cls: "oracle-result-title", text: number ? `[${number}] ${label(hit)}` : label(hit) });
    title.onclick = (e) => this.openHit(hit, e);
    item.createSpan({ cls: "oracle-badge", text: hit.via });
    const details = item.createEl("details");
    details.createEl("summary", { text: "Excerpt" });
    details.createEl("pre", { text: hit.text });
  }

  /** Open the note at the hit's section; Ctrl/Cmd-click opens it in a new tab. */
  private openHit(hit: Hit, event: MouseEvent) {
    void this.app.workspace.openLinkText(linktext(hit), "", Keymap.isModEvent(event));
  }
}

class OracleSettingTab extends PluginSettingTab {
  constructor(app: App, private readonly plugin: OraclePlugin) {
    super(app, plugin);
  }

  display() {
    const { containerEl } = this;
    containerEl.empty();

    new Setting(containerEl)
      .setName("Server address")
      .setDesc("Where the Oracle server is running (python src/server.py).")
      .addText((text) =>
        text
          .setPlaceholder(DEFAULT_SETTINGS.serverUrl)
          .setValue(this.plugin.settings.serverUrl)
          .onChange(async (value) => {
            this.plugin.settings.serverUrl = value.trim() || DEFAULT_SETTINGS.serverUrl;
            await this.plugin.saveSettings();
          }),
      );

    new Setting(containerEl)
      .setName("Re-index automatically")
      .setDesc("Update the index shortly after notes are edited, created, renamed, or deleted.")
      .addToggle((toggle) =>
        toggle.setValue(this.plugin.settings.autoReindex).onChange(async (value) => {
          this.plugin.settings.autoReindex = value;
          await this.plugin.saveSettings();
        }),
      );

    new Setting(containerEl)
      .setName("Re-index delay (seconds)")
      .setDesc("Wait this long after the last change before re-indexing.")
      .addText((text) =>
        text.setValue(String(this.plugin.settings.reindexDelaySeconds)).onChange(async (value) => {
          const seconds = Number(value);
          if (Number.isFinite(seconds) && seconds >= 1) {
            this.plugin.settings.reindexDelaySeconds = seconds;
            await this.plugin.saveSettings();
          }
        }),
      );
  }
}
