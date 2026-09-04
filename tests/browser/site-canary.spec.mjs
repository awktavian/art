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
  // requires.
  for (const [path, project] of [
    ["/art/clue/", "clue"],
    ["/art/skippy/", "skippy"],
    ["/art/collapse/", "collapse"],
    ["/art/orb/", "orb"],
    ["/art/robo-skip/", "robo-skip"],
  ]) {
    const response = await page.goto(path, { waitUntil: "load" });
    expect(response?.status(), path).toBe(200);

    const resolved = await page.evaluate(
      (p) => window.resolveRealtimeEndpoint("voice", { params: { project: p } }),
      project,
    );
    expect(resolved, path).toBe(`ws://127.0.0.1:8766/?project=${project}`);

    // A published origin must NOT silently become localhost.
    const published = await page.evaluate((p) =>
      window.resolveRealtimeEndpoint("voice", { hostname: "awktavian.github.io", params: { project: p } }),
      project,
    );
    expect(published, path).toBe(
      `wss://kagami-realtime-proxy.fly.dev/?project=${project}`,
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
  }

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
