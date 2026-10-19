// Bundles src/main.ts into the main.js Obsidian loads, next to manifest.json and styles.css.
// `npm run dev` rebuilds on every change; reload Obsidian (Ctrl+R) to pick it up.
import esbuild from "esbuild";
import { copyFileSync, mkdirSync } from "node:fs";
import { builtinModules } from "node:module";
import { join } from "node:path";

const watch = process.argv.includes("--watch");
// Where Obsidian loads the plugin from: the repo's sample vault unless OBSIDIAN_PLUGIN_DIR says otherwise.
const outDir = process.env.OBSIDIAN_PLUGIN_DIR ?? "../sample-vault/.obsidian/plugins/oracle";

const copyStaticFiles = {
  name: "copy-static-files",
  setup(build) {
    build.onEnd(() => {
      mkdirSync(outDir, { recursive: true });
      for (const file of ["manifest.json", "styles.css"]) copyFileSync(file, join(outDir, file));
    });
  },
};

const context = await esbuild.context({
  entryPoints: ["src/main.ts"],
  outfile: join(outDir, "main.js"),
  bundle: true,
  format: "cjs",
  target: "es2020",
  // Provided by Obsidian at runtime, so not bundled.
  external: ["obsidian", "electron", "@codemirror/*", "@lezer/*", ...builtinModules],
  sourcemap: watch ? "inline" : false,
  logLevel: "info",
  plugins: [copyStaticFiles],
});

if (watch) {
  await context.watch();
} else {
  await context.rebuild();
  await context.dispose();
}
