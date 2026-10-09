// copies the static files, the self-hosted fonts and the recorded cases next to the compiled script and writes the api address into config.js
import { copyFileSync, mkdirSync, readdirSync, statSync, writeFileSync } from "node:fs";

mkdirSync("dist/fonts", { recursive: true });
for (const file of ["index.html", "style.css", "_headers"]) copyFileSync(file, `dist/${file}`);
const FONTS = {
  "fraunces.woff2": "@fontsource-variable/fraunces/files/fraunces-latin-full-normal.woff2",
  "geist-400.woff2": "@fontsource/geist-sans/files/geist-sans-latin-400-normal.woff2",
  "geist-500.woff2": "@fontsource/geist-sans/files/geist-sans-latin-500-normal.woff2",
  "geist-600.woff2": "@fontsource/geist-sans/files/geist-sans-latin-600-normal.woff2",
  "geist-mono-400.woff2": "@fontsource/geist-mono/files/geist-mono-latin-400-normal.woff2",
  "geist-mono-500.woff2": "@fontsource/geist-mono/files/geist-mono-latin-500-normal.woff2",
};
for (const [name, from] of Object.entries(FONTS)) {
  copyFileSync(`node_modules/${from}`, `dist/fonts/${name}`);
}
// recorded cases ship with the page, so the console plays at once even while the api is asleep
const REPLAYS = "../fixtures/replay";
const cases = readdirSync(REPLAYS).filter((name) => statSync(`${REPLAYS}/${name}`).isDirectory()).sort();
for (const name of cases) {
  mkdirSync(`dist/replays/${name}`, { recursive: true });
  for (const file of ["events.jsonl", "card.json"]) copyFileSync(`${REPLAYS}/${name}/${file}`, `dist/replays/${name}/${file}`);
}
writeFileSync("dist/replays/index.json", JSON.stringify(cases));
const api = process.env.QUAOAR_API_URL ?? "";
writeFileSync("dist/config.js", `window.QUAOAR_API = ${JSON.stringify(api)};\n`);
