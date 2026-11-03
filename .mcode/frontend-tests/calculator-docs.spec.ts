import { expect, test, type Page } from "@playwright/test";

const operations = [
  {
    selector: "#operations-default-api_add_add_post .opblock-summary-control",
    method: "POST",
    path: "/add",
    name: "Api Add",
  },
  {
    selector: "#operations-default-api_subtract_subtract_post .opblock-summary-control",
    method: "POST",
    path: "/subtract",
    name: "Api Subtract",
  },
  {
    selector: "#operations-default-api_multiply_multiply_post .opblock-summary-control",
    method: "POST",
    path: "/multiply",
    name: "Api Multiply",
  },
  {
    selector: "#operations-default-api_divide_divide_post .opblock-summary-control",
    method: "POST",
    path: "/divide",
    name: "Api Divide",
  },
  {
    selector: "#operations-default-list_calculations_calculations_get .opblock-summary-control",
    method: "GET",
    path: "/calculations",
    name: "List Calculations",
  },
  {
    selector: "#operations-default-create_calculation_calculations_post .opblock-summary-control",
    method: "POST",
    path: "/calculations",
    name: "Create Calculation",
  },
  {
    selector:
      "#operations-default-get_calculation_calculations__calculation_id__get .opblock-summary-control",
    method: "GET",
    path: "/calculations/{calculation_id}",
    name: "Get Calculation",
  },
  {
    selector:
      "#operations-default-delete_calculation_calculations__calculation_id__delete .opblock-summary-control",
    method: "DELETE",
    path: "/calculations/{calculation_id}",
    name: "Delete Calculation",
  },
] as const;

const schemaNames = [
  "CalculationCreate",
  "CalculationRequest",
  "CalculationResponse",
  "HTTPValidationError",
  "ResultResponse",
  "ValidationError",
] as const;

async function openSwagger(page: Page) {
  await page.goto("/docs");
  // CDN-loaded generated UIs can retain background connections; the operation
  // control below is the authoritative signal that OpenAPI rendering finished.
  await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => undefined);
  await page.locator(operations[0].selector).waitFor();
}

test.describe("Calculator API generated documentation", () => {
  test("Swagger UI exposes application identity, eight operations, and six schemas", async ({ page }) => {
    await openSwagger(page);

    await expect(page).toHaveTitle("Calculator API - Swagger UI");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Calculator API 0.1.0 OAS 3.1");
    await expect(page.getByRole("link", { name: "/openapi.json", exact: true })).toHaveAttribute(
      "href",
      "/openapi.json",
    );

    for (const { selector, method, path, name } of operations) {
      const label = `${method} ${path} ${name}`;
      await expect(page.locator(selector), label).toBeVisible();
      await expect(page.locator(selector), label).toHaveAccessibleName(label);
    }

    for (const schemaName of schemaNames) {
      await expect(page.getByRole("button", { name: schemaName, exact: true })).toBeVisible();
    }
  });

  test("Swagger UI executes a successful add request", async ({ page }) => {
    await openSwagger(page);
    const operation = page.locator("#operations-default-api_add_add_post");

    await operation.locator(".opblock-summary-control").click();
    const requestBody = operation.locator(".opblock-section-request-body");
    await expect(operation).toContainText("Add two numbers.");
    await expect(requestBody.locator("h4.required")).toHaveText("Request body");
    await expect(requestBody.getByRole("combobox", { name: "Request content type" })).toHaveValue(
      "application/json",
    );
    await expect(requestBody.getByRole("tab", { name: "Example Value", exact: true })).toBeVisible();
    await expect(requestBody.getByRole("tab", { name: "Schema", exact: true })).toBeVisible();
    await expect(operation.locator(".responses-table").getByText("200", { exact: true }).first()).toBeVisible();
    await expect(operation.locator(".responses-table").getByText("422", { exact: true }).first()).toBeVisible();

    await operation.getByRole("button", { name: "Try it out", exact: true }).click();
    await operation.locator("textarea").fill('{"a": 7.5, "b": 2.5}');
    await operation.getByRole("button", { name: "Execute", exact: true }).click();

    await expect(operation.getByText("Server response", { exact: true })).toBeVisible();
    const liveResponse = operation.locator(".live-responses-table");
    await expect(liveResponse.getByRole("cell", { name: "200", exact: true })).toBeVisible();
    await expect(
      liveResponse.locator(".response-col_description pre").filter({ hasText: /"result"/ }),
    ).toContainText(/"result"\s*:\s*10/);
    await expect(operation.locator(".request-url pre")).toHaveText("http://127.0.0.1:8127/add");
  });

  test("Swagger UI exposes calculation-history request and response contracts", async ({ page }) => {
    await openSwagger(page);
    const operation = page.locator("#operations-default-create_calculation_calculations_post");

    await operation.locator(".opblock-summary-control").click();
    const requestBody = operation.locator(".opblock-section-request-body");
    await expect(operation).toContainText("Create and store a new calculation.");
    await expect(requestBody.locator("h4.required")).toHaveText("Request body");
    await expect(requestBody.getByRole("combobox", { name: "Request content type" })).toHaveValue(
      "application/json",
    );
    await expect(requestBody.getByRole("tab", { name: "Example Value", exact: true })).toBeVisible();
    await expect(requestBody.getByRole("tab", { name: "Schema", exact: true })).toBeVisible();
    await expect(operation.locator(".responses-table").getByText("201", { exact: true }).first()).toBeVisible();
    await expect(operation.locator(".responses-table").getByText("422", { exact: true }).first()).toBeVisible();

    for (const { selector } of operations.slice(4)) {
      await expect(page.locator(selector)).toBeVisible();
    }
  });

  test("ReDoc renders all operations and request and response schema samples", async ({ page }) => {
    await page.goto("/redoc");
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => undefined);
    await page.getByRole("heading", { level: 1, name: "Calculator API (0.1.0)", exact: true }).waitFor();

    await expect(page).toHaveTitle("Calculator API - ReDoc");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Calculator API (0.1.0)");
    await expect(page.getByRole("link", { name: "Download", exact: true })).toHaveAttribute(
      "href",
      "http://127.0.0.1:8127/openapi.json",
    );

    for (const { name } of operations) {
      await expect(page.locator("h2").filter({ hasText: name }), name).toBeVisible();
    }

    const requestSchemas = page.locator("h5").filter({ hasText: /Request Body schema:/i });
    await expect(requestSchemas).toHaveCount(5);
    for (let index = 0; index < 5; index += 1) {
      await expect(requestSchemas.nth(index)).toContainText("application/json");
      await expect(requestSchemas.nth(index)).toContainText("required");
    }
    await expect(page.getByRole("heading", { name: "Request samples", exact: true })).toHaveCount(5);
    await expect(page.getByRole("heading", { name: "Response samples", exact: true })).toHaveCount(8);
    await expect(page.getByRole("button", { name: "200 Successful Response", exact: true })).toHaveCount(6);
    await expect(page.getByRole("button", { name: "201 Successful Response", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "422 Validation Error", exact: true })).toHaveCount(7);
    await expect(page.getByRole("button", { name: "— 204 Successful Response", exact: true })).toBeVisible();
  });
});
