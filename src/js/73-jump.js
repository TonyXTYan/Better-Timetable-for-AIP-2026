function openInProgram(go){
  jumpTo(go.dataset.goprogram, go.dataset.jump || '', go.dataset.jumptalk || '');
}

// Open the program on a day and, with `jump`, at that session (and talk). A link in the
// calendar layout (#s=…&layout=calendar) stays in the calendar, in its orientation.
function jumpTo(dayAttr, jump, jumpTalk, layout = 'list'){
  state.day = dayAttr === 'all' || dayAttr === undefined ? 'all' : +dayAttr;
  if (jump){
    clearSearch('q');
    state.group = null;
    state.cats = new Set(Object.keys(DATA.cats));
  }
  const s = jump && slotById(jump);
  // the timeline opens with the session near its left edge
  if (layout === 'calendar' && s && state.day !== 'all' && state.orient !== 'v')
    HZ.left[DATA.days[state.day].date] = toMin(s.start) - (PHONE_MQ.matches ? 15 : 30);
  showView(layout, 'program');
  if (s && layout === 'calendar' && calendarJump(s, jumpTalk)) return;
  if (jump){
    // A day is drawn whole and marked (what has ended, what is on now) before the landing
    // is worked out, and the blocks above the target are measured, not estimated: the page
    // is then where it will stay (All week fills only the session's own block).
    if (state.day === 'all'){ listFill(jump); paintNow(); } else listFill();
    const card = document.querySelector(`#agenda .card[data-sid="${jump}"]`);
    if (card){
      listMeasureAbove(card);
      // (a talk: its row, which opens its details; its abstract stays as it was)
      const talk = jumpTalk && card.querySelector(`.talk[data-tid="${jumpTalk}"] > .t-open`);
      const target = talk || card.querySelector('h3');
      // (with a mouse the target keeps its focus ring, as before; on touch the tint marks it)
      target.focus({ preventScroll: true, focusVisible: !matchMedia('(pointer: coarse)').matches });
      markJumpTarget(target);
      revealInCard(card, talk);
      // (a face still loading, the italic names say, rewraps the text above: place it again
      // once the type is in, unless the reader has scrolled meanwhile)
      if (document.fonts && document.fonts.status === 'loading'){
        let mine = true;
        const ins = ['wheel', 'touchstart', 'keydown', 'pointerdown'], off = () => { mine = false; for (const k of ins) window.removeEventListener(k, off, true); };
        for (const k of ins) window.addEventListener(k, off, { capture: true, passive: true });
        document.fonts.ready.then(() => { if (mine && card.isConnected) revealInCard(card, talk); off(); });
      }
      card.classList.add('flash');
      setTimeout(() => card.classList.remove('flash'), 1400 * motionK() + 100);
      return;
    }
  }
  document.querySelector('#daytabs [aria-pressed="true"]').focus();
}
// The blocks above a jump's target, and its own, are measured at their real height (they
// are only estimated until the browser draws them), so the landing does not move once they
// are, and its block reaches down to it.
function listMeasureAbove(card){
  const all = [...document.querySelectorAll('#agenda .block')], at = all.indexOf(card.closest('.block'));
  const above = all.slice(0, Math.max(0, at + 1)).filter(b => !b._drawn && b.getClientRects().length);
  for (const b of above) b.style.contentVisibility = 'visible';
  const hs = above.map(cihOf);
  above.forEach((b, i) => { b.style.contentVisibility = ''; if (hs[i] > 0) b.style.setProperty('--cih', hs[i] + 'px'); });
}
// On a touch screen the target of a link is marked by a short tint, not a focus ring (a
// ring there crosses the star beside the title); the first key press takes the mark away.
function markJumpTarget(el){
  document.querySelectorAll('.jump-target').forEach(x => x.classList.remove('jump-target'));
  el.classList.add('jump-target');
  const off = () => { el.classList.remove('jump-target'); window.removeEventListener('keydown', off, true); };
  window.addEventListener('keydown', off, true);
}
// Scroll a session card to just under the sticky toolbar, so its header shows above
// the talk; a talk far down a long session goes a quarter of the way down the screen.
function revealInCard(card, summary){
  const bar = stickyWrap.getBoundingClientRect().height, room = window.innerHeight - bar;
  const y = el => el.getBoundingClientRect().top + window.scrollY;
  let top = y(card) - bar - 12;
  if (summary && y(summary) + summary.offsetHeight - top - bar > room * 0.7) top = y(summary) - bar - room * 0.25;
  window.scrollTo({ top: Math.max(0, top), behavior: 'instant' });
}
// What a vertical day keeps stuck under the toolbar over an item: its column heads, in
// their own bar (a grid that scrolls sideways) or atop the grid, unless a short screen
// lets them scroll away (My agenda's one column on a phone on its side); on a phone, whose
// day is one list by start time, the stream chips and the item's time head.
function vtStick(el){
  const lb = el.closest('.vt-lb');
  if (lb){
    const th = tbEdge();
    const low = h => { const cs = h && getComputedStyle(h); return cs && cs.position === 'sticky' ? parseFloat(cs.top) - th + h.offsetHeight : 0; };
    const lh = lb.previousElementSibling, pk = lb.closest('.vt-list')?.previousElementSibling;
    return Math.max(0, low(pk && pk.matches('.vt-picker') ? pk : null), low(lh && lh.matches('.vt-lh') ? lh : null));
  }
  const h = el.closest('.vt-sx')?.querySelector('.vt-hbar') || el.closest('.vt-grid')?.querySelector(':scope > .vt-head');
  return h && getComputedStyle(h).position === 'sticky' ? h.offsetHeight : 0;
}
// The same in a day calendar: the session (or talk) scrolled into view and focused.
function calendarJump(s, tid){
  const t = weekTarget(s.id, tid || '');
  if (!t) return false;
  const hz = t.box.closest('.hz-day');
  if (hz) hzScrollTo(hz, toMin(s.start) - (PHONE_MQ.matches ? 15 : 30), 0, 'instant');
  t.box.scrollIntoView({ block:'center', inline:'nearest', behavior:'instant' });
  const bar = stickyWrap.getBoundingClientRect().bottom;
  const stick = hz ? hz.querySelector('.hz-ruler').offsetHeight + 18 : vtStick(t.box);
  const top = t.box.getBoundingClientRect().top - bar - stick - 12;
  if (top < 0) window.scrollBy({ top, behavior:'instant' });
  t.button.focus({ preventScroll:true });
  t.box.classList.add('week-hit');
  setTimeout(() => t.box.classList.remove('week-hit'), 1400 * motionK() + 200);
  return true;
}

