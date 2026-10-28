import { expect, type Locator, type Page, test } from "@playwright/test";
import { applicationOrigin } from "./application-origin";

async function openSwaggerOperation(
  page: Page,
  accessibleName: string,
  method: "get" | "post",
): Promise<Locator> {
  await page.goto("/docs");
  await page.waitForLoadState("networkidle");

  const operationButton = page.getByRole("button", { name: accessibleName, exact: true });
  await expect(operationButton).toBeVisible();
  await operationButton.click();

  const openOperation = page.locator(`.opblock-${method}.is-open`);
  await expect(openOperation).toHaveCount(1);
  return openOperation;
}

async function executeSwaggerPost(
  page: Page,
  accessibleName: string,
  endpoint: string,
  requestBody: object,
  expectedStatus: number,
) {
  const openOperation = await openSwaggerOperation(page, accessibleName, "post");
  await openOperation.getByRole("button", { name: "Try it out", exact: true }).click();
  await expect(openOperation.getByRole("button", { name: "Cancel", exact: true })).toBeVisible();
  await openOperation.locator("textarea").fill(JSON.stringify(requestBody));

  const responsePromise = page.waitForResponse(
    (response) =>
      response.url() === `${applicationOrigin}${endpoint}` &&
      response.request().method() === "POST",
  );
  await openOperation.getByRole("button", { name: "Execute", exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(expectedStatus);

  const liveResponse = openOperation.locator(".live-responses-table");
  await expect(liveResponse).toBeVisible();
  await expect(
    liveResponse.locator(".response-col_status:not(.col_header)"),
  ).toHaveText(String(expectedStatus));
  const requestUrlSection = openOperation
    .getByRole("heading", { name: "Request URL", exact: true })
    .locator("..");
  await expect(requestUrlSection).toContainText(`${applicationOrigin}${endpoint}`);
  return { liveResponse, response };
}

test.describe("Calculator API generated browser documentation", () => {
  test("Swagger identifies the service and exposes all application operations and schemas", async ({
    page,
  }) => {
    await page.goto("/docs");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "Calculator API 0.1.0 OAS 3.1" })).toBeVisible();
    await expect(page.getByRole("link", { name: "/openapi.json", exact: true })).toBeVisible();

    const operations = [
      "POST /add Api Add",
      "POST /subtract Api Subtract",
      "POST /multiply Api Multiply",
      "POST /divide Api Divide",
      "GET /calculations List Calculations",
      "POST /calculations Create Calculation",
      "GET /calculations/{calculation_id} Get Calculation",
      "DELETE /calculations/{calculation_id} Delete Calculation",
    ];
    for (const operation of operations) {
      await expect(page.getByRole("button", { name: operation, exact: true })).toBeVisible();
    }

    const schemas = [
      "CalculationCreate",
      "CalculationRequest",
      "CalculationResponse",
      "HTTPValidationError",
      "ResultResponse",
      "ValidationError",
    ];
    for (const schema of schemas) {
      await expect(page.getByRole("button", { name: schema, exact: true })).toBeVisible();
    }
  });

  test("Swagger executes direct addition and displays the live 200 response", async ({ page }) => {
    const { liveResponse, response } = await executeSwaggerPost(
      page,
      "POST /add Api Add",
      "/add",
      { a: 8.5, b: 4 },
      200,
    );

    await expect(liveResponse).toContainText('"result": 12.5');
    expect(await response.json()).toEqual({ result: 12.5 });
  });

  test("Swagger creates and displays a persisted calculation record", async ({ page }) => {
    const { liveResponse, response } = await executeSwaggerPost(
      page,
      "POST /calculations Create Calculation",
      "/calculations",
      { operation: "mul", a: 7, b: 6 },
      201,
    );

    await expect(liveResponse).toContainText('"operation": "mul"');
    await expect(liveResponse).toContainText('"result": 42');
    await expect(liveResponse).toContainText('"created_at"');

    const calculation = await response.json();
    expect(calculation).toMatchObject({ operation: "mul", a: 7, b: 6, result: 42 });
    expect(Number.isInteger(calculation.id)).toBe(true);
    expect(typeof calculation.created_at).toBe("string");
    expect(calculation.created_at.length).toBeGreaterThan(0);
  });

  test("Swagger lists a calculation persisted through an earlier interactive request", async ({
    page,
  }) => {
    await executeSwaggerPost(
      page,
      "POST /calculations Create Calculation",
      "/calculations",
      { operation: "mul", a: 7, b: 6 },
      201,
    );

    const openOperation = await openSwaggerOperation(
      page,
      "GET /calculations List Calculations",
      "get",
    );
    await openOperation.getByRole("button", { name: "Try it out", exact: true }).click();

    const responsePromise = page.waitForResponse(
      (response) =>
        response.url() === `${applicationOrigin}/calculations` &&
        response.request().method() === "GET",
    );
    await openOperation.getByRole("button", { name: "Execute", exact: true }).click();
    const response = await responsePromise;
    expect(response.status()).toBe(200);

    const liveResponse = openOperation.locator(".live-responses-table");
    await expect(liveResponse).toBeVisible();
    await expect(liveResponse.locator(".response-col_status:not(.col_header)")).toHaveText("200");
    await expect(liveResponse).toContainText('"operation": "mul"');
    await expect(liveResponse).toContainText('"a": 7');
    await expect(liveResponse).toContainText('"b": 6');
    await expect(liveResponse).toContainText('"result": 42');

    const history = await response.json();
    expect(history).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ operation: "mul", a: 7, b: 6, result: 42 }),
      ]),
    );
  });

  test("ReDoc identifies the service and presents all operation contracts", async ({ page }) => {
    await page.goto("/redoc");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "Calculator API (0.1.0)", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download", exact: true })).toBeVisible();

    const body = page.locator("body");
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
      await expect(body).toContainText(operation);
    }
    await expect(
      page.getByRole("heading", {
        name: "Request Body schema: application/json required",
        exact: true,
      }),
    ).toHaveCount(5);
    await expect(page.getByRole("heading", { name: "Responses", exact: true })).toHaveCount(8);
    await expect(body).toContainText("API docs by Redocly");
  });

  test("Swagger OAuth redirect retains its generated page contract", async ({ page }) => {
    const response = await page.goto("/docs/oauth2-redirect");
    await page.waitForLoadState("networkidle");

    expect(response?.status()).toBe(200);
    await expect(page).toHaveTitle("Swagger UI: OAuth2 Redirect");
    await expect(page.locator("body")).toHaveText("");
    expect(await page.locator("script").count()).toBeGreaterThan(0);
  });

  test("browser-visible OpenAPI JSON preserves identity, paths, and eight operations", async ({
    page,
  }) => {
    const response = await page.goto("/openapi.json");
    await page.waitForLoadState("networkidle");

    expect(response?.status()).toBe(200);
    const openapi = JSON.parse(await page.locator("body").innerText());
    expect(openapi.info).toMatchObject({ title: "Calculator API", version: "0.1.0" });

    const expectedPaths = [
      "/add",
      "/subtract",
      "/multiply",
      "/divide",
      "/calculations",
      "/calculations/{calculation_id}",
    ];
    expect(Object.keys(openapi.paths).sort()).toEqual(expectedPaths.sort());
    const operationCount = Object.values(openapi.paths).reduce(
      (count: number, pathItem) =>
        count +
        Object.keys(pathItem as object).filter((key) =>
          ["get", "post", "put", "patch", "delete", "options", "head", "trace"].includes(key),
        ).length,
      0,
    );
    expect(operationCount).toBe(8);
  });
});
