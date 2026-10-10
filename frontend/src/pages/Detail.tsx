import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useLocation } from "react-router-dom";
import { api, API } from "../services/api";
import type { Job, Recipient, Page } from "../types";
import {
  Badge,
  Progress,
  Pager,
  Loading,
  ErrorBox,
  DownloadButton,
} from "../components/ui";
export default function Detail() {
  const { id } = useParams();
  const location = useLocation();
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [preview, setPreview] = useState<string | null>(null);
  const job = useQuery({
    queryKey: ["job", id],
    queryFn: () => api<Job>("/jobs/" + id),
    refetchInterval: (q) =>
      q.state.data && ["queued", "processing"].includes(q.state.data.status)
        ? 2000
        : false,
  });
  const active =
    !job.data || ["queued", "processing"].includes(job.data.status);
  const rows = useQuery({
    queryKey: ["recipients", id, status, page],
    queryFn: () =>
      api<Page<Recipient>>(
        `/jobs/${id}/recipients?page=${page}${status ? "&status=" + status : ""}`,
      ),
    refetchInterval: active ? 2000 : false,
  });
  if (job.isPending) return <Loading />;
  if (job.error) return <ErrorBox error={job.error} />;
  if (!job.data) return null;
  const j = job.data;
  return (
    <>
      {location.state?.created && (
        <p role="status" className="success">
          Batch accepted and stored. Processing continues independently of this
          page.
        </p>
      )}
      <header className="page-head">
        <div>
          <h1>{j.event}</h1>
          <p className="mono">{j.id}</p>
        </div>
        <Badge status={j.status} />
      </header>
      <section className="card">
        <Progress value={j.progress} />
        <div className="counts">
          {(
            ["total", "pending", "processing", "succeeded", "failed"] as const
          ).map((k) => (
            <div key={k}>
              <strong>{j[k]}</strong>
              <span>{k}</span>
            </div>
          ))}
        </div>
        <p>
          Created: {new Date(j.created_at * 1000).toLocaleString()} · Started:{" "}
          {j.started_at
            ? new Date(j.started_at * 1000).toLocaleString()
            : "Not started"}{" "}
          · Completed:{" "}
          {j.completed_at
            ? new Date(j.completed_at * 1000).toLocaleString()
            : "Not completed"}
        </p>
        {!active && j.succeeded > 0 && (
          <DownloadButton
            path={`/jobs/${id}/download`}
            filename={`certificates-${id}.zip`}
          >
            Download successful certificates (ZIP)
          </DownloadButton>
        )}
      </section>
      <section className="card">
        <h2>Recipient results</h2>
        <div className="tabs" role="group" aria-label="Filter recipients">
          {["", "succeeded", "failed", "pending", "processing"].map((s) => (
            <button
              aria-pressed={status === s}
              key={s}
              onClick={() => {
                setStatus(s);
                setPage(1);
              }}
            >
              {s || "All"}
            </button>
          ))}
        </div>
        <ErrorBox error={rows.error} />
        {rows.isPending ? (
          <Loading />
        ) : (
          rows.data && (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Status</th>
                      <th>Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.data.items.map((r) => (
                      <tr key={r.id}>
                        <td>{r.name}</td>
                        <td>{r.email}</td>
                        <td>
                          <Badge status={r.status} />
                        </td>
                        <td>
                          {r.status === "succeeded" ? (
                            <div className="actions">
                              <DownloadButton
                                path={`/recipients/${r.id}/certificate`}
                                filename={`certificate-${r.id}.pdf`}
                              >
                                Download PDF
                              </DownloadButton>
                              <button onClick={() => setPreview(r.id)}>
                                Preview
                              </button>
                            </div>
                          ) : (
                            (r.error ?? "Awaiting processing")
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!rows.data.items.length && (
                  <p className="empty">No recipients match this filter.</p>
                )}
              </div>
              <Pager
                page={page}
                total={rows.data.total}
                size={50}
                onChange={setPage}
              />
            </>
          )
        )}
      </section>
      {preview && (
        <section className="card">
          <div className="section-head">
            <h2>Generated certificate preview</h2>
            <button onClick={() => setPreview(null)}>Close preview</button>
          </div>
          <iframe
            title="Generated certificate"
            src={`${API}/api/v1/recipients/${preview}/certificate?inline=true`}
            className="pdf-preview"
          />
        </section>
      )}
    </>
  );
}
