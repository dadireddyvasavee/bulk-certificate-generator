import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import type { Metrics, Job, Page } from "../types";
import { JobTable } from "./History";
import { Loading, ErrorBox } from "../components/ui";
export default function Dashboard() {
  const m = useQuery({
    queryKey: ["metrics"],
    queryFn: () => api<Metrics>("/metrics"),
    refetchInterval: 5000,
  });
  const jobs = useQuery({
    queryKey: ["recent"],
    queryFn: () => api<Page<Job>>("/jobs?page_size=5"),
    refetchInterval: 5000,
  });
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Certificate operations</h1>
          <p>Create, monitor, and deliver certificates with confidence.</p>
        </div>
        <Link className="button primary" to="/new">
          Create batch
        </Link>
      </header>
      <ErrorBox error={m.error} />
      {m.isPending ? (
        <Loading />
      ) : (
        m.data && (
          <div className="metrics">
            {(
              [
                ["jobs", "Generation jobs"],
                ["processed", "Recipients processed"],
                ["succeeded", "Successful certificates"],
                ["failed", "Failed certificates"],
                ["processing", "Currently processing"],
                ["pending", "Pending recipients"],
              ] as const
            ).map(([key, label]) => (
              <section className="metric" key={key}>
                <span>{label}</span>
                <strong>{m.data[key]}</strong>
              </section>
            ))}
          </div>
        )
      )}
      <section className="card">
        <div className="section-head">
          <h2>Recent batches</h2>
          <Link to="/history">View history</Link>
        </div>
        <ErrorBox error={jobs.error} />
        {jobs.isPending ? (
          <Loading />
        ) : (
          jobs.data && <JobTable jobs={jobs.data.items} />
        )}
      </section>
    </>
  );
}
