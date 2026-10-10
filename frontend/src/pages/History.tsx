import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Job, Page } from "../types";
import { Badge, Progress, Pager, Loading, ErrorBox } from "../components/ui";
export function JobTable({ jobs }: { jobs: Job[] }) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Event / Job ID</th>
            <th>Created</th>
            <th>Recipients</th>
            <th>Success / Failed</th>
            <th>Status</th>
            <th>Progress</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id}>
              <td>
                <Link to={"/jobs/" + j.id}>{j.event}</Link>
                <small>{j.id}</small>
              </td>
              <td>{new Date(j.created_at * 1000).toLocaleString()}</td>
              <td>{j.total}</td>
              <td>
                {j.succeeded} / {j.failed}
              </td>
              <td>
                <Badge status={j.status} />
              </td>
              <td>
                <Progress value={j.progress} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!jobs.length && (
        <p className="empty">
          No jobs yet. Create your first certificate batch.
        </p>
      )}
    </div>
  );
}
export default function History() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const q = useQuery({
    queryKey: ["jobs", search, status, page],
    queryFn: () =>
      api<Page<Job>>(
        `/jobs?page=${page}&search=${encodeURIComponent(search)}${status ? "&status=" + status : ""}`,
      ),
    refetchInterval: 5000,
  });
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Job history</h1>
          <p>Every batch, with persistent results.</p>
        </div>
        <Link className="button primary" to="/new">
          Create batch
        </Link>
      </header>
      <section className="card">
        <div className="actions">
          <label>
            Search events
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <label>
            Status
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              {[
                "queued",
                "processing",
                "completed",
                "completed_with_errors",
                "failed",
              ].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
        </div>
        <ErrorBox error={q.error} />
        {q.isPending ? (
          <Loading />
        ) : (
          q.data && (
            <>
              <JobTable jobs={q.data.items} />
              <Pager
                page={page}
                total={q.data.total}
                size={20}
                onChange={setPage}
              />
            </>
          )
        )}
      </section>
    </>
  );
}
