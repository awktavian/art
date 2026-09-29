import { expect, test } from "@playwright/test";

const SITE_ORIGIN = "http://127.0.0.1:4173";

function monitorRuntime(page) {
  const failures = [];
  page.on("pageerror", (error) => failures.push(`pageerror: ${error.message}`));
  page.on("requestfailed", (request) => {
    const url = new URL(request.url());
    if (url.origin === SITE_ORIGIN && url.pathname.startsWith("/art/")) {
      failures.push(
        `requestfailed: ${url.pathname} (${request.failure()?.errorText ?? "unknown"})`,
      );
    }
  });
  page.on("response", (response) => {
    const url = new URL(response.url());
    if (
      url.origin === SITE_ORIGIN &&
      url.pathname.startsWith("/art/") &&
      response.status() >= 400
    ) {
      failures.push(`response: ${response.status()} ${url.pathname}`);
    }
  });
  return () => expect(failures, failures.join("\n")).toEqual([]);
}

test("directory is keyboard-operable and exposes named controls", async ({ page }) => {
  const assertRuntimeClean = monitorRuntime(page);
  await page.goto("/art/", { waitUntil: "load" });

  await expect(page).toHaveTitle(/The Art Directory/);
  await expect(page.locator("html")).toHaveAttribute("lang", /.+/);
  await expect(page.getByRole("link", { name: "Skip to apps" })).toHaveAttribute("href", /.+/);
  await expect(page.getByRole("main")).toBeVisible();
  const cardCount = await page.locator("a.card").count();
  await expect(page.getByRole("status")).toHaveText(`${cardCount} apps`);
  await expect(page.locator("footer")).toContainText(`${cardCount} works`);
  await expect(page.locator("img:not([alt])")).toHaveCount(0);

  const unnamedControls = await page
    .locator("a, button, input, select, textarea")
    .evaluateAll((elements) =>
      elements
        .filter((element) => {
          if (element.hidden || element.getAttribute("aria-hidden") === "true") return false;
          const labelledBy = element.getAttribute("aria-labelledby");
          const labelledText = labelledBy
            ? labelledBy
                .split(/\s+/)
                .map((id) => document.getElementById(id)?.textContent ?? "")
                .join(" ")
            : "";
          const name =
            element.getAttribute("aria-label") ||
            labelledText ||
            element.textContent ||
            element.getAttribute("title") ||
            element.getAttribute("placeholder") ||
            element.getAttribute("alt");
          return !name?.trim();
        })
        .map((element) => element.outerHTML.slice(0, 160)),
    );
  expect(unnamedControls).toEqual([]);

  const filter = page.getByRole("searchbox", { name: "Filter apps by name or description" });
  const initialStatus = `${cardCount} apps`;
  await page.keyboard.press("/");
  await expect(filter).toBeFocused();
  await filter.fill("catastrophe");
  await expect(page.getByRole("status")).not.toHaveText(initialStatus);
  await page.keyboard.press("ArrowDown");
  await expect(page.locator("a.card:visible").first()).toBeFocused();
  assertRuntimeClean();
});

test("representative interactive routes load without local runtime failures", async ({ page }) => {
  const assertRuntimeClean = monitorRuntime(page);
  for (const path of ["/art/gen/", "/art/figma/", "/art/weather/", "/art/weekend-metamorphosis/"]) {
    const response = await page.goto(path, { waitUntil: "load" });
    expect(response?.status(), path).toBe(200);
    await expect(page.locator("body"), path).toBeVisible();
  }
  assertRuntimeClean();
});

test("collapse mounts its tracked film and supports keyboard pause", async ({ page }) => {
  const assertRuntimeClean = monitorRuntime(page);
  await page.goto("/art/collapse/", { waitUntil: "load" });

  const film = page.getByRole("img", {
    name: "The Symmetry of Collapse — nine-frame film sequence",
  });
  await expect(film).toBeVisible();
  await expect(film.locator("img")).toHaveCount(9);
  await film.focus();
  await expect(film).toBeFocused();
  await film.press("Enter");
  await expect(film).toHaveClass(/paused/);
  assertRuntimeClean();
});

test("voice-enabled pages resolve a real proxy endpoint with no localhost guess", async ({ page }) => {
  const assertRuntimeClean = monitorRuntime(page);

  // Every page that loads lib/realtime-endpoint.js must agree on one endpoint,
  // and must not fall back to a developer's localhost when served from a
  // published origin. The server here is 127.0.0.1, so the LOCAL branch is the
  // correct answer — what is being checked is that the resolution happens at
  // all, from the shared module, and carries the project/colony the proxy now
  // requires. realtime-proxy/server.js closes any session missing either
  // param with 4400; steamboat-willie shipped exactly that bug and lived
  // outside this page list — the offline gate
  // tests/unit/persona-integrity.test.mjs now enumerates voice-connecting
  // pages by scan, so a future page cannot hide from either surface again.
  for (const [path, project] of [
    ["/art/clue/", "clue"],
    ["/art/skippy/", "skippy"],
    ["/art/collapse/", "collapse"],
    ["/art/orb/", "orb"],
    ["/art/robo-skip/", "robo-skip"],
  ]) {
    const response = await page.goto(path, { waitUntil: "load" });
    expect(response?.status(), path).toBe(200);

    // The colony each overlay/voice-coach will send for this project —
    // derived from the dictionary, not hardcoded here, so a persona rewire
    // fails this test instead of silently passing it.
    const colony = await page.evaluate(
      (p) => window.buildVoiceConfig(p).colony.colony.toLowerCase(),
      project,
    );

    const resolved = await page.evaluate(
      ({ p, c }) => window.resolveRealtimeEndpoint("voice", { params: { project: p, colony: c } }),
      { p: project, c: colony },
    );
    expect(resolved, path).toBe(`ws://127.0.0.1:8766/?project=${project}&colony=${colony}`);

    // A published origin must NOT silently become localhost.
    const published = await page.evaluate(
      ({ p, c }) =>
        window.resolveRealtimeEndpoint("voice", { hostname: "awktavian.github.io", params: { project: p, colony: c } }),
      { p: project, c: colony },
    );
    expect(published, path).toBe(
      `wss://kagami-realtime-proxy.fly.dev/?project=${project}&colony=${colony}`,
    );

    // The scene director has no deployed proxy; asking for one off localhost
    // must name the missing service rather than return a URL.
    const directorError = await page.evaluate(() => {
      try {
        window.resolveRealtimeEndpoint("director", { hostname: "awktavian.github.io" });
        return null;
      } catch (e) {
        return { name: e.name, message: e.message };
      }
    });
    expect(directorError, path).not.toBeNull();
    expect(directorError.name, path).toBe("RealtimeEndpointUnavailable");
    expect(directorError.message, path).toContain("claude-proxy.js");

    // Every project key must have a real persona; the overlay no longer
    // substitutes a generic assistant for a missing one.
    const persona = await page.evaluate(
      (p) => (window.buildVoiceConfig ? window.buildVoiceConfig(p) : null),
      project,
    );
    expect(persona, `${path} has no PROJECT_VOICES entry`).not.toBeNull();
    expect(persona.voice, path).toBeTruthy();
    expect(persona.instructions, path).toBeTruthy();

    // Every PROJECT_VOICES key must resolve a persona (7/7), including the
    // keys no page wires today — the dictionary is the contract for all of
    // them (catastrophes and minimize-surprise are reported as page-unwired
    // by the offline gate; they stay asserted here so a broken entry cannot
    // hide behind an absent page).
    const coverage = await page.evaluate(() =>
      Object.keys(window.PROJECT_VOICES || {}).map(
        (k) => [k, window.buildVoiceConfig(k) ? 1 : 0],
      ),
    );
    expect(coverage.length, path).toBeGreaterThanOrEqual(7);
    expect(
      coverage.filter(([, ok]) => !ok).map(([k]) => k),
      `${path}: PROJECT_VOICES keys with no resolvable persona`,
    ).toEqual([]);
  }

  assertRuntimeClean();
});

test("steamboat-willie connects with project AND colony from the shared dictionary", async ({ page }) => {
  const assertRuntimeClean = monitorRuntime(page);

  // This page hand-wires RealtimeVoice (no VoiceOverlay), so it is exactly
  // the shape that can drift into the proxy's 4400 rejection: it must carry
  // BOTH query params and take its voice from KAGAMI_VOICES — never a
  // page-side string literal. lib/kagami-voices.js has no 'steamboat-willie'
  // PROJECT_VOICES key yet; the page borrows the forge colony entry, whose
  // voice ('echo') is the one the page has always used.
  await page.goto("/art/steamboat-willie.html", { waitUntil: "load" });

  const source = await page.content();
  expect(source).not.toMatch(/voice\s*:\s*['"]echo['"]/);
  expect(source, "steamboat-willie must load the shared dictionary").toContain("lib/kagami-voices.js");

  const colony = await page.evaluate(
    () => window.KAGAMI_VOICES.forge.colony.toLowerCase(),
  );
  expect(colony).toBe("forge");

  // Live proof of what the page actually sends: clicking START runs
  // initVoice(); CDP reports the WebSocket URL the moment the handshake is
  // attempted, so this captures the params even though no proxy is running
  // for the canary. A missing param here is a real 4400 in production.
  const wsPromise = page.waitForEvent("websocket", { timeout: 15_000 });
  await page.locator("#start-btn").click();
  const ws = await wsPromise;
  const url = new URL(ws.url());
  expect(url.pathname + url.search, ws.url()).toContain("project=steamboat-willie");
  expect(url.searchParams.get("project"), ws.url()).toBe("steamboat-willie");
  expect(url.searchParams.get("colony"), ws.url()).toBe(colony);

  assertRuntimeClean();
});

test("jill galleries run with no backend configured and no dead-host requests", async ({ page }) => {
  const assertRuntimeClean = monitorRuntime(page);

  // api.kagami.ai and via.placeholder.com are both dead (verified 2026-09-04).
  // Neither may be contacted, and the commerce client must report a typed
  // "not_configured" rather than a doomed fetch and an "offline" console line.
  const offSite = [];
  page.on("request", (request) => {
    const host = new URL(request.url()).hostname;
    if (host === "api.kagami.ai" || host === "via.placeholder.com") {
      offSite.push(request.url());
    }
  });

  for (const path of ["/art/jill/wardrobe/", "/art/jill/narnia/", "/art/jill/navy/", "/art/jill/spring/"]) {
    const response = await page.goto(path, { waitUntil: "load" });
    expect(response?.status(), path).toBe(200);
    await expect(page.locator("body"), path).toBeVisible();
  }

  expect(offSite, `contacted a dead host: ${offSite.join(", ")}`).toEqual([]);

  await page.goto("/art/jill/wardrobe/", { waitUntil: "load" });
  const remote = await page.evaluate(() => window.CommerceClient?.remoteStatus() ?? null);
  expect(remote).not.toBeNull();
  expect(remote.base).toBeNull();
  expect(remote.status).toBe("not_configured");
  expect(remote.detail).toContain("KAGAMI_COMMERCE_API");

  assertRuntimeClean();
});
