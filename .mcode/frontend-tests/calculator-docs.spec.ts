import { expect, test } from "@playwright/test";

const apiOperations = [
  { method: "POST", path: "/add", summary: "Api Add" },
  { method: "POST", path: "/subtract", summary: "Api Subtract" },
  { method: "POST", path: "/multiply", summary: "Api Multiply" },
  { method: "POST", path: "/divide", summary: "Api Divide" },
  { method: "GET", path: "/calculations", summary: "List Calculations" },
  { method: "POST", path: "/calculations", summary: "Create Calculation" },
  {
    method: "GET",
    path: "/calculations/{calculation_id}",
    summary: "Get Calculation",
  },
  {
    method: "DELETE",
    path: "/calculations/{calculation_id}",
    summary: "Delete Calculation",
  },
] as const;

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test.describe("Calculator API generated browser surfaces", () => {
  test("Swagger renders API identity, operations, and schemas", async ({ page }) => {
    await page.goto("/docs");

    await expect(page).toHaveTitle("Calculator API - Swagger UI");
    await expect(
      page.getByRole("heading", { name: "Calculator API 0.1.0 OAS 3.1" }),
    ).toBeVisible();

    const openApiLink = page.getByRole("link", { name: "/openapi.json" });
    await expect(openApiLink).toHaveAttribute("href", "/openapi.json");
    expect(await openApiLink.evaluate((link: HTMLAnchorElement) => link.href)).toBe(
      new URL("/openapi.json", page.url()).href,
    );

    const operations = page.locator(".opblock-summary");
    const expectedOperations = apiOperations.map(
      ({ method, path, summary }) =>
        new RegExp(
          `^\\s*${escapeRegExp(method)}\\s*${escapeRegExp(path)}\\s*${escapeRegExp(summary)}\\s*$`,
        ),
    );
    await expect(operations).toHaveCount(expectedOperations.length);
    await expect(operations).toHaveText(expectedOperations);
    for (let index = 0; index < expectedOperations.length; index += 1) {
      await expect(operations.nth(index)).toBeVisible();
    }

    await expect(page.getByRole("heading", { name: "Schemas" })).toBeVisible();
    for (const schema of [
      "CalculationCreate",
      "CalculationRequest",
      "CalculationResponse",
      "HTTPValidationError",
      "ResultResponse",
      "ValidationError",
    ]) {
      await expect(
        page.getByRole("button", { name: schema, exact: true }),
      ).toBeVisible();
    }
  });

  test("Swagger executes POST /add with 5 and 3 and displays result 8", async ({
    page,
  }) => {
    await page.goto("/docs");
    await page.getByRole("button", { name: "POST /add Api Add" }).click();
    await expect(
      page.getByRole("button", {
        name: "POST /add Api Add",
        expanded: true,
      }),
    ).toBeVisible();

    await page.getByRole("button", { name: "Try it out" }).click();
    const requestBody = page.locator("textarea");
    await requestBody.fill('{"a":5,"b":3}');
    await expect(requestBody).toHaveValue('{"a":5,"b":3}');
    await page.getByRole("button", { name: "Execute", exact: true }).click();

    await expect(page.getByText("Response body", { exact: true })).toBeVisible();
    await expect(page.getByText("Server response", { exact: true })).toBeVisible();
    await expect(page.getByText("Request URL", { exact: true })).toBeVisible();
    await expect(page.getByText("Response headers", { exact: true })).toBeVisible();

    const addOperation = page.locator(".opblock-post.is-open");
    await expect(addOperation.locator(".request-url")).toContainText(
      new URL("/add", page.url()).href,
    );
    const liveResponse = addOperation.locator(".live-responses-table tbody tr");
    await expect(liveResponse.locator(".response-col_status")).toHaveText("200");
    await expect(liveResponse.locator(".response-col_description")).toContainText(
      /"result"\s*:\s*8/,
    );
  });

  test("ReDoc renders API identity and complete operation navigation", async ({
    page,
  }) => {
    await page.goto("/redoc");

    await expect(page).toHaveTitle("Calculator API - ReDoc");
    await expect(page.getByRole("textbox", { name: "Search" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Calculator API (0.1.0)" }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Download" })).toBeVisible();

    for (const { summary } of apiOperations) {
      await expect(page.getByRole("menuitem", { name: summary })).toBeVisible();
    }

    for (const { method, path } of apiOperations) {
      const operationButton = new RegExp(
        `^${escapeRegExp(method)}\\s*${escapeRegExp(path)}$`,
        "i",
      );
      await expect(
        page.getByRole("button", { name: operationButton }),
      ).toBeAttached();
    }
  });

  test("raw OpenAPI exposes metadata and calculator/history paths", async ({
    page,
  }) => {
    const response = await page.goto("/openapi.json");
    expect(response).not.toBeNull();
    expect(response?.status()).toBe(200);
    expect(response?.headers()["content-type"]).toContain("application/json");

    const rawBody = await page.locator("body").innerText();
    const document = JSON.parse(rawBody);
    expect(document.openapi).toBe("3.1.0");
    expect(document.info).toMatchObject({
      title: "Calculator API",
      version: "0.1.0",
    });
    expect(Object.keys(document.paths)).toEqual(
      expect.arrayContaining([
        ...new Set(apiOperations.map(({ path }) => path)),
      ]),
    );
    expect(Object.keys(document.components.schemas)).toEqual(
      expect.arrayContaining([
        "CalculationCreate",
        "CalculationRequest",
        "CalculationResponse",
        "ResultResponse",
      ]),
    );
  });

  test("OAuth redirect helper remains a registered HTML document", async ({
    page,
  }) => {
    const response = await page.goto("/docs/oauth2-redirect");
    expect(response).not.toBeNull();
    expect(response?.status()).toBe(200);
    expect(response?.headers()["content-type"]).toContain("text/html");
    await expect(page).toHaveTitle("Swagger UI: OAuth2 Redirect");
    await expect(page.locator("script")).toHaveCount(1);
    await expect(page.locator("body")).toHaveText("");
  });
});
