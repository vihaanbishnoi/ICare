/** Face enrolment: residents the cameras can name instead of "Person N". */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { deleteResident, enrollResident } from '../api/client';
import { useResidents } from '../hooks/useResidents';
import type { Resident } from '../types';
import { Icon } from './ui';

const MAX_PHOTOS = 5;
const message = (e: unknown, fallback: string) => e instanceof Error ? e.message : fallback;

export function ResidentsView() {
  const { list, unavailable, refresh } = useResidents();
  const [name, setName] = useState('');
  const [room, setRoom] = useState('');
  const [photos, setPhotos] = useState<{ file: File; url: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState('');
  const [removing, setRemoving] = useState<string | null>(null);
  const urls = useRef<string[]>([]);
  useEffect(() => () => { for (const url of urls.current) URL.revokeObjectURL(url); }, [urls]);

  function setPicked(next: { file: File; url: string }[]) {
    for (const url of urls.current) if (!next.some(p => p.url === url)) URL.revokeObjectURL(url);
    urls.current = next.map(p => p.url);
    setPhotos(next);
  }

  function pick(files: File[]) {
    const space = Math.max(MAX_PHOTOS - photos.length, 0);
    setError(files.length > space ? `Up to ${MAX_PHOTOS} photos; only the first ${space} were added.` : '');
    setDone('');
    setPicked([...photos, ...files.slice(0, space).map(file => ({ file, url: URL.createObjectURL(file) }))]);
  }

  async function enrol(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(''); setDone('');
    try {
      const resident = await enrollResident(name, room, photos.map(p => p.file));
      setDone(`${resident.name} enrolled from ${resident.photo_count} photo${resident.photo_count === 1 ? '' : 's'}. Applies to the next camera session or video analysis.`);
      setName(''); setRoom(''); setPicked([]);
      refresh();
    } catch (e) {
      setError(message(e, 'Enrolment failed.'));
    } finally { setBusy(false); }
  }

  async function remove(resident: Resident) {
    if (!window.confirm(`Remove ${resident.name}? Their face measurements are deleted and they will show as "Person N" again.`)) return;
    setRemoving(resident.resident_id); setError(''); setDone('');
    try { await deleteResident(resident.resident_id); refresh(); }
    catch (e) { setError(message(e, 'Could not remove this resident.')); }
    finally { setRemoving(null); }
  }

  const modelsMissing = list?.face_models_ready === false;
  const residents = list?.residents ?? [];

  return <div className="p-stack">
    <div className="p-pagehead">
      <div><h2>Residents</h2>
        <p className="p-muted">Enrol a resident so the camera shows their name instead of "Person N".</p>
        <p className="p-muted p-small">New enrolments apply to the next camera session or video analysis.</p></div>
    </div>
    {unavailable && <p className="p-inline-alert" role="alert"><Icon name="alert" size={16} />The detector API is not running, so residents cannot be loaded or enrolled.</p>}
    {modelsMissing && <p className="p-inline-alert" role="alert"><Icon name="alert" size={16} />Face recognition models are not installed on this computer, so residents cannot be enrolled or recognised yet.</p>}

    <div className="p-grid p-grid--2">
      <form className="p-card" onSubmit={event => void enrol(event)}>
        <header className="p-card__head"><span><Icon name="heart" size={16} />Enrol a resident</span></header>
        <label className="p-field"><span>Name</span>
          <input required maxLength={80} value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Margaret Hill" /></label>
        <label className="p-field"><span>Room (optional)</span>
          <input maxLength={20} value={room} onChange={e => setRoom(e.target.value)} placeholder="e.g. 12" /></label>
        <div className="p-field"><span>Photos ({photos.length}/{MAX_PHOTOS})</span>
          <p className="p-muted p-small">1 to {MAX_PHOTOS} clear photos with only this person's face, ideally from slightly different angles.</p>
          <div className="p-res-photos">
            {photos.map((p, i) => <figure key={p.url} className="p-res-photo">
              <img src={p.url} alt={`Photo ${i + 1}: ${p.file.name}`} />
              <button type="button" className="p-iconbtn" aria-label={`Remove photo ${i + 1}`} onClick={() => setPicked(photos.filter(x => x !== p))}><Icon name="close" size={12} /></button>
            </figure>)}
            {photos.length < MAX_PHOTOS && <label className="p-btn p-btn--sm p-res-pick"><Icon name="camera" size={14} />{photos.length ? 'Add photos' : 'Choose photos'}
              <input type="file" accept="image/*" multiple className="sr-only"
                onChange={e => { pick(Array.from(e.target.files ?? [])); e.target.value = ''; }} /></label>}
          </div>
        </div>
        {error && <p className="p-inline-alert" role="alert">{error}</p>}
        {done && <p className="p-res-done" role="status">{done}</p>}
        <div><button type="submit" className="p-btn p-btn--primary" disabled={busy || modelsMissing || !name.trim() || !photos.length}>
          <Icon name="check" size={16} />{busy ? 'Enrolling…' : 'Enrol'}</button></div>
      </form>

      <section className="p-card">
        <header className="p-card__head"><span>Privacy</span></header>
        <p>Enrol only people who have agreed. Photos are not stored; only face measurements are kept on this computer. A name is shown only after two confident matches; otherwise the person stays 'Person N'.</p>
        <p className="p-muted p-small">Removing a resident deletes their face measurements straight away.</p>
      </section>
    </div>

    <section className="p-card p-card--flush">
      <header className="p-card__head p-pad"><span>Enrolled residents</span><span className="p-muted p-small">{residents.length}</span></header>
      <table className="p-table">
        <thead><tr><th>Name</th><th>Room</th><th>Photos</th><th>Enrolled</th><th><span className="sr-only">Actions</span></th></tr></thead>
        <tbody>{residents.map(r => <tr key={r.resident_id}>
          <td><strong>{r.name}</strong></td>
          <td>{r.room || <span className="p-muted">—</span>}</td>
          <td className="num">{r.photo_count}</td>
          <td className="num">{new Date(r.created_at_utc).toLocaleString()}</td>
          <td className="p-table__act"><button type="button" className="p-btn p-btn--sm" disabled={removing === r.resident_id}
            onClick={() => void remove(r)}><Icon name="close" size={14} />{removing === r.resident_id ? 'Removing…' : 'Delete'}</button></td>
        </tr>)}
        {!residents.length && <tr><td colSpan={5} className="p-empty">{list ? 'No residents enrolled yet.' : unavailable ? 'Residents could not be loaded.' : 'Loading…'}</td></tr>}</tbody>
      </table>
    </section>
  </div>;
}
