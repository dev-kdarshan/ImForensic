import { useEffect, useState } from 'react';
import { createAnalysis, getAnalysis, getHealth } from './services/api';

const ENGINE_LABELS = {
  'metadata-provenance': 'Metadata & Provenance',
  'model-fingerprint': 'Model Fingerprinting',
  'pixel-forensics': 'Pixel Forensics',
  'ai-content-detection': 'AI Content Detection',
  'watermark-detection': 'Watermark Detection',
  'visual-consistency': 'Visual Consistency',
};
const sizeLabel = (bytes) => (bytes / 1024).toFixed(1) + ' KB';
const terminal = (status) => ['completed', 'partial', 'failed'].includes(status);

export default function App() {
  const [file, setFile] = useState(null);
  const [health, setHealth] = useState('checking');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [analysis, setAnalysis] = useState(null);

  useEffect(() => {
    getHealth().then(() => setHealth('online')).catch(() => setHealth('offline'));
  }, []);

  useEffect(() => {
    if (!analysis?.analysis_id || terminal(analysis.status)) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const latest = await getAnalysis(analysis.analysis_id);
        if (!cancelled) setAnalysis(latest);
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not refresh analysis status.');
      }
    }, 2000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [analysis]);

  async function submit(event) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError(''); setAnalysis(null);
    try { setAnalysis(await createAnalysis(file)); }
    catch (err) { setError(err.message || 'Could not queue analysis.'); }
    finally { setBusy(false); }
  }

  const engineResults = analysis?.engine_results || {};
  const expected = analysis?.expected_engines || Object.keys(ENGINE_LABELS);

  return (
    <main className="shell">
      <header className="topbar">
        <div><p className="eyebrow">IMAGE FORENSICS WORKSPACE</p><h1>ImForensic</h1></div>
        <span className={'health ' + health}>API {health}</span>
      </header>
      <p className="intro">Six independent forensic engines analyze the same uploaded image. Their findings are evidence to investigate—not proof of authenticity, manipulation, or AI generation.</p>
      <section className="panel">
        <h2>Start an analysis</h2>
        <p className="muted">JPEG, PNG or WebP · Maximum 20 MB · Processing runs asynchronously through Kafka</p>
        <form onSubmit={submit}>
          <label htmlFor="image">Choose an image</label>
          <input id="image" type="file" accept="image/jpeg,image/png,image/webp"
            onChange={(e) => { setFile(e.target.files?.[0] || null); setAnalysis(null); setError(''); }} />
          {file && <p className="muted">{file.name} · {sizeLabel(file.size)}</p>}
          <button disabled={!file || busy || health === 'offline'}>{busy ? 'Submitting…' : 'Analyze with all six engines'}</button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
      </section>
      {analysis && <section className="panel" aria-live="polite">
        <div className="result-heading"><h2>Analysis status</h2><span className={'status ' + analysis.status}>{analysis.status}</span></div>
        <p className="muted">ID: <code>{analysis.analysis_id}</code></p>
        <dl>
          <div><dt>File</dt><dd>{analysis.filename}</dd></div>
          <div><dt>Size</dt><dd>{sizeLabel(analysis.size_bytes || 0)}</dd></div>
          <div><dt>SHA-256</dt><dd className="hash">{analysis.sha256}</dd></div>
          <div><dt>Engines received</dt><dd>{Object.keys(engineResults).length} / {expected.length}</dd></div>
        </dl>
        <h3>Engine execution</h3>
        <dl>
          {expected.map((name) => {
            const item = engineResults[name];
            const status = item?.status || 'waiting';
            return <div key={name}><dt>{ENGINE_LABELS[name] || name}</dt><dd><span className={'status ' + status}>{status}</span></dd></div>;
          })}
        </dl>
        {analysis.status === 'queued' || analysis.status === 'processing'
          ? <p className="muted">The engines are working. This page refreshes the status automatically.</p> : null}
        {analysis.correlation && <>
          <h3>Evidence correlation</h3>
          <p>Correlation status: <strong>{analysis.correlation.status}</strong></p>
          <p className="muted">Received {analysis.correlation.summary?.received_engine_count ?? 0} of {analysis.correlation.summary?.expected_engine_count ?? expected.length} expected engine results. Scores are not averaged.</p>
          {analysis.correlation.missing_engines?.length > 0 && <p className="error">Missing: {analysis.correlation.missing_engines.join(', ')}</p>}
          {analysis.correlation.conflicts?.length > 0 && <p>Conflicting explicit observations: {analysis.correlation.conflicts.length}. Review the source evidence; no winner is selected.</p>}
        </>}
        {Object.entries(engineResults).map(([name, item]) => (
          <details key={name}>
            <summary>{ENGINE_LABELS[name] || name} — view structured result</summary>
            <pre>{JSON.stringify(item.result?.raw_result || item.result || {}, null, 2)}</pre>
          </details>
        ))}
        {analysis.error && <p className="error">{analysis.error}</p>}
      </section>}
      <p className="footer">A completed execution means the configured engine returned a result. It does not mean the image is authentic. Configure production secrets, access control, retention and encryption before deployment.</p>
    </main>
  );
}
