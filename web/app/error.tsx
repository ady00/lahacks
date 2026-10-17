"use client"; // Next requires error boundaries to be client components; the sole client file at this gate.

import { useEffect } from "react";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => console.error(error), [error]);
  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Something broke</h1>
      <p className="font-mono text-sm text-red-700 dark:text-red-400">{error.message}</p>
      <button onClick={reset} className="rounded border px-3 py-1 text-sm">
        Retry
      </button>
    </div>
  );
}
