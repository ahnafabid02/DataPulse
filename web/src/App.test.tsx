import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({ status: url.includes("live") ? "ok" : "ready" }),
      }),
    ),
  );
  window.scrollTo = vi.fn();
});

test("shows honest sample labels and live system status", async () => {
  render(<App />);
  expect(
    screen.getByText("Sample records only. Your actions stay in this session."),
  ).toBeVisible();
  await screen.findByText("System online");
  expect(screen.getByText("Not set up yet")).toBeVisible();
  expect(fetch).toHaveBeenCalledWith(
    "/health/ready",
    expect.objectContaining({ cache: "no-store" }),
  );
});

test("explains health failure without losing access to the preview", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.reject(new Error("offline"))),
  );
  render(<App />);
  await screen.findByText("System unavailable");
  expect(screen.getByText("We can’t reach the system")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Hospitals" }));
  expect(
    screen.getByRole("heading", { name: "Your hospitals, in one place." }),
  ).toBeVisible();
});

test("an ambiguous date cannot be approved and can be sent for correction", async () => {
  window.location.hash = "fields";
  render(<App />);
  await userEvent.click(
    screen.getByRole("button", { name: /Date of birth.*Padma/ }),
  );
  expect(
    screen.getByRole("button", { name: "Clarify before approving" }),
  ).toBeDisabled();
  await userEvent.click(
    screen.getByRole("button", { name: "Send back for correction" }),
  );
  expect(
    screen.getByText("You returned this example for correction."),
  ).toBeVisible();
});

test("unconfirmed sources stay separate; combined history requires a note and confirmation", async () => {
  window.location.hash = "patients";
  render(<App />);
  expect(
    screen.queryByRole("heading", { name: "Blood glucose test" }),
  ).not.toBeInTheDocument();
  await userEvent.click(
    screen.getByRole("button", { name: /Patient matching/ }),
  );
  const link = screen.getByRole("button", { name: "Link sample identities" });
  expect(link).toBeDisabled();
  await userEvent.type(
    screen.getByRole("textbox", { name: /Why did you make this decision/ }),
    "Synthetic example checked.",
  );
  expect(link).toBeDisabled();
  await userEvent.click(
    screen.getByRole("checkbox", { name: /I have checked/ }),
  );
  await userEvent.click(link);
  await userEvent.click(
    screen.getByRole("button", { name: "Explore patient records" }),
  );
  expect(
    screen.getByRole("heading", { name: "Blood glucose test" }),
  ).toBeVisible();
  expect(screen.getByText(/Combined preview record/)).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Reset preview" }));
  expect(
    screen.queryByRole("heading", { name: "Blood glucose test" }),
  ).not.toBeInTheDocument();
});

test("hospital wizard accepts fictional details without credentials or business writes", async () => {
  window.location.hash = "hospitals";
  render(<App />);
  await userEvent.click(
    screen.getByRole("button", { name: "Add example hospital" }),
  );
  const dialog = screen.getByRole("dialog");
  await userEvent.type(
    within(dialog).getByRole("textbox", { name: /Hospital name/ }),
    "Demo Community Hospital",
  );
  await userEvent.type(
    within(dialog).getByRole("textbox", { name: "City" }),
    "Sylhet",
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "Continue" }),
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "Add to preview" }),
  );
  await waitFor(() =>
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument(),
  );
  expect(
    screen.getByRole("heading", { name: "Demo Community Hospital" }),
  ).toBeVisible();
  for (const [url] of vi.mocked(fetch).mock.calls)
    expect(String(url)).toMatch(/^\/health\//);
});
