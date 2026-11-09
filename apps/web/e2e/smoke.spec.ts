import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function login(page: Page, user = "admin", pass = "admin") {
  await page.goto("/");
  await page.getByLabel("Username or email").fill(user);
  await page.getByLabel("Password", { exact: true }).fill(pass);
  await page.getByRole("button", { name: "Sign In" }).click();
  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByRole("heading", { name: /^(Good (morning|afternoon|evening)|Working late)/, level: 1 })).toBeVisible();
}

test("login, projects, architecture zoom, evidence, drift, a11y", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("heading", { name: "Needs attention" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your projects" })).toBeVisible();
  const homeA11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  expect(homeA11y.violations.filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  await page.getByRole("link", { name: "All projects" }).first().click();
  await expect(page.getByRole("heading", { name: "Projects", level: 1 })).toBeVisible();
  await page.getByLabel("Search projects").fill("archtwin (self)");
  const a11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = a11y.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.help} — ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);

  await page.getByRole("link", { name: /ArchTwin \(self\)/ }).first().click();
  await expect(page.getByRole("heading", { name: "ArchTwin (self)", level: 1 })).toBeVisible();
  await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Architecture" }).click();
  const nav = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(nav).toContainText("Context");
  await expect(page.locator(".react-flow__node").first()).toBeVisible();
  await expect(page.getByText(/lint pass/i)).toBeVisible();

  // C4 zoom: context -> system (double-click) -> container view
  await page.locator(".react-flow__node", { hasText: "archtwin" }).first().dblclick();
  await expect(nav).toContainText("archtwin");
  await page.getByRole("button", { name: /Application/ }).click();
  await expect(nav).toContainText("Application");
  await page.locator(".react-flow__node", { hasText: "api" }).first().click();
  await expect(page.getByRole("complementary", { name: "Evidence" })).toContainText("compose.yaml");
  await page.keyboard.press("Enter");                       // keyboard zoom into the selected container
  await expect(nav).toContainText("api");
  await expect(nav).toHaveText(/Context.*archtwin.*api/);   // spec: Context › S › C
  await page.keyboard.press("Backspace");                   // back up one level
  await expect(nav).not.toContainText("api");
  await expect(nav).toContainText("archtwin");

  await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Drift" }).click();
  await expect(page.getByRole("heading", { name: "Drift findings" })).toBeVisible();
  await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Decisions" }).click();
  await expect(page.getByRole("heading", { name: "Decision records" })).toBeVisible();
});

test("viewer sees read-only state and outsiders see nothing", async ({ page, browser }) => {
  await login(page, "vera", "archtwin");
  await expect(page.getByRole("link", { name: "Feature flags" })).toHaveCount(0);
  const ctx = await browser.newContext();
  const p2 = await ctx.newPage();
  await login(p2, "mallory", "archtwin");
  await expect(p2.getByRole("link", { name: /ArchTwin \(self\)/ })).toHaveCount(0);
  await expect(p2.getByText("No projects yet")).toBeVisible();
  await ctx.close();
});

test("datasources: tab order, folder picker, credential shortcuts, equal resizable columns", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "All projects" }).first().click();
  await page.getByLabel("Search projects").fill("archtwin (self)");
  await page.getByRole("link", { name: /ArchTwin \(self\)/ }).first().click();
  const tabs = page.getByRole("navigation", { name: "Project" }).getByRole("link");
  await expect(tabs.last()).toHaveText("Settings");
  const names = await tabs.allInnerTexts();
  expect(names.slice(-2).map((n) => n.trim())).toEqual(["Datasources", "Settings"]);           // second-to-last, before Settings
  expect(names.map((n) => n.trim())).not.toContain("Inventory");
  await tabs.filter({ hasText: "Datasources" }).click();
  await expect(page).toHaveURL(/\/datasources$/);
  await expect(page.getByRole("heading", { name: "Datasources", level: 2 })).toBeVisible();

  // shared tables: columns start equal and can be resized (scope header and handle to the same, loaded table)
  const scans = page.getByRole("table").filter({ has: page.getByRole("button", { name: "Sort by Datasource" }) });
  await expect(scans).toBeVisible();
  const firstTh = scans.getByRole("columnheader").first();
  const before = (await firstTh.boundingBox())!.width;
  const handle = scans.getByRole("separator", { name: "Resize column" }).first();
  const hb = (await handle.boundingBox())!;
  await page.mouse.move(hb.x + 2, hb.y + hb.height / 2);
  await page.mouse.down();
  await page.mouse.move(hb.x + 80, hb.y + hb.height / 2, { steps: 4 });
  await page.mouse.up();
  expect((await firstTh.boundingBox())!.width).toBeGreaterThan(before + 30);

  await page.getByRole("button", { name: "Add datasource" }).click();
  await page.getByRole("button", { name: /Local directory/ }).click();
  await page.getByRole("button", { name: "Browse…" }).click();
  const picker = page.getByRole("dialog", { name: "Choose a local directory" });
  await expect(picker.getByRole("navigation", { name: "Places" })).toContainText("All sources");
  await picker.getByRole("button", { name: /Current path/ }).focus();
  await page.keyboard.press("Enter");                                                            // edit the path bar
  await picker.getByLabel("Type a path", { exact: true }).fill("/sources/archtwin");
  await picker.getByLabel("Type a path", { exact: true }).press("Enter");
  await expect(picker.getByText("repository", { exact: true })).toBeVisible();                   // layout of the chosen folder
  await picker.getByRole("option", { name: /fixtures/ }).dblclick();
  await expect(picker).toHaveCount(0);
  await expect(page.getByLabel("Local directory path")).toHaveValue("/sources/archtwin/fixtures");
  await expect(page.getByRole("dialog", { name: "Add Local directory / Git repository" })).toBeVisible();   // only the picker closed

  await page.getByRole("button", { name: "All datasource types" }).click();
  await page.getByRole("button", { name: /^GitLab/ }).click();
  await page.locator("textarea").first().fill(JSON.stringify({ projects: ["https://gitlab.acme.test/team/svc"] }));
  const link = page.getByRole("link", { name: /Create personal access token on GitLab/ });
  await expect(link).toHaveAttribute("href", /^https:\/\/gitlab\.acme\.test\/-\/user_settings\/personal_access_tokens\?name=.*&scopes=read_api,read_repository$/);
  await expect(page.getByRole("link", { name: /Open project webhooks/ })).toHaveAttribute("href", "https://gitlab.acme.test/team/svc/-/hooks");
  await page.getByRole("button", { name: "Generate webhook secret" }).click();
  await expect(page.getByLabel("credential webhook_secret")).toHaveValue(/^[0-9a-f]{64}$/);
  await expect(page.getByLabel("credential token")).toHaveAttribute("type", "password");
});

test("command palette: keyboard open, fuzzy search, navigate, project search; night theme is neutral, not blue", async ({ page }) => {
  await login(page);
  await page.keyboard.press("ControlOrMeta+k");
  const palette = page.getByRole("dialog");
  const input = page.getByTestId("cmdk-input");
  await expect(input).toBeFocused();
  await input.fill("usage cost");                                                // fuzzy: matches "Usage & costs"
  await expect(page.getByRole("option", { name: /Usage & costs/ })).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/usage$/);
  await expect(palette).toHaveCount(0);

  // switch to a project from the palette, then search inside it
  await page.getByRole("button", { name: "Open command palette" }).click();
  await input.fill("archtwin self");
  await page.getByRole("option", { name: /ArchTwin \(self\)/ }).first().click();
  await expect(page.getByRole("heading", { name: "ArchTwin (self)", level: 1 })).toBeVisible();
  await page.keyboard.press("ControlOrMeta+k");
  await input.fill("flows");
  await expect(page.getByRole("option", { name: /^Flows/ }).first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(palette).toHaveCount(0);

  // recent destinations are offered on an empty query
  await page.keyboard.press("ControlOrMeta+k");
  await expect(page.getByRole("group", { name: "Recent" }).getByRole("option", { name: /Usage & costs/ })).toBeVisible();
  await page.keyboard.press("Escape");

  // theme toggle (button and ⌘⇧L) — night mode surfaces are neutral graphite, not blue
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  const rgb = await page.evaluate(() => getComputedStyle(document.body).backgroundColor.match(/\d+/g)!.map(Number));
  expect(Math.abs(rgb[0] - rgb[2])).toBeLessThanOrEqual(6);
  expect(rgb[0]).toBeLessThan(40);
  await page.keyboard.press("ControlOrMeta+Shift+l");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});
