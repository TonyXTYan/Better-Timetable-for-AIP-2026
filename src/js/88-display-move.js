// ---------- display options ----------
// Text size, font (System or Archivo), pop-up width, theme, colour (Quiet or Vivid), high-contrast text and reduced motion. Only choices that differ from
// the defaults are stored (localStorage 'aip2026-display'); the inline script in <head>
// applies them before the first paint, and applyDisplay() keeps <html> and theme-color in step.
const DISPLAY_KEY = 'aip2026-display';
const displayDialog = document.getElementById('displayDialog');
const displayBtn = document.getElementById('displayBtn');
// (the button that opened the dialog has the focus back when it closes: the toolbar's or the
// footer's; opened from history, the toolbar's)
let displayOpener = null;
const motionQuery = matchMedia('(prefers-reduced-motion: reduce)');
const darkQuery = matchMedia('(prefers-color-scheme: dark)');
const DISPLAY_VALUES = { text:['sm','lg','xl'], font:['archivo'], theme:['light','dark'], contrast:['high'], colour:['vivid'], motion:['reduce','full'], speed:['fast','xslow'], popw:['narrow','full'] };
function readDisplay(){
  let d = {};
  try { d = JSON.parse(localStorage.getItem(DISPLAY_KEY) || '{}') || {}; } catch (e) { d = {}; }
  const clean = {};
  for (const [k, ok] of Object.entries(DISPLAY_VALUES)) if (ok.includes(d[k])) clean[k] = d[k];
  return clean;
}
let display = readDisplay();
function saveDisplay(){
  try {
    if (Object.keys(display).length) localStorage.setItem(DISPLAY_KEY, JSON.stringify(display));
    else localStorage.removeItem(DISPLAY_KEY);
  } catch (e) {}
}
function motionReduced(){ return display.motion ? display.motion === 'reduce' : motionQuery.matches; }
function syncDisplayForm(){
  displayDialog.querySelectorAll('input[name="dsText"]').forEach(r => r.checked = r.value === (display.text || ''));
  displayDialog.querySelectorAll('input[name="dsFont"]').forEach(r => r.checked = r.value === (display.font || ''));
  displayDialog.querySelectorAll('input[name="dsTheme"]').forEach(r => r.checked = r.value === (display.theme || ''));
  displayDialog.querySelectorAll('input[name="dsColour"]').forEach(r => r.checked = r.value === (display.colour || ''));
  displayDialog.querySelectorAll('input[name="dsSpeed"]').forEach(r => r.checked = r.value === (display.speed || ''));
  displayDialog.querySelectorAll('input[name="dsPopw"]').forEach(r => r.checked = r.value === (display.popw || ''));
  // (phones: the pop-ups are sheets across the whole screen, whatever is chosen here)
  document.getElementById('dsPopwGroup').disabled = PHONE_MQ.matches;
  document.getElementById('dsPopwNote').textContent = PHONE_MQ.matches
    ? 'On a screen this narrow, pop-ups always fill the width.' : 'For the session and talk pop-ups.';
  // (no speed to choose while nothing moves)
  document.getElementById('dsSpeedGroup').disabled = motionReduced();
  document.getElementById('dsSpeedNote').hidden = !motionReduced();
  document.getElementById('dsSystemNote').textContent = 'Now ' + (darkQuery.matches ? 'dark' : 'light');
  document.getElementById('dsContrast').setAttribute('aria-pressed', display.contrast === 'high');
  document.getElementById('dsMotion').setAttribute('aria-pressed', motionReduced());
  displayDialog.querySelectorAll('.seg').forEach(g => segPlace(g));
  document.getElementById('dsMotionNote').textContent = display.motion
    ? 'Set here (your device setting is ' + (motionQuery.matches ? 'on' : 'off') + ')'
    : 'Follows your device setting (' + (motionQuery.matches ? 'on' : 'off') + ')';
}
// (a new rem: the calendars fit again at once, as a reload would)
function refitCalendars(){
  const main = document.getElementById('agenda');
  if (main.querySelector('.hz-day')) hzDraw(main);
  weekFit();
  // (the list's blocks and rows remember their heights at the old size: forget them,
  // so the page is as tall as a reload would make it)
  document.querySelectorAll('#agenda .block, #builderList .ag-row').forEach(b => { b._drawn = false; b.style.removeProperty('--cih'); });
  blockHeightsSoon();
}
// Archivo's faces are decoded only once that font is chosen (the inline script in <head>
// starts them when it was chosen before); this resolves when they are ready.
function archivoReady(){
  const F = document.fonts;
  if (!F || !F.load) return Promise.resolve();
  return Promise.all(['420 16px Archivo', '700 16px Archivo', 'italic 480 16px Archivo'].map(f => F.load(f))).catch(() => {});
}
function setDisplay(key, value){
  if (value) display[key] = value; else delete display[key];
  const go = () => {
    window.applyDisplay(display);
    saveDisplay();
    syncDisplayForm();
    fitPlaceholder();
    // (a new rem or a new face: the calendars measure their text again)
    if (key === 'text' || key === 'font'){ refitCalendars(); platesRefit(); }
  };
  // a new look fades in; the motion settings themselves apply at once, as does the pop-up
  // width (nothing on the page changes with it). Archivo loads
  // first, so the fade lands on it (never on a stand-in face) and the calendars measure it.
  if (key === 'motion' || key === 'speed' || key === 'popw') go();
  else if (key === 'font' && value) archivoReady().then(() => { if (display.font === value) displayFade(go); });
  else displayFade(go, key === 'text');
}
// A new theme, contrast or text size cross-fades the whole page (this dialog too) from
// the old look to the new one, so nothing flashes and a new text size never jumps. Not
// while motion is reduced, and never on load (the inline script in <head> applies the
// stored settings before the first paint).
function displayFade(fn, seq){
  settleTransition();
  const root = document.documentElement;
  if (motionReduced() || !document.startViewTransition){ fn(); return; }
  let ran = false;
  const run = () => { if (!ran){ ran = true; fn(); } };
  root.dataset.viewTx = 'disp';
  // (no colour transition of the page's own runs under the fade: an attribute of its own,
  // as one rule for every element would restyle the whole page for every other change too)
  root.dataset.viewTxDisp = '';
  // (a new text size: the old look fades out before the new one fades in)
  if (seq) root.dataset.viewTxSeq = ''; else delete root.dataset.viewTxSeq;
  let vt;
  try { vt = document.startViewTransition(run); }
  catch (e){ delete root.dataset.viewTx; delete root.dataset.viewTxSeq; delete root.dataset.viewTxDisp; run(); return; }
  const tx = viewTx = { vt, run };
  vt.ready.catch(() => {});   // (a skipped fade: a newer change took over)
  vt.updateCallbackDone.catch(e => console.error(e));
  vt.finished.catch(() => {}).then(() => {
    if (viewTx === tx) viewTx = null;
    if (!viewTx){ delete root.dataset.viewTx; delete root.dataset.viewTxSeq; }
    if (!viewTx || root.dataset.viewTx !== 'disp') delete root.dataset.viewTxDisp;
  });
}
// A new speed: the preview card slides in at it, to show how it feels.
function speedDemo(){
  const pv = displayDialog.querySelector('.dd-preview');
  if (motionReduced() || !pv.animate) return;
  pv.animate([{ opacity: 0, transform: 'translateX(-16px)' }, { opacity: 1, transform: 'none' }], { duration: MX_MS * motionK(), easing: MX_EASE });
}
function openDisplay(fromHistory, opener){
  displayOpener = opener || null;
  syncDisplayForm();
  hideToast();
  displayDialog.showModal();
  // (from the top each time, as the details)
  displayDialog.scrollTop = 0;
  if (!fromHistory) pnlHistoryOpen('display');
}
for (const b of [displayBtn, document.getElementById('displayBtnFoot')]) b.addEventListener('click', () => openDisplay(false, b));
displayDialog.addEventListener('change', e => {
  if (e.target.name === 'dsText') setDisplay('text', e.target.value);
  else if (e.target.name === 'dsFont') setDisplay('font', e.target.value);
  else if (e.target.name === 'dsTheme') setDisplay('theme', e.target.value);
  else if (e.target.name === 'dsColour') setDisplay('colour', e.target.value);
  else if (e.target.name === 'dsSpeed'){ setDisplay('speed', e.target.value); speedDemo(); }
  else if (e.target.name === 'dsPopw') setDisplay('popw', e.target.value);
});
lightDismiss(displayDialog, () => displayDialog.close());
// ---------- GitHub issues (the footer's About) ----------
// "Request a data update" and "Report a problem" open a new issue on GitHub, filled in. The
// build writes each link whole (its title, its template and the data's date), so it works
// without the script; just before it is followed (pressed, focused, clicked or opened from
// its menu) the page adds what the reader is looking at. Nothing is sent from here: GitHub
// shows the issue to edit before it is submitted.
const ISSUE_SCOPE = { program: 'Full program', agenda: 'My agenda', participants: 'Participants' };
function issueView(){
  const day = state.day === 'all' ? 'All week' : DATA.days[state.day]?.label || String(state.day);
  let view = ISSUE_SCOPE[state.scope] || state.scope;
  if (state.scope !== 'participants'){
    view += ', ' + state.layout;
    if (state.layout === 'calendar' && state.scope === 'program' && state.day !== 'all')
      view += ` (${state.programTalks ? 'talks' : 'sessions'}, ${state.orient === 'v' ? 'vertical' : 'horizontal'})`;
  }
  const q = state.scope === 'participants' ? state.pq : state.scope === 'agenda' ? state.aq : state.q;
  const cats = state.scope === 'agenda' ? state.acats : state.cats, all = Object.keys(DATA.cats).length;
  // (the search as code, so the issue shows it as typed; cut by characters, so an emoji
  // at the cut never leaves half of itself, which the link could not encode)
  const qs = q && '`' + Array.from(q.replace(/`/g, "'")).slice(0, 80).join('') + '`';
  // (Participants has no day)
  return (state.scope === 'participants' ? view : `${day}; ${view}`) + (qs ? '; search ' + qs : '') + (cats.size < all ? `; streams: ${cats.size} of ${all}` : '');
}
function issueDisplay(){
  const r = document.documentElement, at = (n, d) => r.getAttribute('data-' + n) || d;
  const mq = q => matchMedia(q).matches;
  return [
    'theme ' + at('theme', `system (${mq('(prefers-color-scheme: dark)') ? 'dark' : 'light'})`),
    'text ' + at('text', 'default'), 'font ' + at('font', 'system'), 'colour ' + at('colour', 'quiet'),
    'contrast ' + at('contrast', mq('(prefers-contrast: more)') ? 'system (more)' : 'standard'),
    'motion ' + at('motion', mq('(prefers-reduced-motion: reduce)') ? 'system (reduced)' : 'system'),
    'speed ' + at('speed', 'default'), 'pop-up width ' + ({ narrow: 'narrower', full: 'full width' }[at('popw', '')] || 'wide (default)'),
  ].join(', ') + (mq('(forced-colors: active)') ? ', forced colours' : '');
}
function issueContext(kind){
  // (a shared agenda's address can be long: the link keeps well within what GitHub takes)
  const href = location.href.length > 1500 ? location.href.slice(0, 1500) + '… (cut short)' : location.href;
  const lines = ['- Page: ' + href];
  if (kind === 'data') lines.push('- Day and view: ' + issueView());
  else lines.push(`- Viewport: ${innerWidth} × ${innerHeight} (pixel ratio ${+devicePixelRatio.toFixed(2)})`,
    '- Display: ' + issueDisplay(), '- Browser: ' + navigator.userAgent.slice(0, 300));
  return lines.join('\n');
}
for (const a of document.querySelectorAll('a[data-issue]')){
  const base = new URL(a.getAttribute('href')), title = base.searchParams.get('title') || '', body = base.searchParams.get('body') || '';
  const refresh = () => {
    try {
      a.href = base.origin + base.pathname + '?title=' + encodeURIComponent(title)
        + '&body=' + encodeURIComponent(body.replace(/\n*$/, '\n') + issueContext(a.dataset.issue) + '\n');
    } catch (e) {}
  };
  for (const ev of ['pointerdown', 'focus', 'click', 'contextmenu']) a.addEventListener(ev, refresh);
}

displayDialog.addEventListener('click', e => {
  if (e.target === displayDialog) return;
  if (e.target.closest('#dsContrast')) setDisplay('contrast', display.contrast === 'high' ? '' : 'high');
  else if (e.target.closest('#dsMotion')){
    // Store an override only when it differs from the device setting.
    const want = !motionReduced();
    setDisplay('motion', want === motionQuery.matches ? '' : (want ? 'reduce' : 'full'));
  } else if (e.target.closest('#dsReset')){
    // (motion and speed go back too, so the fade is decided by the settings being left)
    const hadText = !!display.text, hadFont = !!display.font;
    displayFade(() => {
      display = {};
      window.applyDisplay(display);
      saveDisplay();
      syncDisplayForm();
      fitPlaceholder();
      if (hadText || hadFont) refitCalendars();
    }, hadText);
    toast('Display options reset');
  }
});
displayDialog.addEventListener('close', () => {
  pnlHistoryClose();
  const b = displayOpener && displayOpener.isConnected && displayOpener.getClientRects().length ? displayOpener : displayBtn;
  displayOpener = null;
  b.focus();
});
for (const q of [motionQuery, darkQuery, PHONE_MQ]){
  const sync = () => { if (displayDialog.open) syncDisplayForm(); };
  if (q.addEventListener) q.addEventListener('change', sync); else if (q.addListener) q.addListener(sync);
}
window.addEventListener('storage', e => {
  if (e.key !== DISPLAY_KEY && e.key !== null) return;
  const was = display;
  display = readDisplay();
  window.applyDisplay(display);
  syncDisplayForm();
  // (another tab chose a new font: measure the calendars again once it is in)
  if (was.font !== display.font) (display.font ? archivoReady() : Promise.resolve()).then(() => { fitPlaceholder(); refitCalendars(); });
});

// ---------- move to another device ----------
const moveDialog = document.getElementById('moveDialog');
const APP_ID = 'aip2026-program';
let moveTrigger = null, pendingImport = null;
qrcode.stringToBytes = qrcode.stringToBytesFuncs['UTF-8'];
function agendaIds(){ return agendaSaved().map(it => it.t ? it.t.id : it.s.id); }
// QR code as SVG with a 4-module quiet zone, dark on light in both colour schemes;
// null when the text needs a code too dense to scan reliably.
function qrSvg(text){
  for (const level of ['L']){
    let qr;
    try { qr = qrcode(0, level); qr.addData(text, 'Byte'); qr.make(); }
    catch (e) { continue; }
    const n = qr.getModuleCount(), q = 4, size = n + 2 * q;
    if (n > 117) continue;  // past version 25 the modules get too small to scan from a screen
    let d = '';
    for (let r = 0; r < n; r++){
      for (let c = 0; c < n; c++){
        if (!qr.isDark(r, c)) continue;
        let w = 1;
        while (c + w < n && qr.isDark(r, c + w)) w++;
        d += `M${c + q} ${r + q}h${w}v1h-${w}z`;
        c += w - 1;
      }
    }
    return { modules: size, svg: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" shape-rendering="crispEdges" role="img" aria-label="QR code of your agenda link"><rect class="qr-bg" width="${size}" height="${size}"/><path class="qr-fg" d="${d}"/></svg>` };
  }
  return null;
}
function renderMoveSend(){
  const box = document.getElementById('moveSend');
  const ids = agendaIds();
  document.getElementById('moveCopyFallback').hidden = true;
  if (!ids.length){
    box.innerHTML = '<p class="md-note">Your agenda is empty on this device, so there is nothing to send yet. To bring an agenda here, use the options below.</p>';
    return;
  }
  const link = linkTo('agenda=' + ids.join(','));
  const qr = qrSvg(link);
  const local = !/^https?:$/.test(location.protocol);
  const n = countWord(agendaItems().length, 'item');
  // On a phone (touch or a narrow screen) the QR code would be scanned by... the same
  // phone: lead with Share, Copy and the file, and keep the QR code for another phone.
  const phone = matchMedia('(pointer: coarse)').matches || PHONE_MQ.matches;
  const canShare = typeof navigator.share === 'function';
  const qrHtml = cap => qr
    ? `<div class="qr-box" style="--qr-size:${Math.max(260, Math.min(360, qr.modules * 4))}px">${qr.svg}</div><p class="qr-cap">${cap}</p>`
    : `<p class="md-warn">Your agenda (${n}) is too long for a QR code that phones can read reliably. Use Copy link, the agenda code or the file instead.</p>`;
  const buttons = `<div class="md-row">
      ${phone && canShare ? '<button type="button" class="toggle primary" data-move-share>Share link&#8230;</button>' : ''}
      <button type="button" class="toggle" data-move-copy="link">Copy link</button>
      <button type="button" class="toggle" data-move-copy="code">Copy agenda code</button>
      <button type="button" class="toggle" id="moveDownload">Download file</button>
    </div>`;
  const warn = local ? `<p class="md-warn">This page is open from a file on this computer, so the ${phone ? 'link and QR code only work' : 'QR code and link only work'} here. The agenda code and the file work on any device.</p>` : '';
  const note = `<p class="md-note">On the other device, open the link; or open this page there, open <b>My agenda</b>, then <b>Export</b>, then <b>Move to another device</b>, and paste the code or import the file.</p>`;
  box.innerHTML = phone
    ? `<p class="md-lead">Send your agenda (${n}) to your other device: share or copy the link, or save the file.</p>` + buttons + warn + note +
      (qr ? `<details class="md-qr"><summary>Show QR code (to scan with another phone)</summary>${qrHtml('Scan this with the other phone’s camera to open your agenda there, then tap <b>Add</b>.')}</details>` : qrHtml(''))
    : qrHtml(`Scan with your phone’s camera to open your agenda (${n}) there, then tap <b>Add</b>.`) + warn + buttons + note;
}
function openMoveDialog(trigger, fromHistory){
  moveTrigger = trigger;
  pendingImport = null;
  renderMoveSend();
  // a pasted code stays until it is imported (a tap outside the box closes it)
  showImportResult('');
  hideToast();
  moveDialog.showModal();
  moveDialog.scrollTop = 0;
  if (!fromHistory) pnlHistoryOpen('move');
}
lightDismiss(moveDialog, () => moveDialog.close());
moveDialog.addEventListener('close', () => {
  pnlHistoryClose();
  pendingImport = null;
  const back = [moveTrigger, document.getElementById('moveAgenda'), document.getElementById('builderTitle')]
    .find(el => el && el.isConnected && el.getClientRects().length);
  back?.focus({ preventScroll: true });
});
document.getElementById('moveAgenda').addEventListener('click', () => { exportSay(''); openMoveDialog(exportBtn); });
document.getElementById('builder').addEventListener('click', e => {
  const b = e.target.closest('[data-open-move]');
  if (b) openMoveDialog(b);
});
async function copyFromDialog(text, what){
  const fallback = document.getElementById('moveCopyFallback');
  try {
    await navigator.clipboard.writeText(text);
    fallback.hidden = true;
    toast(what + ' copied');
  } catch (e) {
    const input = document.getElementById('moveCopyBox');
    fallback.hidden = false;
    input.value = text;
    input.focus();
    input.select();
  }
}
moveDialog.addEventListener('click', async e => {
  if (e.target.closest('[data-move-share]')){
    const url = linkTo('agenda=' + agendaIds().join(','));
    try { await navigator.share({ title: 'My AIP Congress 2026 agenda', url }); }
    catch (err) { if (!err || err.name !== 'AbortError') copyFromDialog(url, 'Link'); }
    return;
  }
  const copy = e.target.closest('[data-move-copy]');
  if (copy){
    const ids = agendaIds().join(',');
    if (copy.dataset.moveCopy === 'link') copyFromDialog(linkTo('agenda=' + ids), 'Link');
    else copyFromDialog(ids, 'Agenda code');
    return;
  }
  if (e.target.closest('#moveDownload')){
    const file = JSON.stringify({ app: APP_ID, version: 1, exported: new Date().toISOString(), items: agendaIds() }, null, 2) + '\n';
    try {
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([file], { type: 'application/json' }));
      a.download = 'aip-congress-2026-my-agenda.json';
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      toast('Saved aip-congress-2026-my-agenda.json');
    } catch (err) {
      copyFromDialog(file, 'File contents');
    }
    return;
  }
  const act = e.target.closest('[data-import]');
  if (act && pendingImport){
    const { ids, fresh } = pendingImport;
    pendingImport = null;
    document.getElementById('importText').value = '';
    if (act.dataset.import === 'merge'){
      const before = agendaItems().length;
      mergeIntoAgenda(fresh);
      moveDialog.close();
      toast(addedMessage(before));
    } else {
      const n = mergeSaved(agendaSaved(new Set(ids))).length;
      replaceStars(ids, `Agenda replaced with ${countWord(n, 'imported item')}`);
      moveDialog.close();
      document.getElementById('undoBtn').focus();
    }
  }
});

// Reads a pasted link (…#agenda=…), an agenda code (id,id,…) or an exported file.
function parseAgendaInput(text){
  const raw = (text || '').trim();
  if (!raw) return { error: 'Paste a link, an agenda code or the contents of an agenda file first.' };
  let ids;
  if (/^[\[{]/.test(raw)){
    let obj;
    try { obj = JSON.parse(raw); }
    catch (e) { return { error: 'This looks like an agenda file, but it isn’t complete or valid. Download the file again, or copy the agenda code instead.' }; }
    const ours = obj && !Array.isArray(obj) && obj.app === APP_ID;
    const list = Array.isArray(obj) ? obj : obj && Array.isArray(obj.items) ? obj.items : null;
    if (ours && !list) return { error: 'This agenda file has no list of items. It may be damaged: download it again, or copy the agenda code instead.' };
    if (Array.isArray(obj) && !obj.every(x => typeof x === 'string')) return { error: 'This isn’t an AIP Congress 2026 agenda. Paste a link, an agenda code or the file from “Download file”.' };
    if (!list || (obj && obj.app && obj.app !== APP_ID)) return { error: 'This file isn’t an AIP Congress 2026 agenda. Use the file from “Download file”.' };
    ids = list.filter(x => typeof x === 'string').map(x => x.trim());
  } else {
    const m = /[#?&]agenda=([^&#\s]*)/.exec(raw);
    // A real URL (scheme://… or a known non-hierarchical scheme) without agenda= is a link without an agenda;
    // anything else with a "Label:" prefix (e.g. "Agenda: c1,c2") is read as a code after the label.
    if (!m && /^(?:[a-z][a-z0-9+.-]*:\/\/|(?:file|mailto|data|blob|about|javascript):)|^www\./i.test(raw)) return { error: 'This link doesn’t carry an agenda. Use the link from “Copy link” or “Share link”.' };
    let code = m ? m[1] : raw.replace(/^[^:,;\n]{1,60}:\s*/, '');
    try { code = decodeURIComponent(code); } catch (e) {}
    ids = code.split(/[\s,;]+/).filter(Boolean);
  }
  const unique = [...new Set(ids)];
  const items = resolveAgendaIds(unique);
  if (!items.length) return { error: unique.length
    ? 'Nothing in it matches a session or talk in this program. Check that the whole link or code was copied.'
    : 'No sessions or talks found in it.' };
  return { items, unknown: unique.length - items.length };
}
function showImportResult(html, error){
  const el = document.getElementById('importResult');
  el.classList.toggle('error', !!error);
  el.innerHTML = html;
}
function previewImport(text){
  const r = parseAgendaInput(text);
  if (r.error){ pendingImport = null; showImportResult(esc(r.error), true); return; }
  const ids = r.items.map(it => it.id);
  const fresh = ids.filter(id => !state.starred.has(id));
  pendingImport = { ids, fresh };
  const t = agendaTally(r.items);
  const have = agendaItems().length;
  const same = !fresh.length && state.starred.size === ids.length;
  showImportResult(`<p><b>Found ${countWord(t.n, 'item')}</b> (${t.words}): ${t.fresh} new${t.have ? `, ${t.have} already in your agenda` : ''}.${r.unknown ? ` ${r.unknown} unknown code${r.unknown === 1 ? ' was' : 's were'} skipped.` : ''}</p>
    ${same ? '<p>Your agenda already matches it exactly.</p>'
      : have ? `<p>Add keeps your ${have} saved item${have === 1 ? '' : 's'}; Replace swaps ${have === 1 ? 'it' : 'them'} for this list (you can undo).</p>` : ''}
    <div class="md-row">${fresh.length ? `<button type="button" class="toggle primary" data-import="merge">${addLabel(t.fresh, fresh.length)} to my agenda</button>` : ''}${have && !same ? `<button type="button" class="toggle" data-import="replace">Replace my agenda</button>` : ''}</div>
    <details><summary>See what’s in it</summary>${agendaPreviewList(r.items)}</details>`);
  document.querySelector('#importResult [data-import]')?.focus();
}
document.getElementById('importTextBtn').addEventListener('click', () => previewImport(document.getElementById('importText').value));
document.getElementById('importFileBtn').addEventListener('click', () => document.getElementById('importFile').click());
document.getElementById('importFile').addEventListener('change', async e => {
  const file = e.target.files && e.target.files[0];
  e.target.value = '';
  if (!file) return;
  if (file.size > 1e6){ showImportResult('That file is too large to be an agenda file.', true); return; }
  let text;
  try { text = await file.text(); }
  catch (err) { showImportResult('This file couldn’t be read. Try again, or paste its contents below.', true); return; }
  previewImport(text);
  if (!pendingImport) document.getElementById('importFileBtn').focus();
});

