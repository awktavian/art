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
  await expect(page.getByRole("main")).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("108 apps");
  await expect(page.locator("a.card")).toHaveCount(108);
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
  await page.keyboard.press("/");
  await expect(filter).toBeFocused();
  await filter.fill("catastrophe");
  await expect(page.getByRole("status")).not.toHaveText("108 apps");
  await page.keyboard.press("ArrowDown");
  await expect(page.locator("a.card:visible").first()).toBeFocused();
  assertRuntimeClean();
});

test("representative interactive routes load without local runtime failures", async ({ page }) => {
  const assertRuntimeClean = monitorRuntime(page);
  for (const path of ["/art/gen/", "/art/figma/", "/art/weather/"]) {
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
