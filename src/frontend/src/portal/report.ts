/** End-of-day report exports: CSV for spreadsheets, a print-ready page for PDF. */
import { clock, dayStats, duration, responseSeconds, type FallEvent, type Resident } from './data';

function save(name: string, type: string, body: string) {
  const url = URL.createObjectURL(new Blob([body], { type }));
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const stamp = () => new Date().toISOString().slice(0, 10);
const esc = (s: string) => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]!));
const cell = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`;

export function downloadCsv(falls: FallEvent[], residents: Resident[], scope = 'facility') {
  const name = (id: string) => residents.find(r => r.id === id)?.name ?? id;
  const rows = [['Time', 'Resident', 'Room', 'Wing', 'Confidence', 'Status', 'Response time', 'Attended by', 'Note']];
  for (const f of [...falls].sort((a, b) => a.at - b.at)) {
    const rs = responseSeconds(f);
    rows.push([new Date(f.at).toLocaleString(), name(f.residentId), f.room, f.wing, `${Math.round(f.confidence * 100)}%`,
      f.acknowledgedAt ? 'Attended' : 'Open', rs === null ? '' : duration(rs), f.acknowledgedBy ?? '', f.note ?? '']);
  }
  const s = dayStats(falls);
  rows.push([], ['Summary'], ['Total falls', String(s.total)], ['Open', String(s.open)],
    ['Average response', s.avgResponse === null ? '-' : duration(s.avgResponse)]);
  for (const [room, n] of [...s.byRoom].sort((a, b) => b[1] - a[1])) rows.push([`Room ${room}`, String(n)]);
  save(`icare-${scope}-report-${stamp()}.csv`, 'text/csv', rows.map(r => r.map(cell).join(',')).join('\n'));
}

export function printReport(falls: FallEvent[], residents: Resident[], title: string) {
  const s = dayStats(falls);
  const name = (id: string) => residents.find(r => r.id === id)?.name ?? id;
  const rooms = [...s.byRoom].sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...rooms.map(r => r[1]));
  const hourMax = Math.max(1, ...s.byHour);
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>${esc(title)}</title>
<style>
body{font:14px/1.5 Inter,system-ui,sans-serif;color:#17181c;margin:40px;}
h1{font-size:22px;margin:0}.sub{color:#6b6f78;margin:4px 0 24px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
.k{border:1px solid #e6e7ea;border-radius:12px;padding:14px}.k span{color:#6b6f78;font-size:12px}.k b{display:block;font-size:24px}
h2{font-size:15px;margin:24px 0 10px}table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid #eee;font-size:13px}th{color:#6b6f78;font-weight:500}
.bar{height:10px;background:#f26b1d;border-radius:5px}.row{display:grid;grid-template-columns:80px 1fr 30px;gap:10px;align-items:center;margin:6px 0}
.hours{display:flex;gap:3px;align-items:flex-end;height:80px;border-bottom:1px solid #ddd}.hours div{flex:1;background:#f26b1d;border-radius:3px 3px 0 0}
.hl{display:flex;justify-content:space-between;color:#6b6f78;font-size:11px}
.open{color:#c2361b;font-weight:600}@media print{body{margin:16px}}
</style></head><body>
<h1>${esc(title)}</h1><p class="sub">Generated ${new Date().toLocaleString()} · ICare fall monitoring</p>
<div class="kpis"><div class="k"><span>Total falls</span><b>${s.total}</b></div>
<div class="k"><span>Open alerts</span><b>${s.open}</b></div>
<div class="k"><span>Rooms with falls</span><b>${s.byRoom.size}</b></div>
<div class="k"><span>Avg response</span><b>${s.avgResponse === null ? '–' : duration(s.avgResponse)}</b></div></div>
<h2>Falls by room</h2>${rooms.map(([r, n]) => `<div class="row"><span>Room ${esc(r)}</span><div class="bar" style="width:${(n / max) * 100}%"></div><b>${n}</b></div>`).join('') || '<p>No falls recorded.</p>'}
<h2>Falls by hour</h2><div class="hours">${s.byHour.map(n => `<div style="height:${(n / hourMax) * 100}%" title="${n}"></div>`).join('')}</div>
<div class="hl"><span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>23:00</span></div>
<h2>Incident log</h2><table><thead><tr><th>Time</th><th>Resident</th><th>Room</th><th>Confidence</th><th>Response</th><th>Attended by</th></tr></thead><tbody>
${[...falls].sort((a, b) => a.at - b.at).map(f => { const rs = responseSeconds(f); return `<tr><td>${clock(f.at)}</td><td>${esc(name(f.residentId))}</td><td>${esc(f.room)}</td><td>${Math.round(f.confidence * 100)}%</td><td>${rs === null ? '<span class="open">Open</span>' : duration(rs)}</td><td>${esc(f.acknowledgedBy ?? '')}</td></tr>`; }).join('')}
</tbody></table>
<script>window.onload=()=>setTimeout(()=>window.print(),300)</script></body></html>`;
  const w = window.open('', '_blank');
  if (w) { w.document.write(html); w.document.close(); }
  else save(`icare-report-${stamp()}.html`, 'text/html', html);
}
