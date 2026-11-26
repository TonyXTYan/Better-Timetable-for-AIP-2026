// ---------- export helpers ----------
function icsEscape(s){ return (s||'').replace(/\\/g,'\\\\').replace(/;/g,'\\;').replace(/,/g,'\\,').replace(/\r\n?|\n/g,'\\n'); }
function icsFold(line){
  const encoder = new TextEncoder();
  if (encoder.encode(line).length <= 75) return line;
  const out = [];
  let chunk = '', bytes = 0;
  for (const char of line){
    const size = encoder.encode(char).length;
    if (bytes + size > 75){
      out.push(chunk);
      chunk = ' ';
      bytes = 1;
    }
    chunk += char;
    bytes += size;
  }
  out.push(chunk);
  return out.join('\r\n');
}
function toUTCStamp(date, time){
  // Congress runs on Australian Eastern Daylight Time (UTC+11) in December 2026
  const iso = date.includes('-') ? date : (date.slice(0,4) + '-' + date.slice(4,6) + '-' + date.slice(6));
  const dt = new Date(iso + 'T' + time + ':00+11:00');
  return dt.toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
}
function exportClashes(items){
  markClashes(items);
  if (state.hideClashes) clearClashes(items);
}
function buildIcs(){
  const items = agendaItems();
  exportClashes(items);
  // A saved session is one event; the talks starred in it lead its description.
  const speakers = t => t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ');
  const stamp = new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
  const lines = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//AIP Congress 2026 Program Explorer//EN','CALSCALE:GREGORIAN','X-WR-CALNAME:AIP Congress 2026 - My agenda'];
  items.forEach(it => {
    let desc = it.kind === 'talk' ? (it.t.d || '') : (it.s.desc || '');
    const chars = Array.from(desc);
    if (chars.length > 900) desc = chars.slice(0, 900).join('') + '…';
    const who = it.kind === 'talk' ? speakers(it.t) : (it.s.conv || []).join('; ');
    // a session with no Indico page (breaks, the Welcome Reception) carries the bare site
    // root: leave it out; a Congress event gives its note and official pages instead
    const url = indicoUrl(it.kind === 'talk' ? it.t.u : it.s.url);
    const official = it.kind === 'talk' ? '' : [it.s.info || '', ...(it.s.links || []).map(l => l.l + ': ' + l.u)].filter(Boolean).join('\n');
    const parent = it.kind === 'talk' ? 'Part of: ' + it.s.title : '';
    const word = it.s.cat === 'poster' ? 'posters' : 'talks';
    const starred = it.inner && it.inner.length ? `Saved ${word} in this session:\n` +
      it.inner.map(t => `★ ${t.s}–${t.e} ${t.t}${t.sp.length ? ' — ' + speakers(t) : ''}`).join('\n') : '';
    const clashLine = it.clashes.length ? 'Overlaps: ' + it.clashes.map(x => `${itemTitle(x)} (${x.start}–${x.end})`).join('; ') : '';
    const softLine = it.soft.length ? 'Possible clash, sessions overlap: ' + it.soft.map(x => `${itemTitle(x)} (${x.start}–${x.end})`).join('; ') : '';
    const body = [starred, who ? (it.kind === 'talk' ? 'Speakers: ' : 'Convened by: ') + who : '', clashLine, softLine, desc, official, parent, url].filter(Boolean).join('\n\n');
    lines.push('BEGIN:VEVENT');
    lines.push(icsFold('UID:' + it.s.id + (it.t ? '-' + it.t.id : '') + '@aip2026-program'));
    lines.push('DTSTAMP:' + stamp);
    lines.push('DTSTART:' + toUTCStamp(it.d.date, it.start));
    lines.push('DTEND:' + toUTCStamp(it.d.date, it.end));
    lines.push(icsFold('SUMMARY:' + icsEscape(itemTitle(it))));
    lines.push(icsFold('DESCRIPTION:' + icsEscape(body)));
    lines.push(icsFold('LOCATION:' + icsEscape('Belinda Hutchinson Building, The University of Sydney' + (it.s.room && it.s.room !== 'Belinda Hutchinson Building' ? ' — ' + it.s.room : ''))));
    if (url) lines.push(icsFold('URL:' + url));
    lines.push('END:VEVENT');
  });
  lines.push('END:VCALENDAR');
  return lines.join('\r\n') + '\r\n';
}
function agendaText(){
  const items = agendaItems();
  exportClashes(items);
  const cx = clashTally(items), cxs = clashTally(items, softOf);
  let out = 'AIP Congress 2026 — My agenda\n=============================\nAll times AEDT (Australia/Sydney)\n';
  const speakers = t => t.sp.map(p => p.n + (p.a ? ' (' + p.a + ')' : '')).join('; ');
  out += `${agendaCountText(items, false)}, about ${plannedHours(items).toFixed(1)} h` +
         (cx.groups ? `; ${clashWords(cx.groups, cx.items)}` : '; no clashes') + (cxs.groups ? `; ${softWords(cxs.groups, cxs.items)}, sessions overlap` : '') + '\n';
  DATA.days.forEach((d, di) => {
    const dayItems = items.filter(x => x.di === di);
    if (!dayItems.length) return;
    out += `\n${d.label} 2026\n${'-'.repeat(d.label.length + 5)}\n`;
    dayItems.forEach(it => {
      out += `  ${it.start}–${it.end}  ${itemTitle(it)}  [${kindLabel(it)}]\n`;
      const who = it.kind === 'talk' ? (speakers(it.t) || 'Speaker TBA') : (it.s.room || '');
      if (who) out += `             ${who}\n`;
      if (it.kind === 'talk') out += `             part of ${it.s.title}\n`;
      if (it.kind === 'talk' && it.s.room) out += `             ${it.s.room}\n`;
      (it.inner || []).forEach(t => out += `             ★ ${t.s}–${t.e}  ${t.t}${t.sp.length ? ' — ' + speakers(t) : ''}\n`);
      it.clashes.forEach(x => out += `             Clashes with “${itemTitle(x)}” (${x.start}–${x.end})\n`);
      it.soft.forEach(x => out += `             Possible clash with “${itemTitle(x)}” (${x.start}–${x.end}): sessions overlap\n`);
    });
  });
  out += '\nSource: official AIP Congress 2026 Indico timetable — https://indico.global/event/16926/timetable/\n';
  return out;
}
// Every Export action says what it did in the line under the bar, in place of what the
// last one said (and closes the last one's text box).
function exportSay(msg){
  document.getElementById('exportStatus').textContent = msg;
  document.getElementById('copyNote').hidden = true;
  document.getElementById('icsNote').hidden = true;
}
const agendaSize = () => countWord(agendaItems().length, 'item');
async function copyToClipboard(txt){
  const note = document.getElementById('copyNote');
  try {
    await navigator.clipboard.writeText(txt);
    exportSay(`Copied your agenda (${agendaSize()}) as text.`);
    toast('Agenda copied as text');
  } catch {
    const box = document.getElementById('copyBox');
    exportSay('Copying is blocked here: select the text below and copy it.');
    note.hidden = false;
    box.value = txt;
    box.focus();
    box.select();
  }
}
function downloadIcs(){
  const txt = buildIcs();
  const n = (txt.match(/BEGIN:VEVENT/g) || []).length;
  let ok = true;
  try {
    const blob = new Blob([txt], { type: 'text/calendar' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'aip-congress-2026-my-agenda.ics';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  } catch(e){ ok = false; }
  exportSay(ok ? `Saved aip-congress-2026-my-agenda.ics with ${n} event${n===1?'':'s'}. Open it to add them to your calendar.`
    : 'The download didn’t start: copy the calendar text below.');
  const note = document.getElementById('icsNote');
  note.hidden = false;
  note.open = !ok;
  document.getElementById('icsBox').value = txt;
}

function programCalendarItems(){
  const items = [], talks = state.programTalks && state.day !== 'all';   // (All week: sessions)
  DATA.days.forEach((d,di) => {
    for (const s of d.slots.filter(slotMatches)){
      if (talks && s.talks.length && s.cat !== 'poster'){
        for (const t of s.talks.filter(t => talkMatches(t,s))){
          items.push({di,d,s,t,kind:'talk',start:t.s,end:t.e,clashes:[]});
        }
      } else {
        items.push({di,d,s,t:null,kind:'session',start:s.start,end:s.end,clashes:[],
                    children:s.talks.filter(t => state.starred.has(t.id))});
      }
    }
  });
  return items.sort((a,b) => a.di-b.di || a.start.localeCompare(b.start));
}

