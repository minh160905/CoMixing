import { copyFile, mkdir } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const output = new URL("dist/", root);
await mkdir(new URL("assets/", output), { recursive: true });

const files = ["index.html", "style.css", "game.mjs", "board.mjs"];
await Promise.all([
  ...files.map((name) => copyFile(new URL("web/" + name, root), new URL(name, output))),
  copyFile(
    new URL("co_xam/assets/western-pieces.png", root),
    new URL("assets/western-pieces.png", output),
  ),
]);
console.log("Browser game built in dist/");
