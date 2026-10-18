"use client"; // Next requires error boundaries to be client components.

import { useEffect } from "react";

// In production Next replaces a server error's message with a digest, so the banner in layout.tsx
// (server-rendered) is what names the unreachable API; this page only offers the retry.
export default function Error({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => console.error(error), [error]);
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">This page could not load</h1>
      <p className="text-sm">The API returned an error or is not answering. If there is a red banner above, fix that first; otherwise check the server log.</p>
      {error.digest && <p className="font-mono text-xs text-zinc-500">{error.digest}</p>}
      <button onClick={() => retry()} className="rounded border px-3 py-1 text-sm">
        Try again
      </button>
    </div>
  );
}
