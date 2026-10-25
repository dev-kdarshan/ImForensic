import { useState } from 'react';

export default function App() {
  const [file, setFile] = useState(null);

  return (
    <main className="shell">
      <p className="eyebrow">IMAGE FORENSICS WORKSPACE</p>
      <h1>ImForensic</h1>
      <p className="intro">
        Examine image provenance, AI-generation indicators, and possible manipulation.
        Findings are evidence indicators, not proof by themselves.
      </p>
      <section className="upload">
        <h2>Start an analysis</h2>
        <label htmlFor="image">Choose an image</label>
        <input
          id="image"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        {file && <p>Selected: {file.name} ({Math.ceil(file.size / 1024)} KB)</p>}
        <button disabled={!file} onClick={() => alert('Upload API is not implemented yet.')}>
          Analyze image
        </button>
        <p className="note">Starter UI only. Upload processing is not connected yet.</p>
      </section>
      <p className="footer">Privacy-first design · Temporary processing planned · No login</p>
    </main>
  );
}
