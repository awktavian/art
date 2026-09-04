/**
 * Load a `lib/*.js` browser script into a sandbox and return its `window`.
 *
 * The shared libraries are plain <script> files, not ES modules: they attach
 * their exports to `window`. Node cannot `import` them (the package is
 * "type": "module", so a bare .js is parsed as ESM and the top-level `class`
 * declarations never reach `window`). Running them in a vm context with a real
 * `window` object is the only way to exercise the code the browser executes.
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

export function loadBrowserLib(relativePath, extraGlobals = {}) {
  const window = {};
  const context = vm.createContext({
    window,
    console,
    URL,
    URLSearchParams,
    location: { hostname: "localhost", pathname: "/" },
    localStorage: null,
    ...extraGlobals,
  });
  context.globalThis = context;
  vm.runInContext(readFileSync(resolve(REPO, relativePath), "utf8"), context, {
    filename: relativePath,
  });
  return window;
}
