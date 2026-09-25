import React from "react";
import { loadSnapshotData } from "@/lib/chat/tools";

export default function HomePage() {
  const { catalog, countries, manifest } = loadSnapshotData();
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-8">
      <header className="max-w-6xl mx-auto border-b border-slate-800 pb-6 mb-8">
        <span className="text-xs uppercase tracking-widest text-teal-400 font-mono">
          Snapshot Versionado · {manifest.snapshot_id} · DOI: {manifest.zenodo_doi}
        </span>
        <h1 className="text-4xl font-serif font-bold mt-2">
          Observatorio de Desarrollo de América Latina y el Caribe
        </h1>
        <p className="text-slate-400 mt-2">
          {manifest.total_observations.toLocaleString()} observaciones verificadas ·{" "}
          {catalog.indicators.length} indicadores · {countries.priority_countries.length} países prioritarios (COL, CHL, CRI, BRA, MEX)
        </p>
      </header>
    </main>
  );
}
