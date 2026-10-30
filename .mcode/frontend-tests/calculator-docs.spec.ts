import { expect, test } from "@playwright/test";

const operations = [
  "POST /add Api Add",
  "POST /subtract Api Subtract",
  "POST /multiply Api Multiply",
  "POST /divide Api Divide",
  "GET /calculations List Calculations",
  "POST /calculations Create Calculation",
  "GET /calculations/{calculation_id} Get Calculation",
  "DELETE /calculations/{calculation_id} Delete Calculation",
] as const;

const schemas = [
  "CalculationCreate",
  "CalculationRequest",
  "CalculationResponse",
  "HTTPValidationError",
  "ResultResponse",
  "ValidationError",
] as const;

const redocOperations = [
  "post /add",
  "post /subtract",
  "post /multiply",
  "post /divide",
  "get /calculations",
  "post /calculations",
  "get /calculations/{calculation_id}",
  "delete /calculations/{calculation_id}",
] as const;

const redocMenuItems = [
  "Api Add",
  "Api Subtract",
  "Api Multiply",
  "Api Divide",
  "List Calculations",
  "Create Calculation",
  "Get Calculation",
  "Delete Calculation",
] as const;

test.describe("generated calculator API documentation", () => {
  test("Swagger renders the complete API and schema inventory", async ({ page }) => {
    await page.goto("/docs", { waitUntil: "networkidle" });
    await page.waitForTimeout(1_000);

    await expect(page).toHaveTitle("Calculator API - Swagger UI");
    await expect(
      page.getByRole("heading", { name: "Calculator API 0.1.0 OAS 3.1" }),
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "/openapi.json" })).toHaveAttribute(
      "href",
      "/openapi.json",
    );
    await expect(page.locator(".opblock")).toHaveCount(8);

    for (const operation of operations) {
      await expect(page.getByRole("button", { name: operation, exact: true })).toBeVisible();
    }

    await expect(page.getByRole("heading", { name: "Schemas" })).toBeVisible();
    for (const schema of schemas) {
      await expect(page.getByRole("button", { name: schema, exact: true })).toBeVisible();
    }
  });

  test("Swagger create-calculation controls expose an editable request", async ({ page }) => {
    await page.goto("/docs", { waitUntil: "networkidle" });
    await page.waitForTimeout(1_000);

    const operationButton = page.getByRole("button", {
      name: "POST /calculations Create Calculation",
      exact: true,
    });
    const operation = page.locator(".opblock").filter({ has: operationButton });

    await operationButton.click();
    await page.waitForTimeout(700);
    await expect(operationButton).toHaveAttribute("aria-expanded", "true");
    await operation.getByRole("button", { name: "Try it out", exact: true }).click();
    await page.waitForTimeout(700);

    await expect(operation.getByRole("heading", { name: "Request bodyrequired" })).toBeVisible();
    await expect(operation.getByRole("combobox", { name: "Request content type" })).toHaveValue(
      "application/json",
    );
    await expect(operation.getByRole("tab", { name: "Edit Value" })).toBeVisible();

    const requestBody = operation.locator("textarea.body-param__text");
    await expect(requestBody).toHaveCount(1);
    await expect(requestBody).toBeEditable();
    expect(JSON.parse(await requestBody.inputValue())).toEqual({
      operation: "string",
      a: 0,
      b: 0,
    });

    await expect(operation.getByRole("button", { name: "Cancel", exact: true })).toHaveCount(1);
    await expect(operation.getByRole("button", { name: "Execute", exact: true })).toHaveCount(1);
    await expect(operation.getByRole("cell", { name: "201", exact: true })).toBeVisible();
    await expect(operation.getByRole("cell", { name: "422", exact: true })).toBeVisible();

    const successExample = operation.getByRole("tabpanel", { name: "Example Value" }).first();
    for (const field of ["operation", "a", "b", "result", "id", "created_at"]) {
      await expect(successExample).toContainText(field);
    }
  });

  test("ReDoc renders the complete reference and accepts search text", async ({ page }) => {
    await page.goto("/redoc", { waitUntil: "networkidle" });
    await page.waitForTimeout(1_200);

    await expect(page).toHaveTitle("Calculator API - ReDoc");
    await expect(page.getByRole("heading", { name: "Calculator API (0.1.0)" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Download", exact: true })).toBeVisible();
    await expect(page.getByRole("menuitem")).toHaveCount(8);

    for (const item of redocMenuItems) {
      await expect(page.getByRole("menuitem", { name: item, exact: true })).toBeVisible();
    }
    for (const operation of redocOperations) {
      await expect(page.getByRole("button", { name: operation, exact: true })).toBeVisible();
    }

    await expect(
      page.getByRole("heading", {
        name: "Request Body schema: application/json required",
        exact: true,
      }),
    ).toHaveCount(5);
    await expect(page.getByRole("heading", { name: "path Parameters", exact: true })).toHaveCount(2);
    await expect(page.getByRole("heading", { name: "Responses", exact: true })).toHaveCount(8);
    await expect(page.getByRole("heading", { name: "Request samples", exact: true })).toHaveCount(5);
    await expect(page.getByRole("heading", { name: "Response samples", exact: true })).toHaveCount(8);
    await expect(page.getByRole("button", { name: "200 Successful Response" })).toHaveCount(6);
    await expect(page.getByRole("button", { name: "201 Successful Response" })).toHaveCount(1);
    await expect(page.getByRole("button", { name: /204 Successful Response/ })).toHaveCount(1);
    await expect(page.getByRole("button", { name: "422 Validation Error" })).toHaveCount(7);

    const search = page.getByRole("textbox", { name: "Search" });
    await search.pressSequentially("Divide");
    await expect(search).toHaveValue("Divide");
    await expect(page.getByRole("menuitem", { name: "Api Divide", exact: true })).toBeVisible();
  });
});
