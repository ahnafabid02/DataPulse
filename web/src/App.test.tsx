import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: !url.startsWith("/v1"),
        status: url.startsWith("/v1") ? 401 : 200,
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
    screen.getByText(
      "Sample records only. Review and matching actions stay in this session.",
    ),
  ).toBeVisible();
  await screen.findByText("System online");
  expect(screen.getByText("View in Hospitals")).toBeVisible();
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
  expect(screen.getByText(/reach the system/)).toBeVisible();
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

const identity = {
  id: "admin-id",
  username: "demo-admin",
  kind: "human",
  roles: ["platform_admin"],
};
const organization = {
  id: "org-id",
  code: "demo-community",
  name: "Demo Community Hospital",
  revision: 1,
};
const source = {
  id: "source-id",
  organization_id: "org-id",
  code: "primary",
  ehr_product: "OpenMRS",
  ehr_version: null,
  database_vendor: "mysql",
  database_name: "fictional_demo",
  status: "registered",
  revision: 1,
};
function mockAdministration(conflict = false) {
  let signedIn = false;
  let saved = false;
  const mock = vi.fn(async (url: string, options?: RequestInit) => {
    let status = 200;
    let body: unknown = {};
    if (url.startsWith("/health"))
      body = { status: url.includes("live") ? "ok" : "ready" };
    else if (url === "/v1/auth/login") {
      signedIn = true;
      body = identity;
    } else if (url === "/v1/auth/me") {
      status = signedIn ? 200 : 401;
      body = signedIn ? identity : { error: { message: "Please sign in." } };
    } else if (url.startsWith("/v1/organizations"))
      body = { items: saved ? [organization] : [], next_cursor: null };
    else if (url.startsWith("/v1/sources?"))
      body = { items: saved ? [source] : [], next_cursor: null };
    else if (url === "/v1/onboarding") {
      expect(signedIn).toBe(true);
      expect(options?.credentials).toBe("same-origin");
      expect(options?.headers).toEqual(
        expect.objectContaining({ "X-DataPulse-Request": "1" }),
      );
      const payload = JSON.parse(String(options?.body));
      expect(payload.organization).toEqual({
        name: "Demo Community Hospital",
        code: "demo-community",
      });
      expect(payload.source.database_name).toBe("fictional_demo");
      if (conflict) {
        status = 409;
        body = { error: { message: "That hospital code already exists." } };
      } else {
        saved = true;
        status = 201;
        body = {
          organization,
          source,
          credential: {
            id: "credential-id",
            token: "one-time-fictional-token",
            expires_at: "2027-01-01T00:00:00Z",
          },
        };
      }
    } else throw new Error(`Unexpected request ${url}`);
    return { ok: status < 400, status, json: async () => body };
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}
async function signInAndSetup() {
  await userEvent.type(
    screen.getByLabelText("Administrator username"),
    "demo-admin",
  );
  await userEvent.type(
    screen.getByLabelText("Password", { exact: true }),
    "fictional-password",
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  await userEvent.click(
    await screen.findByRole("button", {
      name: "Add hospital or record system",
    }),
  );
  const dialog = screen.getByRole("dialog");
  await userEvent.type(
    within(dialog).getByLabelText(/^Hospital name/),
    "Demo Community Hospital",
  );
  await userEvent.type(
    within(dialog).getByLabelText(/^Hospital code/),
    "demo-community",
  );
  await userEvent.type(
    within(dialog).getByLabelText(/^Demo database name/),
    "fictional_demo",
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "Continue" }),
  );
  await userEvent.click(
    within(dialog).getByRole("button", { name: "Save hospital setup" }),
  );
}
test("signed-out hospital setup requires sign-in and never writes registrations", async () => {
  window.location.hash = "hospitals";
  render(<App />);
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled(),
  );
  expect(
    screen.queryByRole("button", { name: "Add hospital or record system" }),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText("Hospital setup is saved. No database is connected."),
  ).toBeVisible();
  expect(
    vi
      .mocked(fetch)
      .mock.calls.some(([url]) => String(url).includes("onboarding")),
  ).toBe(false);
});
test("hospital setup saves through authenticated API, shows the key once, and reloads saved registrations", async () => {
  mockAdministration();
  window.location.hash = "hospitals";
  const first = render(<App />);
  await signInAndSetup();
  const key = await screen.findByLabelText("Connector access key");
  expect(key).toHaveValue("one-time-fictional-token");
  await userEvent.click(
    screen.getByRole("checkbox", { name: /I have saved it securely/ }),
  );
  await userEvent.click(screen.getByRole("button", { name: "Done" }));
  await screen.findByRole("heading", { name: "Demo Community Hospital" });
  expect(
    screen.queryByLabelText("Connector access key"),
  ).not.toBeInTheDocument();
  first.unmount();
  render(<App />);
  await screen.findByRole("heading", { name: "Demo Community Hospital" });
  expect(screen.getByText("Saved · not connected")).toBeVisible();
  expect(
    screen.queryByLabelText("Connector access key"),
  ).not.toBeInTheDocument();
});
test("registration conflict keeps the form and explains failure without claiming success", async () => {
  mockAdministration(true);
  window.location.hash = "hospitals";
  render(<App />);
  await signInAndSetup();
  const dialog = screen.getByRole("dialog");
  expect(
    await within(dialog).findByText("That hospital code already exists."),
  ).toBeVisible();
  expect(
    screen.queryByLabelText("Connector access key"),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Demo Community Hospital" }),
  ).not.toBeInTheDocument();
});
