// copies the static files and the self-hosted fonts next to the compiled script and writes the api address into config.js
import { copyFileSync, writeFileSync, mkdirSync } from "node:fs";

mkdirSync("dist/fonts", { recursive: true });
for (const file of ["index.html", "style.css", "_headers"]) copyFileSync(file, `dist/${file}`);
const FONTS = {
  "fraunces.woff2": "@fontsource-variable/fraunces/files/fraunces-latin-full-normal.woff2",
  "fraunces-italic.woff2": "@fontsource-variable/fraunces/files/fraunces-latin-full-italic.woff2",
  "geist-400.woff2": "@fontsource/geist-sans/files/geist-sans-latin-400-normal.woff2",
  "geist-500.woff2": "@fontsource/geist-sans/files/geist-sans-latin-500-normal.woff2",
  "geist-600.woff2": "@fontsource/geist-sans/files/geist-sans-latin-600-normal.woff2",
  "geist-mono-400.woff2": "@fontsource/geist-mono/files/geist-mono-latin-400-normal.woff2",
  "geist-mono-500.woff2": "@fontsource/geist-mono/files/geist-mono-latin-500-normal.woff2",
};
for (const [name, from] of Object.entries(FONTS)) {
  copyFileSync(`node_modules/${from}`, `dist/fonts/${name}`);
}
const api = process.env.QUAOAR_API_URL ?? "";
writeFileSync("dist/config.js", `window.QUAOAR_API = ${JSON.stringify(api)};\n`);
