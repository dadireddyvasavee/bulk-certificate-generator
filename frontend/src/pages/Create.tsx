import { useRef, useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, Trash2, Upload } from "lucide-react";
import { jobSchema, parseCsv, type JobInput } from "../lib/validation";
import { api } from "../services/api";
import type { Job } from "../types";
import { Confirm, ErrorBox } from "../components/ui";
export default function Create() {
  const navigate = useNavigate();
  const cache = useQueryClient();
  const [confirmed, setConfirmed] = useState<JobInput | null>(null);
  const [importError, setImportError] = useState<unknown>(null);
  const [paste, setPaste] = useState("");
  const key = useRef({ body: "", key: "" });
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
    getValues,
  } = useForm<JobInput>({
    resolver: zodResolver(jobSchema),
    defaultValues: {
      event: "",
      organization: "",
      title: "Certificate of Achievement",
      statement: "For successfully completing the course",
      signatory: "",
      issue_date: new Date().toISOString().slice(0, 10),
      recipients: [{ name: "", email: "" }],
    },
  });
  const { fields, append, remove, replace } = useFieldArray({
    control,
    name: "recipients",
  });
  const mutation = useMutation({
    mutationFn: (data: JobInput) => {
      const body = JSON.stringify(data);
      if (key.current.body !== body)
        key.current = { body, key: crypto.randomUUID() };
      return api<Job>("/jobs", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": key.current.key,
        },
        body,
      });
    },
    onSuccess: (job) => {
      void cache.invalidateQueries();
      navigate("/jobs/" + job.id, { state: { created: true } });
    },
  });
  function importText(text: string) {
    try {
      const rows = parseCsv(text);
      const current = getValues("recipients");
      // If the form only holds blank starter rows, replace them so an import
      // does not leave a leading empty row that fails validation.
      const onlyBlankRows = current.every(
        (r) => !r.name.trim() && !r.email.trim(),
      );
      const kept = onlyBlankRows ? 0 : current.length;
      if (kept + rows.length > 1000)
        throw new Error("Remove unused rows: maximum 1000 recipients");
      if (onlyBlankRows) replace(rows);
      else append(rows);
      setImportError(null);
    } catch (error) {
      setImportError(error);
    }
  }
  const labels = {
    event: "Event or course",
    organization: "Organization",
    title: "Certificate title",
    statement: "Achievement statement",
    signatory: "Authorized signatory (optional)",
    issue_date: "Issue date",
  };
  return (
    <>
      <header className="page-head">
        <div>
          <h1>Create a batch</h1>
          <p>Personalized certificates, one reliable workflow.</p>
        </div>
      </header>
      <form onSubmit={handleSubmit(setConfirmed)}>
        <section className="card">
          <h2>1. Certificate details</h2>
          <div className="form-grid">
            {(
              [
                "event",
                "organization",
                "title",
                "statement",
                "signatory",
                "issue_date",
              ] as const
            ).map((name) => (
              <label key={name}>
                {labels[name]}
                <input
                  type={name === "issue_date" ? "date" : "text"}
                  {...register(name)}
                  aria-invalid={!!errors[name]}
                />
                {errors[name] && (
                  <span className="field-error">{errors[name]?.message}</span>
                )}
              </label>
            ))}
          </div>
        </section>
        <section className="card">
          <h2>
            2. Recipients <span className="muted">({fields.length}/1000)</span>
          </h2>
          <p>
            Imported rows are kept for review. Correct all invalid or duplicate
            rows before submission.
          </p>
          <div className="actions">
            <label className="file-button">
              <Upload size={16} /> Import CSV
              <input
                aria-label="Import CSV"
                type="file"
                accept=".csv,text/csv"
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file) return;
                  if (
                    !file.name.toLowerCase().endsWith(".csv") ||
                    file.size > 1000000
                  ) {
                    setImportError(
                      new Error("Choose a CSV file smaller than 1 MB"),
                    );
                    return;
                  }
                  importText(await file.text());
                  e.target.value = "";
                }}
              />
            </label>
            <a
              download="recipients.csv"
              href={
                "data:text/csv;charset=utf-8," +
                encodeURIComponent(
                  "name,email\nAlex Rivera,alex@example.com\nSam Taylor,sam@example.com\n",
                )
              }
            >
              Sample CSV
            </a>
          </div>
          <details>
            <summary>Paste recipients as CSV</summary>
            <label>
              CSV with name,email headers
              <textarea
                value={paste}
                onChange={(e) => setPaste(e.target.value)}
              />
            </label>
            <button type="button" onClick={() => importText(paste)}>
              Add pasted rows
            </button>
          </details>
          <ErrorBox error={importError} />
          <div className="recipient-editor">
            {fields.map((field, i) => (
              <div className="recipient-row" key={field.id}>
                <span>{i + 1}</span>
                <label>
                  Name {i + 1}
                  <input
                    {...register(`recipients.${i}.name`)}
                    aria-invalid={!!errors.recipients?.[i]?.name}
                  />
                  <span className="field-error">
                    {errors.recipients?.[i]?.name?.message}
                  </span>
                </label>
                <label>
                  Email {i + 1}
                  <input
                    {...register(`recipients.${i}.email`)}
                    aria-invalid={!!errors.recipients?.[i]?.email}
                  />
                  <span className="field-error">
                    {errors.recipients?.[i]?.email?.message}
                  </span>
                </label>
                <button
                  type="button"
                  aria-label={`Remove recipient ${i + 1}`}
                  onClick={() => remove(i)}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
          <span className="field-error">
            {errors.recipients?.root?.message ?? errors.recipients?.message}
          </span>
          <button
            type="button"
            disabled={fields.length >= 1000}
            onClick={() => append({ name: "", email: "" })}
          >
            <Plus size={16} /> Add recipient
          </button>
        </section>
        <ErrorBox error={mutation.error} />
        <button type="submit" className="primary" disabled={mutation.isPending}>
          Review batch
        </button>
      </form>
      <Confirm
        open={!!confirmed}
        onClose={() => setConfirmed(null)}
        onConfirm={() => {
          if (confirmed) mutation.mutate(confirmed);
        }}
        busy={mutation.isPending}
      >
        <p>
          <strong>{confirmed?.event}</strong> · {confirmed?.organization}
        </p>
        <p>
          {confirmed?.recipients.length} validated recipients · Issue date{" "}
          {confirmed?.issue_date}
        </p>
        <ErrorBox error={mutation.error} />
      </Confirm>
    </>
  );
}
