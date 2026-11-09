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
  await page.getByLabel("Search projects").fill("horizon");
  const a11y = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
  const serious = a11y.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(serious.map((v) => `${v.id}: ${v.help} — ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);

  await page.getByRole("link", { name: "Horizon" }).first().click();
  await expect(page.getByRole("heading", { name: "Horizon", level: 1 })).toBeVisible();
  await page.getByRole("navigation", { name: "Project" }).getByRole("link", { name: "Architecture" }).click();
  const nav = page.getByRole("navigation", { name: "Breadcrumb" });
  await expect(nav).toContainText("Context");
  await expect(page.locator(".react-flow__node").first()).toBeVisible();
  await expect(page.getByText(/lint pass/i)).toBeVisible();

  // C4 zoom: context -> system (double-click) -> container view
  await page.locator(".react-flow__node", { hasText: "horizon" }).first().dblclick();
  await expect(nav).toContainText("horizon");
  await page.getByRole("button", { name: /Application/ }).click();
  await expect(nav).toContainText("Application");
  await page.locator(".react-flow__node", { hasText: "api" }).first().click();
  await expect(page.getByRole("complementary", { name: "Evidence" })).toContainText("compose.yaml");
  await page.keyboard.press("Enter");                       // keyboard zoom into the selected container
  await expect(nav).toContainText("api");
  await expect(nav).toHaveText(/Context.*horizon.*api/);   // spec: Context › S › C
  await page.keyboard.press("Backspace");                   // back up one level
  await expect(nav).not.toContainText("api");
  await expect(nav).toContainText("horizon");

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
  await expect(p2.getByRole("link", { name: "Horizon" })).toHaveCount(0);
  await expect(p2.getByText("No projects yet")).toBeVisible();
  await ctx.close();
});
