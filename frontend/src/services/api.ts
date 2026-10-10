export const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(API + "/api/v1" + path, init);
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "Service unavailable" }));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  }
  return response.json() as Promise<T>;
}
export async function download(path: string, filename: string): Promise<void> {
  const response = await fetch(API + "/api/v1" + path);
  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: "Download failed" }));
    throw new Error(String(body.detail));
  }
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
