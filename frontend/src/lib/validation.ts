import { z } from "zod";
import Papa from "papaparse";
const printable = (v: string) => !/[\x00-\x1f]/.test(v);
export const recipientSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "Name is required")
    .max(200)
    .refine(printable, "Control characters are not allowed"),
  email: z.email("Enter a valid email").max(320),
});
export const jobSchema = z
  .object({
    event: z
      .string()
      .trim()
      .min(1, "Event is required")
      .max(300)
      .refine(printable),
    organization: z
      .string()
      .trim()
      .min(1, "Organization is required")
      .max(200)
      .refine(printable),
    title: z
      .string()
      .trim()
      .min(1, "Title is required")
      .max(200)
      .refine(printable),
    statement: z
      .string()
      .trim()
      .min(1, "Statement is required")
      .max(500)
      .refine(printable),
    signatory: z.string().max(200).refine(printable),
    issue_date: z.iso.date("Enter a valid date"),
    recipients: z
      .array(recipientSchema)
      .min(1, "Add at least one recipient")
      .max(1000, "Maximum 1000 recipients"),
  })
  .superRefine((data, ctx) => {
    const seen = new Set<string>();
    data.recipients.forEach((row, i) => {
      const email = row.email.toLowerCase();
      if (seen.has(email))
        ctx.addIssue({
          code: "custom",
          path: ["recipients", i, "email"],
          message: "Duplicate email",
        });
      seen.add(email);
    });
  });
export type JobInput = z.infer<typeof jobSchema>;
export function parseCsv(text: string): { name: string; email: string }[] {
  const result = Papa.parse<Record<string, string>>(text, {
    header: true,
    skipEmptyLines: "greedy",
    transformHeader: (h) => h.trim().toLowerCase(),
  });
  if (result.errors.length)
    throw new Error("CSV parsing failed: " + result.errors[0].message);
  if (
    !result.meta.fields?.includes("name") ||
    !result.meta.fields.includes("email")
  )
    throw new Error("CSV needs name,email headers");
  if (result.data.length > 1000) throw new Error("Maximum 1000 recipients");
  return result.data.map((row) => ({
    name: row.name ?? "",
    email: row.email ?? "",
  }));
}
