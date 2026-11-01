import { useEffect, useMemo, useState } from 'react';
import { jsPDF } from 'jspdf';
import { createAnalysis, getAnalysis, getHealth } from './services/api';

const ENGINE_LABELS = {
  'metadata-provenance': 'Metadata & Provenance',
  'model-fingerprint': 'Model Fingerprinting',
  'pixel-forensics': 'Pixel Forensics',
  'ai-content-detection': 'AI Content Detection',
  'watermark-detection': 'Watermark Detection',
  'visual-consistency': 'Visual Consistency',
};
const ESTIMATE_MS = 120000;
const sizeLabel = (bytes = 0) => bytes < 1024 * 1024 ? (bytes / 1024).toFixed(1) + ' KB' : (bytes / 1024 / 1024).toFixed(2) + ' MB';
const terminal = (status) => ['completed', 'partial', 'failed'].includes(String(status || '').toLowerCase());
const humanize = (key) => String(key).replace(/[_-]+/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/^./, (s) => s.toUpperCase());
const isEmpty = (v) => v === null || v === undefined || v === '';
const displayValue = (v) => typeof v === 'boolean' ? (v ? 'Yes' : 'No') : typeof v === 'number' ? String(v) : typeof v === 'string' ? v : JSON.stringify(v);
const flatten = (obj, prefix = '') => {
  if (!obj || typeof obj !== 'object') return [];
  return Object.entries(obj).flatMap(([key, value]) => {
    const label = prefix ? prefix + ' / ' + humanize(key) : humanize(key);
    if (isEmpty(value)) return [];
    if (Array.isArray(value)) return value.length ? [[label, value.map(displayValue).join(', ')]] : [];
    if (typeof value === 'object') return flatten(value, label);
    return [[label, displayValue(value)]];
  });
};
const rawFor = (item) => item?.result?.raw_result ?? item?.result ?? item?.raw_result ?? item ?? {};
const statusMessage = (item) => {
  const s = String(item?.status || '').toLowerCase();
  if (['failed', 'error'].includes(s)) return 'This engine could not complete its analysis. Review its status and technical details.';
  if (['waiting', 'queued', 'processing', 'running'].includes(s)) return 'This engine is still processing the submitted image.';
  if (!item) return 'No result was received from this engine. Evidence is not available for this check.';
  return 'The engine returned a result. Review the observations below; an absence of indicators is not proof that none exist.';
};
const download = (blob, name) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a'); a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
const safeName = (name) => (name || 'examination').replace(/[^a-z0-9._-]+/gi, '_');

export default function App() {
  const [file, setFile] = useState(null);
  const [health, setHealth] = useState('checking');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [startedAt, setStartedAt] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [timedOut, setTimedOut] = useState(false);
  const previewUrl = useMemo(() => file ? URL.createObjectURL(file) : '', [file]);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  useEffect(() => { getHealth().then(() => setHealth('online')).catch(() => setHealth('offline')); }, []);
  useEffect(() => {
    if (!startedAt || terminal(analysis?.status) || timedOut) return undefined;
    const timer = setInterval(() => {
      const now = Date.now();
      setElapsed(now - startedAt);
      if (now - startedAt >= ESTIMATE_MS) setTimedOut(true);
    }, 1000);
    return () => clearInterval(timer);
  }, [startedAt, analysis?.status, timedOut]);
  useEffect(() => {
    if (!analysis?.analysis_id || terminal(analysis.status) || timedOut) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const latest = await getAnalysis(analysis.analysis_id);
        if (!cancelled) setAnalysis(latest);
      } catch (err) {
        if (!cancelled) setError(err.message || 'Could not refresh analysis status.');
      }
    }, 2500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [analysis, timedOut]);

  async function submit(event) {
    event.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError(''); setAnalysis(null); setTimedOut(false); setElapsed(0);
    const start = Date.now(); setStartedAt(start);
    try { setAnalysis(await createAnalysis(file)); }
    catch (err) { setError(err.message || 'Could not queue analysis.'); setStartedAt(null); }
    finally { setBusy(false); }
  }

  const engineResults = analysis?.engine_results || {};
  const expected = analysis?.expected_engines || Object.keys(ENGINE_LABELS);
  const received = Object.keys(engineResults).length;
  const isComplete = terminal(analysis?.status);
  const rawBundle = { analysis, uploaded_file: file ? { name: file.name, size: file.size, type: file.type } : null };
  const downloadJson = () => download(new Blob([JSON.stringify(rawBundle, null, 2)], { type: 'application/json' }), safeName(analysis?.filename) + '-technical.json');

  async function downloadPdf() {
    if (!analysis) return;
    const pdf = new jsPDF({ unit: 'mm', format: 'a4' });
    const left = 18, right = 192, width = right - left;
    let y = 20;
    const page = () => { pdf.addPage(); y = 20; };
    const ensure = (h = 8) => { if (y + h > 278) page(); };
    const line = (text, opts = {}) => {
      const lines = pdf.splitTextToSize(String(text), width);
      ensure(lines.length * (opts.leading || 5) + 2);
      pdf.setFont('helvetica', opts.bold ? 'bold' : 'normal');
      pdf.setFontSize(opts.size || 9);
      pdf.text(lines, left, y);
      y += lines.length * (opts.leading || 5) + (opts.after ?? 2);
    };
    const heading = (text) => { ensure(12); pdf.setFont('helvetica', 'bold'); pdf.setFontSize(13); pdf.setTextColor(32, 52, 95); pdf.text(text, left, y); y += 8; pdf.setTextColor(35, 42, 55); };
    pdf.setFillColor(30, 48, 91); pdf.rect(0, 0, 210, 34, 'F');
    pdf.setTextColor(255, 255, 255); pdf.setFont('helvetica', 'bold'); pdf.setFontSize(20); pdf.text('ImForensic', left, 16);
    pdf.setFontSize(9); pdf.text('DIGITAL IMAGE EXAMINATION REPORT', left, 25);
    pdf.setTextColor(35, 42, 55); y = 45;
    line('Examination summary', { size: 16, bold: true, leading: 8, after: 5 });
    line('Analysis ID: ' + (analysis.analysis_id || 'Not supplied'));
    line('Status: ' + (analysis.status || 'Unknown') + '    |    Engines received: ' + received + ' / ' + expected.length);
    line('Filename: ' + (analysis.filename || file?.name || 'Not supplied'));
    line('File size: ' + sizeLabel(analysis.size_bytes || file?.size || 0));
    line('SHA-256: ' + (analysis.sha256 || 'Not supplied'));
    line('Elapsed time: ' + Math.floor(elapsed / 1000) + ' seconds');
    if (file && previewUrl) {
      try {
        const dataUrl = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
        ensure(65); heading('Submitted image');
        const format = file.type === 'image/png' ? 'PNG' : 'JPEG';
        pdf.addImage(dataUrl, format, left, y, 100, 56, undefined, 'FAST'); y += 61;
      } catch { line('Image preview could not be embedded in this report.'); }
    }
    heading('Engine findings');
    expected.forEach((name) => {
      const item = engineResults[name];
      ensure(18); line(ENGINE_LABELS[name] || humanize(name), { size: 11, bold: true, leading: 6, after: 1 });
      line('Status: ' + (item?.status || 'No result received'), { size: 8, after: 1 });
      line(statusMessage(item), { size: 8, after: 2 });
      const fields = flatten(rawFor(item));
      if (fields.length) fields.forEach(([k, v]) => line(k + ': ' + v, { size: 8, leading: 4.2, after: 1 }));
      else line('No structured observations were supplied by this engine.', { size: 8, after: 2 });
      y += 3;
    });
    if (analysis.correlation) {
      heading('Evidence correlation');
      line('Correlation status: ' + (analysis.correlation.status || 'Not supplied'));
      line('Received ' + (analysis.correlation.summary?.received_engine_count ?? received) + ' of ' + (analysis.correlation.summary?.expected_engine_count ?? expected.length) + ' expected engine results.');
      if (analysis.correlation.missing_engines?.length) line('Missing engines: ' + analysis.correlation.missing_engines.join(', '));
      if (analysis.correlation.conflicts?.length) line('Conflicting observations: ' + analysis.correlation.conflicts.length + '. Review original evidence; no winner is selected.');
    }
    heading('Interpretation and limitations');
    line('This report summarizes outputs returned by the configured forensic engines. “Not detected” does not establish confirmed absence. Missing or unavailable evidence is not a negative finding. Engine scores are not probabilities unless explicitly calibrated and documented by the source engine.');
    const pages = pdf.getNumberOfPages();
    for (let i = 1; i <= pages; i++) { pdf.setPage(i); pdf.setFontSize(8); pdf.setTextColor(120, 128, 142); pdf.text('ImForensic • Examination report • Page ' + i + ' of ' + pages, left, 289); }
    pdf.save(safeName(analysis.filename || file?.name) + '-examination-report.pdf');
  }

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
          <input id="image" type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => { setFile(e.target.files?.[0] || null); setAnalysis(null); setError(''); setStartedAt(null); setTimedOut(false); }} />
          {file && <p className="muted">{file.name} · {sizeLabel(file.size)}</p>}
          <button disabled={!file || busy || health === 'offline'}>{busy ? 'Submitting…' : 'Analyze with all six engines'}</button>
        </form>
        {error && <p className="error" role="alert">{error}</p>}
      </section>
      {analysis && <section className="panel" aria-live="polite">
        <div className="result-heading"><h2>Examination overview</h2><span className={'status ' + analysis.status}>{analysis.status}</span></div>
        {previewUrl && <div className="evidence-preview"><img src={previewUrl} alt="Uploaded evidence preview"/><div><strong>{file?.name}</strong><p className="muted">{sizeLabel(file?.size || 0)} · {file?.type || 'Image file'}</p></div></div>}
        <p className="muted">Analysis ID: <code>{analysis.analysis_id}</code></p>
        <dl>
          <div><dt>File</dt><dd>{analysis.filename || file?.name}</dd></div>
          <div><dt>Size</dt><dd>{sizeLabel(analysis.size_bytes || file?.size || 0)}</dd></div>
          <div><dt>SHA-256</dt><dd className="hash">{analysis.sha256 || 'Not supplied'}</dd></div>
          <div><dt>Engines received</dt><dd>{received} / {expected.length}</dd></div>
          <div><dt>Elapsed time</dt><dd>{Math.floor(elapsed / 1000)} seconds</dd></div>
          <div><dt>Estimated window</dt><dd>About 2 minutes (indicative)</dd></div>
        </dl>
        <div className="progress-track"><div className="progress-fill" style={{ width: Math.min(100, received / Math.max(expected.length, 1) * 100) + '%' }}/></div>
        <p className="muted">{received} of {expected.length} engine results received.</p>
        {timedOut && !isComplete && <p className="notice" role="status">Analysis is taking longer than expected. Please wait a while. No further action has been taken. Automatic status checks have stopped.</p>}
        {!isComplete && !timedOut && <p className="muted">Analysis is in progress. Status refreshes automatically until completion or the estimated waiting window expires.</p>}
        <h3>Engine findings</h3>
        <div className="engine-grid">
          {expected.map((name) => {
            const item = engineResults[name];
            const fields = flatten(rawFor(item));
            return <article className="engine-card" key={name}>
              <div className="result-heading"><h4>{ENGINE_LABELS[name] || humanize(name)}</h4><span className={'status ' + (item?.status || 'waiting')}>{item?.status || 'waiting'}</span></div>
              <p>{statusMessage(item)}</p>
              {fields.length ? <dl className="finding-list">{fields.map(([label, value], index) => <div key={index}><dt>{label}</dt><dd>{value}</dd></div>)}</dl> : <p className="muted">No structured observations were returned. See technical details for the original response.</p>}
              <details><summary>Technical details · Original JSON</summary><pre>{JSON.stringify(rawFor(item), null, 2)}</pre></details>
            </article>;
          })}
        </div>
        {analysis.correlation && <>
          <h3>Evidence correlation</h3>
          <p>Correlation status: <strong>{analysis.correlation.status}</strong></p>
          <p className="muted">Received {analysis.correlation.summary?.received_engine_count ?? received} of {analysis.correlation.summary?.expected_engine_count ?? expected.length} expected engine results. Scores are not averaged.</p>
          {analysis.correlation.missing_engines?.length > 0 && <p className="error">Missing: {analysis.correlation.missing_engines.join(', ')}</p>}
          {analysis.correlation.conflicts?.length > 0 && <p>Conflicting explicit observations: {analysis.correlation.conflicts.length}. Review the source evidence; no winner is selected.</p>}
        </>}
        <div className="download-panel"><div><h3>Examination downloads</h3><p className="muted">Download the original machine-readable evidence or a formatted A4 report.</p></div><div className="download-actions"><button type="button" onClick={downloadJson}><span aria-hidden="true">↓</span> Download Technical JSON</button><button type="button" className="secondary-button" onClick={downloadPdf}><span aria-hidden="true">↓</span> Download A4 PDF Report</button></div></div>
        {analysis.error && <p className="error">{analysis.error}</p>}
      </section>}
      <p className="footer">A completed execution means the configured engine returned a result. It does not mean the image is authentic. Configure production secrets, access control, retention and encryption before deployment.</p>
    </main>
  );
}