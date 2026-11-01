import { useEffect, useMemo, useRef, useState } from 'react';
import { createAnalysis, getAnalysis, getHealth } from './services/api';

const ENGINES = [
  ['metadata-provenance', 'Metadata & provenance', 'EXIF, file properties and provenance indicators'],
  ['model-fingerprint', 'Model fingerprinting', 'Known model or generator fingerprint signals'],
  ['pixel-forensics', 'Pixel forensics', 'Image-level inconsistencies and pixel artefacts'],
  ['ai-content-detection', 'AI content detection', 'Model-based synthetic-content indicators'],
  ['watermark-detection', 'Watermark detection', 'Visible and machine-detectable watermark signals'],
  ['visual-consistency', 'Visual consistency', 'Cross-region and visual coherence observations'],
];
const TERMINAL = ['completed', 'partial', 'failed'];
const MAX_BYTES = 20 * 1024 * 1024;
const formatBytes = (n = 0) => n < 1024 * 1024 ? (n / 1024).toFixed(1) + ' KB' : (n / 1024 / 1024).toFixed(2) + ' MB';
const pretty = (value) => JSON.stringify(value ?? {}, null, 2);
const safeDate = (value) => value ? new Date(value).toLocaleString() : '—';

function Status({ value = 'waiting' }) {
  const label = String(value).replaceAll('_', ' ');
  return <span className={'status status-' + String(value).toLowerCase()}>{label}</span>;
}
function Findings({ item }) {
  const result = item?.result || item || {};
  const findings = result.findings ?? result.observations ?? result.summary;
  if (Array.isArray(findings) && findings.length) return <ul className="finding-list">{findings.slice(0, 8).map((f, i) => <li key={i}>{typeof f === 'string' ? f : f.description || f.message || f.name || pretty(f)}</li>)}</ul>;
  if (typeof findings === 'string' && findings) return <p className="finding-text">{findings}</p>;
  return <p className="muted small">No normalized findings supplied by this engine.</p>;
}
export default function App() {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [health, setHealth] = useState('checking');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const inputRef = useRef(null);

  useEffect(() => {
    let alive = true;
    getHealth().then(() => alive && setHealth('online')).catch(() => alive && setHealth('offline'));
    const id = setInterval(() => getHealth().then(() => alive && setHealth('online')).catch(() => alive && setHealth('offline')), 15000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  useEffect(() => {
    if (!analysis?.analysis_id || TERMINAL.includes(analysis.status)) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const latest = await getAnalysis(analysis.analysis_id);
        if (!cancelled) { setAnalysis(latest); setLastUpdated(new Date()); }
      } catch (e) { if (!cancelled) setError('Status refresh failed: ' + e.message); }
    }, 2500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [analysis]);

  const expected = analysis?.expected_engines?.length ? analysis.expected_engines : ENGINES.map(([id]) => id);
  const results = analysis?.engine_results || {};
  const received = Object.keys(results).length;
  const correlation = analysis?.correlation;
  const progress = expected.length ? Math.min(100, Math.round(received / expected.length * 100)) : 0;
  const resultFilename = useMemo(() => analysis?.filename || file?.name || 'No evidence selected', [analysis, file]);

  function choose(candidate) {
    setError('');
    if (!candidate) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(candidate.type)) { setFile(null); setError('Unsupported format. Select a JPEG, PNG or WebP image.'); return; }
    if (candidate.size > MAX_BYTES) { setFile(null); setError('The selected image exceeds the 20 MB upload limit.'); return; }
    setFile(candidate); setAnalysis(null); setLastUpdated(null);
  }
  async function submit(e) {
    e.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError(''); setAnalysis(null);
    try {
      const queued = await createAnalysis(file);
      setAnalysis(queued); setLastUpdated(new Date());
    } catch (e) { setError(e.message || 'Unable to submit the image.'); }
    finally { setBusy(false); }
  }
  function downloadReport() {
    if (!analysis) return;
    const blob = new Blob([pretty(analysis)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'imforensic-' + analysis.analysis_id + '.json'; a.click();
    URL.revokeObjectURL(url);
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">IF</div><div><strong>ImForensic</strong><span>IMAGE EXAMINATION SYSTEM</span></div></div>
      <div className="side-rule" />
      <p className="side-label">WORKSPACE</p>
      <a className="nav-item active" href="#intake"><span>▣</span> Evidence intake</a>
      <a className="nav-item" href="#examination"><span>▤</span> Examination results</a>
      <a className="nav-item" href="#correlation"><span>⌘</span> Evidence correlation</a>
      <div className="sidebar-bottom"><span className={'pulse ' + health}></span><div><b>API gateway</b><small>{health === 'online' ? 'Connection available' : health === 'checking' ? 'Checking connection…' : 'Connection unavailable'}</small></div></div>
    </aside>
    <main className="main-area">
      <header className="page-header"><div><div className="breadcrumb">FORENSIC WORKSPACE <span>/</span> IMAGE ANALYSIS</div><h1>Image examination</h1><p>Submit digital image evidence for independent engine-based examination.</p></div><div className="header-status"><span className={'pulse ' + health}></span> Gateway {health}</div></header>
      <div className="notice"><b>Evidence handling notice</b><span>Automated findings are technical observations. They do not, by themselves, establish authenticity, authorship, manipulation or AI generation.</span></div>

      <section id="intake" className="section-block">
        <div className="section-heading"><div><span className="section-index">01</span><div><h2>Evidence intake</h2><p>Register an image and initiate the examination workflow.</p></div></div><span className="protocol">JPEG · PNG · WEBP / MAX 20 MB</span></div>
        <form className="intake-card" onSubmit={submit}>
          <div className={'drop-zone ' + (dragging ? 'dragging' : '')} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files?.[0]); }}>
            <input ref={inputRef} type="file" accept="image/jpeg,image/png,image/webp" onChange={e => choose(e.target.files?.[0])} />
            <div className="upload-symbol">↑</div><b>{file ? file.name : 'Select image evidence'}</b><span>{file ? formatBytes(file.size) + ' · ' + file.type : 'Drag and drop a file here, or browse your device'}</span>
            <button type="button" className="button-secondary" onClick={() => inputRef.current?.click()}>Browse files</button>
          </div>
          <div className="intake-actions"><div><b>Examination scope</b><small>All six configured forensic engines will be requested.</small></div><button className="button-primary" disabled={!file || busy || health !== 'online'}>{busy ? 'Submitting evidence…' : 'Submit for examination  →'}</button></div>
          {error && <p className="error-message" role="alert">{error}</p>}
        </form>
      </section>

      {analysis && <>
        <section className="section-block" id="examination">
          <div className="section-heading"><div><span className="section-index">02</span><div><h2>Examination record</h2><p>Submission identity, integrity reference and processing state.</p></div></div><button className="button-secondary export-button" onClick={downloadReport}>↓ Export JSON</button></div>
          <div className="record-card">
            <div className="record-top"><div><span className="field-label">EXAMINATION IDENTIFIER</span><code>{analysis.analysis_id}</code></div><Status value={analysis.status} /></div>
            <div className="record-grid"><div><span className="field-label">Evidence file</span><b>{resultFilename}</b></div><div><span className="field-label">Submitted</span><b>{safeDate(analysis.created_at)}</b></div><div><span className="field-label">File size</span><b>{formatBytes(analysis.size_bytes || 0)}</b></div><div><span className="field-label">Media type</span><b>{analysis.content_type || '—'}</b></div></div>
            <div className="hash-row"><span className="field-label">SHA-256 INTEGRITY REFERENCE</span><code>{analysis.sha256 || 'Not returned by gateway'}</code></div>
            <div className="progress-head"><b>Engine response collection</b><span>{received} / {expected.length} received</span></div><div className="progress-track"><div style={{width: progress + '%'}} /></div>
            <small className="muted">Last refreshed: {lastUpdated ? lastUpdated.toLocaleTimeString() : 'Awaiting first refresh'}</small>
          </div>
          <div className="engine-grid">{expected.map(name => {
            const meta = ENGINES.find(x => x[0] === name) || [name, name, 'Configured analysis engine'];
            const item = results[name]; const status = item?.status || 'waiting';
            return <article className="engine-card" key={name}><div className="engine-card-head"><span className="engine-code">{String(expected.indexOf(name) + 1).padStart(2, '0')}</span><Status value={status} /></div><h3>{meta[1]}</h3><p>{meta[2]}</p><Findings item={item} />{item && <details className="raw-details"><summary>Inspect engine response</summary><pre>{pretty(item.result?.raw_result ?? item.result ?? item)}</pre></details>}</article>;
          })}</div>
        </section>

        <section className="section-block" id="correlation">
          <div className="section-heading"><div><span className="section-index">03</span><div><h2>Evidence correlation</h2><p>Cross-engine observations and execution completeness.</p></div></div>{correlation && <Status value={correlation.status} />}</div>
          <div className="correlation-card">
            {!correlation ? <div className="pending-correlation"><b>Correlation report pending</b><p className="muted">The consolidated report will appear when the backend evidence-correlation service returns it.</p></div> : <>
              <div className="metric-row"><div><span className="field-label">RESULTS RECEIVED</span><strong>{correlation.summary?.received_engine_count ?? received}<small> / {correlation.summary?.expected_engine_count ?? expected.length}</small></strong></div><div><span className="field-label">OBSERVATION CONFLICTS</span><strong>{correlation.summary?.conflict_count ?? correlation.conflicts?.length ?? 0}</strong></div><div><span className="field-label">SCORES AGGREGATED</span><strong>{correlation.summary?.scores_aggregated === true ? 'Yes' : 'No'}</strong></div></div>
              {correlation.missing_engines?.length > 0 && <p className="review-line"><b>Missing engines:</b> {correlation.missing_engines.join(', ')}</p>}
              {correlation.failed_engines?.length > 0 && <p className="review-line"><b>Failed engines:</b> {correlation.failed_engines.join(', ')}</p>}
              {correlation.partial_engines?.length > 0 && <p className="review-line"><b>Partial engines:</b> {correlation.partial_engines.join(', ')}</p>}
              {correlation.conflicts?.length > 0 && <div className="review-block"><b>Conflicting observations</b><pre>{pretty(correlation.conflicts)}</pre></div>}
              {correlation.limitations?.length > 0 && <div className="review-block"><b>Method limitations</b><ul>{correlation.limitations.map((x,i)=><li key={i}>{typeof x === 'string' ? x : pretty(x)}</li>)}</ul></div>}
              <details className="raw-details"><summary>Inspect complete correlation payload</summary><pre>{pretty(correlation)}</pre></details>
            </>}
          </div>
          <p className="method-note"><b>Interpretation boundary</b> ImForensic reports independent engine outputs and explicit evidence relationships. It does not calculate a combined authenticity verdict or calibrated probability. Any engine-specific score must be interpreted using that engine's documented semantics.</p>
        </section>
      </>}
      <footer className="page-footer">IMFORENSIC · DIGITAL IMAGE EXAMINATION <span>Internal analytical workspace · Verify findings against source evidence</span></footer>
    </main>
  </div>;
}
