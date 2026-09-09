"use client";

/**
 * Says plainly, on every page, that a hosted deployment is a demonstration.
 *
 * CA-Guard's privacy claim is that a client's ledger never leaves the machine.
 * That is true of a self-hosted install and **not** true of anything running on
 * someone else's infrastructure. A CA who uploaded real client data to a public
 * demo because the interface did not say otherwise would have been misled by us,
 * so the demo says otherwise — permanently, and not in small print.
 */

import { useEffect, useState } from "react";
import { AlertTriangle } from "lucide-react";

export function DemoBanner() {
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    fetch("/api/health")
      .then((response) => response.json())
      .then((body) => setDemo(Boolean(body.demo_mode)))
      .catch(() => setDemo(false));
  }, []);

  if (!demo) return null;

  return (
    <div className="flex items-center justify-center gap-2 bg-medium px-4 py-1.5 text-center text-[12px] font-medium text-white">
      <AlertTriangle size={13} className="shrink-0" />
      <span>
        Demonstration on synthetic data. Do not upload a real client ledger — this
        runs on hosted infrastructure. The private version runs on your own machine.
      </span>
    </div>
  );
}
