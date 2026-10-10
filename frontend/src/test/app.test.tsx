import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { vi, afterEach, test, expect } from "vitest";
import Create from "../pages/Create";
import Detail from "../pages/Detail";
import {
  Progress,
  Badge,
  Loading,
  ErrorBox,
  DownloadButton,
} from "../components/ui";
import { jobSchema, parseCsv, recipientSchema } from "../lib/validation";
function wrap(node: React.ReactNode, path = "/new") {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/new" element={node} />
          <Route
            path="/jobs/:id"
            element={path === "/new" ? <p>Created job</p> : node}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
afterEach(() => vi.restoreAllMocks());
test("CSV parser preserves invalid rows, handles quoted commas, rejects headers", () => {
  expect(
    parseCsv('name,email\n"Rivera, Alex",alex@example.com\n,broken'),
  ).toEqual([
    { name: "Rivera, Alex", email: "alex@example.com" },
    { name: "", email: "broken" },
  ]);
  expect(() => parseCsv("foo,bar\nx,y")).toThrow("headers");
  expect(recipientSchema.safeParse({ name: "", email: "broken" }).success).toBe(
    false,
  );
});
test("schema rejects duplicates and invalid dates", () => {
  const data = {
    event: "Course",
    organization: "Lab",
    title: "Certificate",
    statement: "Completed",
    signatory: "",
    issue_date: "2026-10-09",
    recipients: [
      { name: "Alex", email: "alex@example.com" },
      { name: "Other", email: "alex@example.com" },
    ],
  };
  expect(jobSchema.safeParse(data).success).toBe(false);
  expect(
    jobSchema.safeParse({ ...data, issue_date: "2026-02-30" }).success,
  ).toBe(false);
});
test("manual rows add and remove and validation errors display", async () => {
  const user = userEvent.setup();
  wrap(<Create />);
  await user.click(screen.getByRole("button", { name: "Add recipient" }));
  expect(screen.getByLabelText("Name 2")).toBeInTheDocument();
  await user.click(screen.getByLabelText("Remove recipient 2"));
  expect(screen.queryByLabelText("Name 2")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Review batch" }));
  expect(await screen.findByText("Event is required")).toBeInTheDocument();
  expect(screen.getByText("Name is required")).toBeInTheDocument();
});
test("pasted CSV replaces the blank starter row and stays editable", async () => {
  const user = userEvent.setup();
  wrap(<Create />);
  await user.click(screen.getByText("Paste recipients as CSV"));
  fireEvent.change(screen.getByLabelText("CSV with name,email headers"), {
    target: { value: "name,email\nAlex,alex@example.com\n,broken" },
  });
  await user.click(screen.getByText("Add pasted rows"));
  // The single empty starter row is replaced, so imported rows start at 1.
  expect(screen.getByLabelText("Name 1")).toHaveValue("Alex");
  expect(screen.getByLabelText("Email 2")).toHaveValue("broken");
  expect(screen.queryByLabelText("Name 3")).not.toBeInTheDocument();
  await user.type(screen.getByLabelText("Name 2"), "Corrected");
  expect(screen.getByLabelText("Name 2")).toHaveValue("Corrected");
});

test("CSV import appends when existing rows already have data", async () => {
  const user = userEvent.setup();
  wrap(<Create />);
  await user.type(screen.getByLabelText("Name 1"), "Existing");
  await user.type(screen.getByLabelText("Email 1"), "existing@example.com");
  await user.click(screen.getByText("Paste recipients as CSV"));
  fireEvent.change(screen.getByLabelText("CSV with name,email headers"), {
    target: { value: "name,email\nAlex,alex@example.com" },
  });
  await user.click(screen.getByText("Add pasted rows"));
  // Populated rows are preserved; the import is appended after them.
  expect(screen.getByLabelText("Name 1")).toHaveValue("Existing");
  expect(screen.getByLabelText("Name 2")).toHaveValue("Alex");
});
async function fill(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Event or course"), "Engineering");
  await user.type(screen.getByLabelText("Organization"), "Learning Lab");
  await user.type(screen.getByLabelText("Name 1"), "Alex Rivera");
  await user.type(screen.getByLabelText("Email 1"), "alex@example.com");
  await user.click(screen.getByText("Review batch"));
  await screen.findByRole("dialog");
}
test("valid submission confirms and calls API with idempotency key", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(
      new Response(JSON.stringify({ id: "job-1" }), { status: 201 }),
    );
  const user = userEvent.setup();
  wrap(<Create />);
  await fill(user);
  await user.click(screen.getByText("Generate certificates"));
  expect(await screen.findByText("Created job")).toBeInTheDocument();
  expect(fetcher).toHaveBeenCalledTimes(1);
  const init = fetcher.mock.calls[0][1];
  expect(init?.method).toBe("POST");
  expect(JSON.parse(String(init?.body)).recipients[0].name).toBe("Alex Rivera");
  expect(
    (init?.headers as Record<string, string>)["Idempotency-Key"],
  ).toBeTruthy();
});
test("submission error retains form values", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "Database unavailable" }), {
      status: 503,
    }),
  );
  const user = userEvent.setup();
  wrap(<Create />);
  await fill(user);
  await user.click(screen.getByText("Generate certificates"));
  await screen.findAllByText("Database unavailable");
  await user.click(screen.getByText("Back to editing"));
  expect(screen.getByLabelText("Name 1")).toHaveValue("Alex Rivera");
});
test("loading error progress and status components", () => {
  render(
    <>
      <Loading />
      <ErrorBox error={new Error("Network failed")} />
      <Progress value={50} />
      <Badge status="completed_with_errors" />
    </>,
  );
  expect(screen.getByRole("status")).toHaveTextContent("Loading");
  expect(screen.getByRole("alert")).toHaveTextContent("Network failed");
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "50");
  expect(screen.getByText("completed with errors")).toBeInTheDocument();
});
test("download action requests actual resource", async () => {
  const fetcher = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response("PDF", { status: 200 }));
  Object.defineProperty(URL, "createObjectURL", {
    value: vi.fn(() => "blob:test"),
    configurable: true,
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    value: vi.fn(),
    configurable: true,
  });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  render(
    <DownloadButton
      path="/recipients/abc/certificate"
      filename="certificate.pdf"
    >
      Download PDF
    </DownloadButton>,
  );
  await userEvent.click(screen.getByText("Download PDF"));
  await waitFor(() =>
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining("/recipients/abc/certificate"),
    ),
  );
});
test("job details render real query results and recipient statuses", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async (input) =>
      new Response(
        JSON.stringify(
          String(input).includes("/recipients")
            ? {
                items: [
                  {
                    id: "r1",
                    name: "Alex",
                    email: "alex@example.com",
                    status: "succeeded",
                    error: null,
                  },
                ],
                total: 1,
              }
            : {
                id: "j1",
                event: "Engineering",
                status: "completed",
                total: 1,
                pending: 0,
                processing: 0,
                succeeded: 1,
                failed: 0,
                progress: 100,
                created_at: 1,
                started_at: 1,
                completed_at: 2,
              },
        ),
        { status: 200 },
      ),
  );
  wrap(<Detail />, "/jobs/j1");
  expect(await screen.findByText("Alex")).toBeInTheDocument();
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "100");
  expect(screen.getByText("Download PDF")).toBeInTheDocument();
  expect(
    screen.getByText("succeeded", { selector: ".badge" }),
  ).toBeInTheDocument();
});

test("CSV file upload previews records and rejects unsupported files", async () => {
  const user = userEvent.setup({ applyAccept: false });
  wrap(<Create />);
  const file = new File(
    ["name,email\nAlex,alex@example.com"],
    "recipients.csv",
    { type: "text/csv" },
  );
  Object.defineProperty(file, "text", {
    value: async () => "name,email\nAlex,alex@example.com",
  });
  await user.upload(screen.getByLabelText("Import CSV"), file);
  await waitFor(() =>
    expect(screen.getByLabelText("Name 1")).toHaveValue("Alex"),
  );
  await user.upload(
    screen.getByLabelText("Import CSV"),
    new File(["bad"], "recipients.exe"),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Choose a CSV file",
  );
});
