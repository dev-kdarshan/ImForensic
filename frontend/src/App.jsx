import { useEffect, useMemo, useRef, useState } from 'react';
import { jsPDF } from 'jspdf';
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
const ESTIMATE_MS = 120000;
const formatBytes = (n = 0) => n < 1024 * 1024 ? (n / 1024).toFixed(1) + ' KB' : (n / 1024 / 1024).toFixed(2) + ' MB';
const pretty = (value) => JSON.stringify(value ?? {}, null, 2);
const safeDate = (value) => value ? new Date(value).toLocaleString() : '—';
const humanize = (value) => String(value).replace(/[_-]+/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').replace(/^./, c => c.toUpperCase());
const rawFor = (item) => item?.result?.raw_result ?? item?.result ?? item?.raw_result ?? item ?? {};
const statusMessage = (item) => {
  if (!item) return 'No result received. Evidence is not available for this check.';
  const status = String(item.status || '').toLowerCase();
  if (['failed', 'error'].includes(status)) return 'This engine could not complete its analysis. Review the execution status and technical response.';
  if (['queued', 'waiting', 'processing', 'running'].includes(status)) return 'This engine is processing the submitted evidence.';
  return 'The engine returned a response. Review the observations below; absence of an indicator is not proof that none exists.';
};
const flatten = (value, prefix = '', out = []) => {
  if (!value || typeof value !== 'object') return out;
  Object.entries(value).forEach(([key, item]) => {
    if (item === null || item === undefined || item === '') return;
    const label = prefix ? prefix + ' / ' + humanize(key) : humanize(key);
    if (Array.isArray(item)) {
      if (item.length) out.push([label, item.map(x => typeof x === 'object' ? pretty(x) : String(x)).join('; ')]);
    } else if (typeof item === 'object') flatten(item, label, out);
    else out.push([label, typeof item === 'boolean' ? (item ? 'Yes' : 'No') : String(item)]);
  });
  return out;
};
const downloadBlob = (blob, filename) => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url; anchor.download = filename; anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
};
const safeName = (name) => (name || 'examination').replace(/[^a-z0-9._-]+/gi, '_');

function Status({ value = 'waiting' }) {
  const label = String(value).replaceAll('_', ' ');
  return <span className={'status status-' + String(value).toLowerCase()}>{label}</span>;
}
function getAiAssessment(item) {
  if (!item) return { label: 'AI-generation assessment unavailable', detail: 'The AI content detection engine has not returned a result.' };
  const data = rawFor(item);
  const sources = [data, data.findings, data.observations, data.result, data.output].filter(Boolean);
  for (const source of sources) {
    if (typeof source !== 'object') continue;
    for (const key of ['is_ai_generated', 'ai_generated', 'is_synthetic', 'synthetic']) {
      if (typeof source[key] === 'boolean') return { label: source[key] ? 'AI-generated indicators reported' : 'AI-generated indicators not reported', detail: 'Based on the engine boolean field ' + key + '. This is an engine-specific result, not proof of origin.' };
    }
    for (const key of ['classification', 'prediction', 'predicted_label', 'label', 'verdict', 'decision']) {
      if (typeof source[key] === 'string' && source[key].trim()) return { label: humanize(source[key]), detail: 'Classification returned by the AI content detection engine. Interpret using the engine documented score semantics.' };
    }
  }
  const scores = flatten(data).filter(([key]) => /score|confidence/i.test(key));
  if (scores.length) return { label: 'AI detection score returned; no explicit classification', detail: scores.slice(0, 2).map(([key, value]) => key + ': ' + value).join(' · ') + '. A score alone is not a probability or a definitive AI-generation verdict.' };
  return { label: 'AI-generation assessment inconclusive from returned fields', detail: 'No recognized classification field was returned. Inspect the technical response; no AI-generated/not-AI-generated conclusion can be supported.' };
}
function Findings({ item }) {
  if (!item) return <p className="muted small">No engine response has been received yet.</p>;
  const result = item.result?.raw_result ?? item.result ?? item;
  const findings = result.findings ?? result.observations ?? result.summary;
  if (Array.isArray(findings) && findings.length) return <ul className="finding-list">{findings.slice(0, 8).map((f, i) => <li key={i}>{typeof f === 'string' ? f : f.description || f.message || f.name || pretty(f)}</li>)}</ul>;
  if (typeof findings === 'string' && findings) return <p className="finding-text">{findings}</p>;
  const candidates = flatten(result).filter(([key]) => !/score|confidence|probability/i.test(key)).slice(0, 5);
  if (candidates.length) return <dl className="finding-facts">{candidates.map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}</dl>;
  return <p className="muted small">No normalized findings supplied by this engine. Consult the technical response for available measurements.</p>;
}

export default function App() {
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [health, setHealth] = useState('checking');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [analysis, setAnalysis] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [startedAt, setStartedAt] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [timedOut, setTimedOut] = useState(false);
  const inputRef = useRef(null);
  const previewUrl = useMemo(() => file ? URL.createObjectURL(file) : '', [file]);

  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]);
  useEffect(() => {
    let alive = true;
    getHealth().then(() => alive && setHealth('online')).catch(() => alive && setHealth('offline'));
    const id = setInterval(() => getHealth().then(() => alive && setHealth('online')).catch(() => alive && setHealth('offline')), 15000);
    return () => { alive = false; clearInterval(id); };
  }, []);
  useEffect(() => {
    if (!startedAt || TERMINAL.includes(analysis?.status) || timedOut) return undefined;
    const id = setInterval(() => {
      const duration = Date.now() - startedAt;
      setElapsed(duration);
      if (duration >= ESTIMATE_MS) setTimedOut(true);
    }, 1000);
    return () => clearInterval(id);
  }, [startedAt, analysis?.status, timedOut]);
  useEffect(() => {
    if (!analysis?.analysis_id || TERMINAL.includes(analysis.status) || timedOut) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const latest = await getAnalysis(analysis.analysis_id);
        if (!cancelled) { setAnalysis(latest); setLastUpdated(new Date()); }
      } catch (e) { if (!cancelled) setError('Status refresh failed: ' + e.message); }
    }, 2500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [analysis, timedOut]);

  const expected = analysis?.expected_engines?.length ? analysis.expected_engines : ENGINES.map(([id]) => id);
  const results = analysis?.engine_results || {};
  const received = Object.keys(results).length;
  const correlation = analysis?.correlation;
  const progress = expected.length ? Math.min(100, Math.round(received / expected.length * 100)) : 0;
  const resultFilename = analysis?.filename || file?.name || 'No evidence selected';
  const isComplete = TERMINAL.includes(analysis?.status);
  const elapsedLabel = Math.floor(elapsed / 60000) + ':' + String(Math.floor((elapsed % 60000) / 1000)).padStart(2, '0');

  function choose(candidate) {
    setError('');
    if (!candidate) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(candidate.type)) { setError('Unsupported format. Select a JPEG, PNG or WebP image.'); return; }
    if (candidate.size > MAX_BYTES) { setError('The selected image exceeds the 20 MB upload limit.'); return; }
    setFile(candidate); setAnalysis(null); setLastUpdated(null); setStartedAt(null); setElapsed(0); setTimedOut(false);
  }
  async function submit(e) {
    e.preventDefault();
    if (!file || busy) return;
    setBusy(true); setError(''); setAnalysis(null); setTimedOut(false); setElapsed(0);
    const start = Date.now(); setStartedAt(start);
    try {
      const queued = await createAnalysis(file);
      setAnalysis(queued); setLastUpdated(new Date());
    } catch (e) { setError(e.message || 'Unable to submit the image.'); setStartedAt(null); }
    finally { setBusy(false); }
  }
  function downloadTechnicalJson() {
    if (!analysis) return;
    const bundle = { analysis, uploaded_file: file ? { name: file.name, size: file.size, type: file.type } : null };
    downloadBlob(new Blob([pretty(bundle)], { type: 'application/json' }), 'imforensic-' + safeName(analysis.analysis_id) + '-technical.json');
  }
  async function downloadPdf() {
    if (!analysis) return;
    const pdf = new jsPDF({ unit: 'mm', format: 'a4' });
    const left = 17, width = 176;
    let y = 20;
    const addPage = () => { pdf.addPage(); y = 19; };
    const ensure = (height = 8) => { if (y + height > 276) addPage(); };
    const write = (text, size = 9, bold = false) => {
      pdf.setFont('helvetica', bold ? 'bold' : 'normal'); pdf.setFontSize(size);
      const lines = pdf.splitTextToSize(String(text), width);
      ensure(lines.length * 4.5 + 3); pdf.text(lines, left, y); y += lines.length * 4.5 + 2;
    };
    const section = (text) => { ensure(12); y += 3; pdf.setFont('helvetica', 'bold'); pdf.setFontSize(12); pdf.setTextColor(35, 65, 91); pdf.text(text, left, y); y += 7; pdf.setTextColor(35, 43, 52); };
    pdf.setFillColor(20, 43, 69); pdf.rect(0, 0, 210, 34, 'F');
    pdf.setTextColor(255,255,255); pdf.setFont('helvetica','bold'); pdf.setFontSize(19); pdf.text('ImForensic', left, 15);
    pdf.setFontSize(8); pdf.text('DIGITAL IMAGE EXAMINATION REPORT', left, 23);
    pdf.setFont('helvetica','normal'); pdf.text('EXAMINATION RECORD', left, 29);
    pdf.setTextColor(35,43,52); y = 43;
    write('Examination summary', 15, true);
    write('Examination ID: ' + (analysis.analysis_id || 'Not supplied'));
    write('Execution status: ' + (analysis.status || 'Unknown') + '     Engine responses: ' + received + ' / ' + expected.length);
    write('Evidence file: ' + resultFilename);
    write('File size: ' + formatBytes(analysis.size_bytes || file?.size || 0));
    write('Media type: ' + (analysis.content_type || file?.type || 'Not supplied'));
    write('Submitted: ' + safeDate(analysis.created_at));
    write('SHA-256: ' + (analysis.sha256 || 'Not returned by gateway'));
    if (file) {
      try {
        const data = await new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
        section('Submitted evidence image');
        const format = file.type === 'image/png' ? 'PNG' : 'JPEG';
        pdf.addImage(data, format, left, y, 92, 55, undefined, 'FAST'); y += 59;
      } catch { write('The submitted image could not be embedded in this report.'); }
    }
    section('Engine examination findings');
    expected.forEach((id, index) => {
      const meta = ENGINES.find(x => x[0] === id) || [id, humanize(id), 'Configured examination engine'];
      const item = results[id];
      ensure(22);
      write(String(index + 1).padStart(2, '0') + '  ' + meta[1], 10, true);
      write('Execution status: ' + (item?.status || 'No response received'), 8, true);
      write(statusMessage(item), 8);
      const result = rawFor(item);
      const normalized = result.findings ?? result.observations ?? result.summary;
      if (Array.isArray(normalized) && normalized.length) normalized.slice(0, 8).forEach(f => write('• ' + (typeof f === 'string' ? f : f.description || f.message || f.name || 'Observation recorded'), 8));
      else if (typeof normalized === 'string' && normalized) write(normalized, 8);
      else {
        const facts = flatten(result).filter(([key]) => !/score|confidence|probability/i.test(key)).slice(0, 4);
        if (facts.length) facts.forEach(([key, value]) => write(key + ': ' + value, 8));
        else write('No normalized observations were supplied by this engine.', 8);
      }
      y += 2;
    });
    if (correlation) {
      section('Evidence correlation');
      write('Correlation status: ' + (correlation.status || 'Not supplied'));
      write('Engine responses received: ' + (correlation.summary?.received_engine_count ?? received) + ' / ' + (correlation.summary?.expected_engine_count ?? expected.length));
      write('Observation conflicts: ' + (correlation.summary?.conflict_count ?? correlation.conflicts?.length ?? 0));
      if (correlation.missing_engines?.length) write('Missing engines: ' + correlation.missing_engines.join(', '));
      if (correlation.failed_engines?.length) write('Failed engines: ' + correlation.failed_engines.join(', '));
    }
    section('Interpretation and limitations');
    write('This report summarizes the observations returned by the configured examination engines. A non-detection does not prove that an indicator is absent. Missing or unavailable evidence is not a negative finding. Engine scores are not probabilities unless the source engine explicitly documents calibration and score semantics.');
    write('This document is an analytical aid. Interpret findings alongside original evidence and the technical JSON record.');
    const total = pdf.getNumberOfPages();
    for (let i = 1; i <= total; i++) { pdf.setPage(i); pdf.setFontSize(8); pdf.setTextColor(115,128,140); pdf.text('IMFORENSIC  |  CONTROLLED EXAMINATION OUTPUT', left, 287); pdf.text('Page ' + i + ' of ' + total, 192, 287, { align: 'right' }); }
    pdf.save('imforensic-' + safeName(analysis.analysis_id) + '-examination-report.pdf');
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
          {previewUrl && <div className="intake-preview"><img src={previewUrl} alt="Selected evidence preview"/><div><b>Selected evidence preview</b><small>{file?.name} · {formatBytes(file?.size || 0)}</small></div></div>}
          <div className="intake-actions"><div><b>Examination scope</b><small>All six configured forensic engines will be requested.</small></div><button className="button-primary" disabled={!file || busy || health !== 'online'}>{busy ? 'Submitting evidence…' : 'Submit for examination  →'}</button></div>
          {error && <p className="error-message" role="alert">{error}</p>}
        </form>
      </section>

      {analysis && <>
        <section className="section-block" id="examination">
          <div className="section-heading"><div><span className="section-index">02</span><div><h2>Examination record</h2><p>Submission identity, integrity reference and processing state.</p></div></div><div className="report-actions"><button className="button-secondary" onClick={downloadTechnicalJson}>↓ Technical JSON</button><button className="button-primary" onClick={downloadPdf}>↓ A4 examination report</button></div></div>
          <div className="record-card">
            <div className="record-top"><div><span className="field-label">EXAMINATION IDENTIFIER</span><code>{analysis.analysis_id}</code></div><Status value={analysis.status} /></div>
            <div className="record-grid"><div><span className="field-label">Evidence file</span><b>{resultFilename}</b></div><div><span className="field-label">Submitted</span><b>{safeDate(analysis.created_at)}</b></div><div><span className="field-label">File size</span><b>{formatBytes(analysis.size_bytes || file?.size || 0)}</b></div><div><span className="field-label">Media type</span><b>{analysis.content_type || file?.type || '—'}</b></div></div>
            <div className="hash-row"><span className="field-label">SHA-256 INTEGRITY REFERENCE</span><code>{analysis.sha256 || 'Not returned by gateway'}</code></div>
            <div className="timing-row"><div><span className="field-label">ELAPSED TIME</span><b>{elapsedLabel}</b></div><div><span className="field-label">ESTIMATED PROCESSING WINDOW</span><b>Indicative processing target: 2 minutes</b></div><div><span className="field-label">LAST STATUS UPDATE</span><b>{lastUpdated ? lastUpdated.toLocaleTimeString() : 'Awaiting update'}</b></div></div>
            <div className="progress-head"><b>Engine response collection</b><span>{received} / {expected.length} received</span></div><div className="progress-track"><div style={{width: progress + '%'}} /></div>
            <small className="muted">This is a fixed initial waiting target, not a measured prediction or guaranteed completion time.</small>
            {timedOut && !isComplete && <p className="timeout-notice" role="status">Analysis is taking longer than expected. Please wait a while. No further action has been taken. Automatic status checks have stopped.</p>}
            {!isComplete && !timedOut && <p className="muted small">Status is refreshed automatically while the estimated waiting window remains active.</p>}
          </div>
          <div className="engine-grid">{expected.map(name => {
            const meta = ENGINES.find(x => x[0] === name) || [name, humanize(name), 'Configured analysis engine'];
            const item = results[name]; const status = item?.status || 'waiting';
            const aiAssessment = name === 'ai-content-detection' ? getAiAssessment(item) : null;
            return <article className="engine-card" key={name}><div className="engine-card-head"><span className="engine-code">{String(expected.indexOf(name) + 1).padStart(2, '0')}</span><Status value={status} /></div><h3>{meta[1]}</h3><p>{meta[2]}</p><p className="engine-summary">{statusMessage(item)}</p><Findings item={item}/>{aiAssessment && <div className="ai-assessment"><span className="field-label">AI-GENERATION ASSESSMENT</span><strong>{aiAssessment.label}</strong><p>{aiAssessment.detail}</p></div>}{item && <details className="raw-details"><summary>Inspect technical response</summary><pre>{pretty(rawFor(item))}</pre></details>}</article>;
          })}</div>
        </section>

        <section className="section-block" id="correlation">
          <div className="section-heading"><div><span className="section-index">03</span><div><h2>Evidence correlation</h2><p>Cross-engine observations and execution completeness.</p></div></div>{correlation && <Status value={correlation.status} />}</div>
          <div className="correlation-card">
            {!correlation ? <div className="pending-correlation"><b>{TERMINAL.includes(String(analysis.status || '').toLowerCase()) ? 'Correlation data not returned by the API' : 'Correlation report pending'}</b><p className="muted">{TERMINAL.includes(String(analysis.status || '').toLowerCase()) ? 'The examination has reached a terminal status, but this response contains no correlation payload. Six engine responses do not by themselves confirm that cross-engine correlation was performed.' : 'The consolidated report has not yet been returned by the API. It remains pending while the examination is processing.'}</p></div> : <>
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
