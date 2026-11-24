import type { UploadItem } from "../../api/client";

type FSEntry = {
  isFile: boolean; isDirectory: boolean; name: string; fullPath: string;
  file?: (ok: (f: File) => void, err: (e: unknown) => void) => void;
  createReader?: () => { readEntries: (ok: (e: FSEntry[]) => void, err: (e: unknown) => void) => void };
};

function readAll(reader: ReturnType<NonNullable<FSEntry["createReader"]>>): Promise<FSEntry[]> {
  return new Promise((resolve, reject) => {
    const out: FSEntry[] = [];
    const next = () => reader.readEntries((batch) => {
      if (!batch.length) return resolve(out);
      out.push(...batch); next();
    }, reject);
    next();
  });
}

async function walk(entry: FSEntry, out: UploadItem[]): Promise<void> {
  if (entry.isFile && entry.file) {
    const file = await new Promise<File>((ok, err) => entry.file!(ok, err));
    out.push({ file, path: entry.fullPath.replace(/^\//, "") });
  } else if (entry.isDirectory && entry.createReader) {
    const children = await readAll(entry.createReader());
    for (const c of children) await walk(c, out);
  }
}

/** Recursively collect files from a drop event (folders included). */
export async function collectFromDataTransfer(dt: DataTransfer): Promise<UploadItem[]> {
  const out: UploadItem[] = [];
  const entries: FSEntry[] = [];
  const plain: File[] = [];
  // webkitGetAsEntry must be called synchronously during the event
  for (const it of Array.from(dt.items ?? [])) {
    if (it.kind !== "file") continue;
    const e = (it as DataTransferItem & { webkitGetAsEntry?: () => FSEntry | null }).webkitGetAsEntry?.();
    if (e) entries.push(e); else { const f = it.getAsFile(); if (f) plain.push(f); }
  }
  if (!entries.length && !plain.length) plain.push(...Array.from(dt.files ?? []));
  for (const e of entries) await walk(e, out);
  for (const f of plain) out.push({ file: f, path: f.name });
  return out;
}

export function fromFileList(list: FileList | null): UploadItem[] {
  return Array.from(list ?? []).map((file) => ({
    file,
    path: (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name,
  }));
}
