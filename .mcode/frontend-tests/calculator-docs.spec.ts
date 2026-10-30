import { expect, test } from "@playwright/test";

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
      "http://127.0.0.1:8180/openapi.json",
    );

    const operations = page.locator(".opblock-summary");
    const expectedOperations = [
      /^\s*POST\s*\/add\s*Api Add\s*$/,
      /^\s*POST\s*\/subtract\s*Api Subtract\s*$/,
      /^\s*POST\s*\/multiply\s*Api Multiply\s*$/,
      /^\s*POST\s*\/divide\s*Api Divide\s*$/,
      /^\s*GET\s*\/calculations\s*List Calculations\s*$/,
      /^\s*POST\s*\/calculations\s*Create Calculation\s*$/,
      /^\s*GET\s*\/calculations\/\{calculation_id\}\s*Get Calculation\s*$/,
      /^\s*DELETE\s*\/calculations\/\{calculation_id\}\s*Delete Calculation\s*$/,
    ];
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
      "http://127.0.0.1:8180/add",
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

    for (const operation of [
      "Api Add",
      "Api Subtract",
      "Api Multiply",
      "Api Divide",
      "List Calculations",
      "Create Calculation",
      "Get Calculation",
      "Delete Calculation",
    ]) {
      await expect(page.getByRole("menuitem", { name: operation })).toBeVisible();
    }

    for (const operationButton of [
      /^post\s*\/add$/i,
      /^post\s*\/subtract$/i,
      /^post\s*\/multiply$/i,
      /^post\s*\/divide$/i,
      /^get\s*\/calculations$/i,
      /^post\s*\/calculations$/i,
      /^get\s*\/calculations\/\{calculation_id\}$/i,
      /^delete\s*\/calculations\/\{calculation_id\}$/i,
    ]) {
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
        "/add",
        "/subtract",
        "/multiply",
        "/divide",
        "/calculations",
        "/calculations/{calculation_id}",
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
