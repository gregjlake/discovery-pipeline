import { useEffect, useState } from "react";
import { fetchProvenance, type ProvenanceInfo } from "../lib/api";

interface Props {
  datasetX: string;
  datasetY: string;
}

function ProvCard({ info }: { info: ProvenanceInfo }) {
  return (
    <div className="prov-card">
      <h4>{info.source_name}</h4>
      <table>
        <tbody>
          <tr><td>Source</td><td><a href={info.source_url} target="_blank" rel="noreferrer">{info.source_url}</a></td></tr>
          <tr><td>Downloaded</td><td>{info.download_date}</td></tr>
          <tr><td>Counties</td><td>{info.counties_matched}</td></tr>
          <tr><td>Range</td><td>{info.raw_min} – {info.raw_max} (mean {info.raw_mean})</td></tr>
          <tr><td>Missing</td><td>{info.missing_values}</td></tr>
          <tr><td>Hash</td><td className="hash">{info.file_hash?.slice(0, 16)}…</td></tr>
        </tbody>
      </table>
    </div>
  );
}

export default function ProvenancePanel({ datasetX, datasetY }: Props) {
  const [provX, setProvX] = useState<ProvenanceInfo | null>(null);
  const [provY, setProvY] = useState<ProvenanceInfo | null>(null);

  useEffect(() => {
    fetchProvenance(datasetX).then(setProvX).catch(() => setProvX(null));
    fetchProvenance(datasetY).then(setProvY).catch(() => setProvY(null));
  }, [datasetX, datasetY]);

  return (
    <div className="panel-section">
      <h3>Provenance</h3>
      {provX && <ProvCard info={provX} />}
      {provY && <ProvCard info={provY} />}
    </div>
  );
}
