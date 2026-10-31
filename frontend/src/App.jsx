import { useEffect, useState } from 'react';
import { createAnalysis, getHealth } from './services/api';

const sizeLabel = (bytes) => (bytes / 1024).toFixed(1) + ' KB';

export default function App() {
  const [file, setFile] = useState(null);
  const [health, setHealth] = useState('checking');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [analysis, setAnalysis] = useState(null);

  useEffect(() => {
    getHealth().then(() => setHealth('online')).catch(() => setHealth('offline'));
  }, []);

  async function submit(event) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError(''); setAnalysis(null);
    try { setAnalysis(await createAnalysis(file)); }
    catch (err) { setError(err.message || 'Analysis failed.'); }
    finally { setBusy(false); }
  }

  const engineResults = analysis?.engine_results || {};

  return (
    <main className="shell">
      <header className="topbar">
        <div><p className="eyebrow">IMAGE FORENSICS WORKSPACE</p><h1>ImForensic</h1></div>
        <span className={'health ' + health}>API {health}</span>
      </header>
      <p className="intro">Examine image metadata and descriptive image features. Findings are evidence to investigate—not proof of authenticity, manipulation, or AI generation.</p>
      <section className="panel">
        <h2>Start an analysis</h2>
        <p className="muted">JPEG, PNG or WebP · Maximum 20 MB</p>
        <form onSubmit={submit}>
          <label htmlFor="image">Choose an image</label>
          <input id="image" type="file" accept="image/jpeg,image/png,image/webp"
            onChange={(e) => { setFile(e.target.files?.[0] || null); setAnalysis(null); setError(''); }} />
          {file && <p className="muted">{file.name} · {sizeLabel(file.size)}</p>}
          <button disabled={!file || busy || health === 'offline'}>{busy ? 'Analyzing…' : 'Analyze image'}</button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
      </section>
      {analysis && <section className="panel" aria-live="polite">
        <div className="result-heading"><h2>Analysis result</h2><span className={'status ' + analysis.status}>{analysis.status}</span></div>
        <p className="muted">ID: <code>{analysis.analysis_id}</code></p>
        <dl>
          <div><dt>File</dt><dd>{analysis.filename}</dd></div>
          <div><dt>Size</dt><dd>{sizeLabel(analysis.size_bytes)}</dd></div>
          <div><dt>SHA-256</dt><dd className="hash">{analysis.sha256}</dd></div>
        </dl>
        <h3>Engine results</h3>
        <dl>
          <div><dt>Metadata &amp; Provenance</dt><dd>{engineResults['metadata-provenance']?.status || 'Not reported'}</dd></div>
          <div><dt>Model Fingerprinting</dt><dd>{engineResults['model-fingerprint']?.status || 'Not reported'}</dd></div>
          <div><dt>Fingerprint outcome</dt><dd>{engineResults['model-fingerprint']?.result?.findings?.outcome || 'Unavailable'}</dd></div>
        </dl>
        {analysis.error && <p className="error">{analysis.error}</p>}
        {analysis.result && <>
          <h3>Image properties</h3>
          <dl>
            <div><dt>Format</dt><dd>{analysis.result.file.format}</dd></div>
            <div><dt>Dimensions</dt><dd>{analysis.result.file.width} × {analysis.result.file.height}</dd></div>
            <div><dt>EXIF present</dt><dd>{analysis.result.metadata.exif_present ? 'Yes' : 'No'}</dd></div>
            <div><dt>Software tag</dt><dd>{analysis.result.metadata.software_tag || 'Not present'}</dd></div>
            <div><dt>XMP present</dt><dd>{analysis.result.metadata.xmp_present ? 'Yes' : 'No'}</dd></div>
            <div><dt>C2PA verified</dt><dd>No — verification is not implemented</dd></div>
          </dl>
          <h3>Interpretation limits</h3>
          <ul>{analysis.result.observations.map((item) => <li key={item}>{item}</li>)}</ul>
        </>}
        {engineResults['model-fingerprint']?.result?.warnings?.length > 0 && <>
          <h3>Model Fingerprinting limitations</h3>
          <ul>{engineResults['model-fingerprint'].result.warnings.map((item) => <li key={item}>{item}</li>)}</ul>
        </>}
      </section>}
      <p className="footer">Configure retention, access control and encryption before production deployment.</p>
    </main>
  );
}
