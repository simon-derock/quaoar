// copies the static files next to the compiled script and writes the api address into config.js
import { copyFileSync, writeFileSync, mkdirSync } from "node:fs";

mkdirSync("dist", { recursive: true });
for (const file of ["index.html", "style.css", "_headers"]) copyFileSync(file, `dist/${file}`);
const api = process.env.QUAOAR_API_URL ?? "";
writeFileSync("dist/config.js", `window.QUAOAR_API = ${JSON.stringify(api)};\n`);
