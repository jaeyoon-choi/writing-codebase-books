// Page checks run by build_pdf.py in the page after Paged.js has laid out the book.
// Returns [{page, kind, what}], where page is the 1-based PDF page index.
(() => {
  const issues = [];
  // n: the data-n number build_pdf.py gives each p and h2-h4, so that a fix can target it.
  const add = (page, kind, el, extra, more) => {
    const text = (el.textContent || el.getAttribute('alt') || '').replace(/\s+/g, ' ').trim().slice(0, 60);
    const numbered = el.closest('[data-n]');
    issues.push(Object.assign({page, kind, n: numbered ? numbered.dataset.n : null,
                               what: `${el.tagName.toLowerCase()}${extra ? ' ' + extra : ''}: ${text}`}, more || {}));
  };
  const pages = [...document.querySelectorAll('.pagedjs_page')];
  // The width of a space in a block's font, measured outside any justified line.
  const spaces = new Map();
  const spaceWidth = (st) => {
    const key = `${st.fontStyle} ${st.fontWeight} ${st.fontSize} ${st.fontFamily}`;
    if (!spaces.has(key)) {
      const sp = document.createElement('span');
      sp.style.cssText = `position: absolute; visibility: hidden; white-space: pre; font: ${key}`;
      sp.textContent = 'x x';
      document.body.appendChild(sp);
      const x = document.createElement('span');
      x.style.cssText = sp.style.cssText;
      x.textContent = 'xx';
      document.body.appendChild(x);
      spaces.set(key, sp.getBoundingClientRect().width - x.getBoundingClientRect().width);
      sp.remove();
      x.remove();
    }
    return spaces.get(key);
  };
  const BLOCKS = 'p, li, pre, table, figure, blockquote, h1, h2, h3, h4, .chapter-head, .part-head';
  const rect = (el) => el.getBoundingClientRect();
  const margins = (el) => { const s = getComputedStyle(el); return parseFloat(s.marginTop) + parseFloat(s.marginBottom); };
  const pageOf = (el) => pages.indexOf(el.closest('.pagedjs_page'));
  const areaOf = (i) => rect(pages[i].querySelector('.pagedjs_page_content'));
  const sectionOf = (el) => { const s = el.closest('section'); return s && (s.dataset.id || s.id); };
  // The top-level box of a numbered element: the element when a section holds it, the wrapper of
  // a highlighted listing, or none when the element is inside another block.
  const top = (el) => el.parentElement.tagName === 'SECTION' ? el
    : el.tagName === 'PRE' && el.parentElement.classList.contains('hl') &&
      el.parentElement.parentElement.tagName === 'SECTION' ? el.parentElement : null;
  // Top-level blocks in reading order with their parts (one per page that holds some of the block),
  // and the blocks on each page.
  const seq = [], at = new Map(), onPage = pages.map(() => []);
  pages.forEach((pg, i) => pg.querySelectorAll('.pagedjs_page_content [data-n]').forEach((el) => {
    const box = top(el);
    if (!box || rect(box).height === 0) return;
    const n = el.dataset.n;
    if (!at.has(n)) { at.set(n, seq.length); seq.push({n, el, parts: []}); }
    seq[at.get(n)].parts.push(box);
    onPage[i].push({n, el, box});
  }));

  // Listing cuts (build_pdf.py split_listings). A cut is named by the listing and the line, counted
  // over the whole listing, that starts the part after it (data-l: the first line of a part).
  const listingOf = (pre) => pre.dataset.n.replace(/b+$/, '');
  const firstLine = (pre) => Number(pre.dataset.l || 0);
  // The cut that brings the first lines of listing part `pre`, which opens the next page, into
  // `room` px at the end of this page. A part that continues the listing from this page gives its
  // lines to the part before (the cut moves, or goes when all lines fit); any other part is cut
  // into a new part with its own box, when at least three lines go and two stay.
  const cutFor = (pre, room) => {
    const cont = pre.classList.contains('cont-prev');
    if (!cont) {
      const s = getComputedStyle(pre);
      room -= parseFloat(s.paddingTop) + parseFloat(s.paddingBottom) + 2 * parseFloat(s.borderTopWidth) + margins(pre);
    }
    const lines = [...pre.querySelectorAll('.ln')];
    let k = 0;
    for (const ln of lines) {
      const h = rect(ln).height;
      if (h > room) break;
      room -= h;
      k++;
    }
    // Not right after a line that the next one continues (a call cut after its comma, a block after
    // its brace): the cut goes up to three lines earlier, to the end of the statement.
    const open = (ln) => /(?:[,(\[{\\=?]|&&|\|\||<<|\+)\s*$/.test(ln.textContent);
    let back = k;
    while (back > 0 && k - back < 3 && open(lines[back - 1])) back--;
    if (back > 0 && !open(lines[back - 1])) k = back;
    const n = listingOf(pre), l0 = firstLine(pre);
    if (cont && k === lines.length) return {uncut: n, at: l0};
    if (cont && k >= 1 && lines.length - k >= 2) return {split: n, at: l0 + k, replace: l0};
    if (!cont && k >= 3 && lines.length - k >= 2) return {split: n, at: l0 + k};
    return null;
  };
  // A cut whose two parts landed on one page is no longer needed.
  document.querySelectorAll('.pagedjs_page_content pre.cont-next').forEach((pre) => {
    const next = document.querySelector(`.pagedjs_page_content pre[data-n="${pre.dataset.n}b"]`);
    if (next && pageOf(next) === pageOf(pre)) {
      issues.push({page: pageOf(pre) + 1, kind: 'cut-mid-page', what: `pre ${pre.dataset.n} and ${next.dataset.n}`,
                   uncut: listingOf(pre), at: firstLine(next)});
    }
  });

  // Figure moves (build_pdf.py move_figures; data-moved lists the blocks the figure went past). A
  // moved figure goes back to the earliest of its places where it fits on that page, all the way
  // back when it fits where the manuscript has it. A move that no longer fills its page is taken
  // back in check 4.
  const undone = new Set();
  document.querySelectorAll('.pagedjs_page_content figure[data-moved]').forEach((fig) => {
    if (undone.has(fig.dataset.n)) return;
    const moved = fig.dataset.moved.split(' ');
    let need = rect(fig).height + margins(fig);
    for (let j = 0; j < moved.length && at.has(moved[j]); j++) {
      const {el, parts} = seq[at.get(moved[j])];
      // A figure among the moved blocks travels with this one (check 4): the two need room together.
      if (el.tagName === 'FIGURE') { need += rect(el).height + margins(el); continue; }
      const q = pageOf(parts[0]);
      if (areaOf(q).bottom - (rect(parts[0]).top - parseFloat(getComputedStyle(el).marginTop)) >= need) {
        undone.add(fig.dataset.n);
        issues.push({page: q + 1, kind: 'move-undone', what: `figure ${fig.dataset.n} fits before ${moved[j]}`,
                     fig: fig.dataset.n, keep: moved.slice(0, j)});
        break;
      }
    }
  });

  // The least that a heading, table or lead paragraph needs on a page to start there: the run of
  // headings, table captions and short lead paragraphs from it, and the start of the block they
  // lead into (two lines of text, three lines of a listing, the head and two rows of a table, or
  // all of a block that does not break).
  const lineH = (el) => parseFloat(getComputedStyle(el).lineHeight) || 16;
  const groupNeed = (k) => {
    let need = 0;
    for (; k < seq.length; k++) {
      const {el, parts} = seq[k];
      const h = rect(parts[0]).height, m = margins(el);
      const prev = k > 0 ? seq[k - 1].el : null;
      if (/^H[234]$/.test(el.tagName) || el.classList.contains('tcap') || (el.tagName === 'P' && !el.className &&
          prev && /^H[234]$/.test(prev.tagName) && parts.length === 1 && h < 2.5 * lineH(el))) {
        need += h + m;
        continue;
      }
      if (el.tagName === 'PRE') {
        const lines = [...el.querySelectorAll('.ln')];
        const body = lines.reduce((s, ln) => s + rect(ln).height, 0);
        return need + (lines.length >= 5 ? h - body + 3 * rect(lines[0]).height : h) + m;
      }
      if (el.tagName === 'TABLE' && getComputedStyle(el).breakInside !== 'avoid') {
        const rows = [...el.querySelectorAll(':scope > tbody > tr')].slice(0, 2);
        return need + (el.tHead ? rect(el.tHead).height : 0) + rows.reduce((s, r) => s + rect(r).height, 0) + m;
      }
      if (/^(P|UL|OL)$/.test(el.tagName) && !el.className) return need + Math.min(h, 2 * lineH(el)) + m;
      return need + h + m;
    }
    return need;
  };
  // Page breaks that fixes of earlier passes forced (build_pdf.py lists them with the check that
  // asked for each). One is no longer needed when what it moved would now fit on the page before;
  // a break before a heading and its lead line also goes when it leaves that page less than 60% full.
  (window.__fixBreaks || []).forEach(({sel, why}) => {
    const el = document.querySelector(`.pagedjs_page_content ${sel}`);
    const i = el ? pageOf(el) : -1;
    if (i < 1 || !onPage[i - 1].length) return;
    const a = areaOf(i - 1);
    const bottom = Math.max(...onPage[i - 1].map((b) => rect(b.box).bottom));
    let need = Infinity;
    if (el.tagName === 'TR') {
      // The row alone when two rows of its part stay here, or the rest of the table when it ends here.
      const t = el.closest('table');
      const rest = [...t.querySelectorAll(':scope > tbody > tr')].filter((r) => rect(r).height > 0 && rect(r).top >= rect(el).top);
      if (rest.length >= 3) need = rect(el).height;
      else if (!t.dataset.splitTo) need = rest.reduce((s, r) => s + rect(r).height, 0);
    } else if (at.has(el.dataset.n)) {
      need = groupNeed(at.get(el.dataset.n));
    }
    const fill = (bottom - a.top) / a.height;
    if (need <= a.bottom - bottom - 16 || (why === 'lead' && fill < 0.6)) {
      issues.push({page: i + 1, kind: 'break-unneeded', what: `${sel} (${why}): page ${i} is ${(fill * 100).toFixed(0)}% full`,
                   drop: sel, veto: why === 'lead'});
    }
  });

  // Every block and listing line must be visible on some page. Paged.js leaves content that it
  // failed to carry over in a hidden overflow column of the page, so such content is lost. A
  // listing line or body row must not be visible on two pages (a table that Paged.js started
  // again repeats its rows); the head row a table part repeats is not counted.
  const seen = new Map();
  pages.forEach((pg, i) => {
    const n = i + 1;
    const area = pg.querySelector('.pagedjs_page_content');
    if (!area) return;
    const a = area.getBoundingClientRect();
    const blocks = [...area.querySelectorAll(BLOCKS)].filter((el) => el.getBoundingClientRect().height > 0);
    // A page that shows nothing, other than a blank page before a recto start.
    if (!pg.classList.contains('pagedjs_blank_page') && !area.textContent.trim() && !area.querySelector('img, svg')) {
      issues.push({page: n, kind: 'empty-page', what: 'no content'});
    }
    area.querySelectorAll(BLOCKS + ', .ln, tr').forEach((el) => {
      const ref = el.dataset.ref;
      if (!ref) return;
      const r = el.getBoundingClientRect();
      const visible = r.left < a.right && r.right > a.left;
      if (!seen.has(ref)) seen.set(ref, {visible, page: n, el});
      else if (visible && seen.get(ref).visible && seen.get(ref).page !== n && (el.classList.contains('ln') ||
               el.tagName === 'TR' && !el.closest('thead'))) add(n, 'duplicate', el, `(also on page ${seen.get(ref).page})`);
      else if (visible) seen.get(ref).visible = true;
    });

    // 1. Anything past the text block.
    area.querySelectorAll(BLOCKS + ', img, td, th, code, .ln').forEach((el) => {
      const r = el.getBoundingClientRect();
      // Inline code in a pre-wrap listing counts its hanging trailing spaces, so a listing is checked
      // by its pre and line blocks. The box of a fragment that goes on to the next page is not
      // reliable (it reaches into Paged.js's overflow columns), so its lines are checked instead.
      if (r.height === 0 || el.closest('pre') && el.tagName !== 'PRE' && !el.classList.contains('ln')) return;
      if (el.dataset.splitTo && r.right > a.right + 1) return;
      if (r.right > a.right + 1) add(n, 'overflow-x', el, `+${(r.right - a.right).toFixed(0)}px`);
      if (r.bottom > a.bottom + 1 && !el.closest('section.cover')) {
        // Paged.js ignores break-inside on multi-column blocks (the index), so the fix moves the
        // heading before such a block instead (head).
        const block = el.closest('[data-n]');
        const prev = block && block.previousElementSibling;
        const head = prev && /^H[234]$/.test(prev.tagName) ? prev.dataset.n : null;
        add(n, 'overflow-y', el, `+${(r.bottom - a.bottom).toFixed(0)}px`, {head});
      }
    });
    area.querySelectorAll('pre, td, th').forEach((el) => {
      if (el.scrollWidth > el.clientWidth + 1) add(n, 'clipped', el, `${el.scrollWidth - el.clientWidth}px`);
    });
    area.querySelectorAll('img').forEach((el) => { if (!el.naturalWidth) add(n, 'missing-image', el, el.getAttribute('src')); });
    // Text of a block that goes on to the next page but stayed behind in an overflow column.
    area.querySelectorAll('p[data-split-to], li[data-split-to], td[data-split-to], th[data-split-to]').forEach((el) => {
      const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
      for (let t = w.nextNode(); t; t = w.nextNode()) {
        const rg = document.createRange();
        rg.selectNodeContents(t);
        const r = rg.getBoundingClientRect();
        if (t.textContent.trim() && r.width > 0 && r.left > a.right + 1) {
          add(n, 'lost', el, `text "${t.textContent.trim().slice(0, 30)}"`);
          break;
        }
      }
    });
    // A figure is one unit: its caption must not go to another page.
    area.querySelectorAll('figure[data-split-to]').forEach((el) => add(n, 'figure-split', el));

    // 2. A heading or table caption with nothing after it on its page.
    area.querySelectorAll('h2, h3, h4, p.tcap').forEach((h) => {
      const hb = h.getBoundingClientRect().bottom;
      const after = blocks.some((b) => !b.contains(h) && !h.contains(b) && b.getBoundingClientRect().top >= hb - 1);
      if (!after) add(n, 'heading-at-bottom', h);
    });

    // 3. One line of a paragraph or list item left alone at the bottom (orphan) or top (widow) of a
    // page. A list item that holds paragraphs or other blocks is checked by those.
    area.querySelectorAll('p[data-split-to], p[data-split-from]').forEach((p) => {
      const lh = parseFloat(getComputedStyle(p).lineHeight) || 16;
      const h = p.getBoundingClientRect().height;
      if (h >= lh * 1.5) return;
      if (p.dataset.splitTo) { add(n, 'orphan', p); return; }
      // Lines of the same paragraph on the previous page: moving them over leaves that much space.
      const prev = i > 0 ? pages[i - 1].querySelector(`p[data-n="${p.dataset.n}"]`) : null;
      const before = prev ? Math.round(prev.getBoundingClientRect().height / lh) : 99;
      add(n, 'widow', p, `(${before} lines before)`, {before});
    });
    area.querySelectorAll('li[data-split-to], li[data-split-from]').forEach((li) => {
      if (!li.dataset.li || li.closest('section.index, section.toc') || li.querySelector('p, ul, ol, pre, table, blockquote')) return;
      const lh = parseFloat(getComputedStyle(li).lineHeight) || 16;
      if (rect(li).height >= lh * 1.5) return;
      const sel = `li[data-li="${li.dataset.li}"]`;
      if (li.dataset.splitTo) { add(n, 'orphan', li, '', {sel}); return; }
      const prev = i > 0 ? pages[i - 1].querySelector(sel) : null;
      const before = prev ? Math.round(rect(prev).height / lh) : 99;
      add(n, 'widow', li, `(${before} lines before)`, {before, sel});
    });

    // 4. A page much emptier than it needs to be: its section goes on to the next page.
    if (blocks.length && i + 1 < pages.length) {
      const bottom = Math.max(...blocks.map((b) => b.getBoundingClientRect().bottom));
      const fill = (bottom - a.top) / a.height;
      const next = pages[i + 1].querySelector('.pagedjs_page_content [data-split-from]');
      // Below 60% the page is reported; up to 75% a fix is still tried (kind 'loose').
      if (fill < 0.75 && next) {
        const item = {page: n, kind: fill < 0.6 ? 'sparse' : 'loose', what: `fill ${(fill * 100).toFixed(0)}%`};
        // What opens the next page decides the fix (build_pdf.py fixes_for):
        // a figure floats below the following paragraphs that fit here (listed in `paras`;
        // build_pdf.py checks that they follow the figure directly), and a listing, alone or
        // after a heading, is cut into two listings after the lines that fit here.
        const free = a.bottom - bottom - 16;
        const [first, second] = onPage[i + 1].map((b) => b.el);
        if (first && first.tagName === 'FIGURE' && !undone.has(first.dataset.n)) {
          const mm = 96 / 25.4;
          const img = first.querySelector('img');
          const deficit = first.getBoundingClientRect().height + 6 * mm - (a.bottom - bottom) + 4;
          if (img && deficit > 0 && deficit <= 0.05 * img.getBoundingClientRect().height) {
            // Short of the space by at most 5% of its height: the figure shrinks to fit here.
            item.shrink = first.dataset.n;
            item.maxh = ((img.getBoundingClientRect().height - deficit) / mm).toFixed(1);
          } else {
            // Otherwise it floats below the following top-level blocks (paragraphs, lists,
            // listings, tables, boxes, h3 and h4 headings) that fit here, as a LaTeX float goes to
            // the next page top; an h2, another figure or a listing cut into parts stops the run,
            // and a heading or a table caption never ends it (the figure would land between the
            // caption and its table). A block split over two pages counts with all its parts.
            // Figures that directly follow this one go with it (carry), in their order.
            const moved = first.dataset.moved ? first.dataset.moved.split(' ') : [];
            const run = [], hs = [], carry = [];
            let used = 0;
            for (let k = at.get(first.dataset.n) + 1; k < seq.length; k++) {
              const {n: m, el, parts} = seq[k];
              if (el.tagName === 'FIGURE' && !run.length && !el.dataset.moved && sectionOf(el) === sectionOf(first)) {
                if (!moved.includes(m)) carry.push(m);
                continue;
              }
              if (/^(H[12]|FIGURE)$/.test(el.tagName) || !/^\d+$/.test(m) || /cont-(next|prev)/.test(el.className) ||
                  sectionOf(el) !== sectionOf(first)) break;
              const h = parts.reduce((s, p) => s + rect(p).height, 0) + margins(el);
              if (used + h > free) break;
              used += h;
              run.push(m);
              hs.push(h);
            }
            const lastEl = () => seq[at.get(run[run.length - 1])].el;
            while (run.length && (/^H[34]$/.test(lastEl().tagName) || lastEl().classList.contains('tcap'))) {
              run.pop();
              used -= hs.pop();
            }
            // Worth the change of reading order only when the page ends up 75% full or the moved
            // blocks (with those moved in earlier passes) fill at least a third of the space.
            const before = moved.reduce((s, m) => s + (at.has(m) ? seq[at.get(m)].parts.filter((p) => pageOf(p) === i)
              .reduce((t, p) => t + rect(p).height, 0) : 0), 0);
            const useful = (bottom + used - a.top) / a.height >= 0.75 || before + used >= (a.bottom - bottom - used) / 2;
            item.fig = first.dataset.n;
            if (useful && run.length) item.paras = moved.concat(carry, run);
            else if (!useful && moved.length) Object.assign(item, {keep: [], veto: true});
          }
        }
        const listing = first && first.tagName === 'PRE' ? first
          : first && /^H[234]$/.test(first.tagName) && second && second.tagName === 'PRE' ? second : null;
        if (listing && listing.dataset.n) {
          Object.assign(item, cutFor(listing, free - (first === listing ? 0 : rect(first).height + margins(first))) || {});
        }
        if (item.kind === 'sparse' || (item.paras && item.paras.length) || item.keep || item.split || item.uncut || item.shrink) {
          issues.push(item);
        }
      }
    }

    // 5. A table split so that one of its parts holds at most one body row (each part repeats the
    // head row, so longer parts read well). The fix keeps a short table whole; a longer one sends
    // its first part with its caption and heading to the next page, or one more row to the last.
    area.querySelectorAll('table[data-split-to], table[data-split-from]').forEach((t) => {
      const rows = [...t.querySelectorAll(':scope > tbody > tr')].filter((r) => rect(r).height > 0);
      if (rows.length > 1) return;
      const all = document.querySelectorAll(`.pagedjs_page_content table[data-n="${t.dataset.n}"] > tbody > tr`);
      const total = Math.max(0, ...[...all].map((r) => Number(r.dataset.r) || 0));
      const item = {page: n, kind: 'table-split', n: t.dataset.n, total,
                    what: `table: ${rows.length} of ${total} rows on this page`};
      if (!t.dataset.splitFrom) {
        // Its caption, headings and a short lead paragraph right after a heading go with it.
        let lead = t;
        for (let p = t.previousElementSibling; p; p = p.previousElementSibling) {
          const head = /^H[234]$/.test(p.tagName) || p.classList.contains('tcap');
          const intro = p.tagName === 'P' && !p.className && !p.dataset.splitFrom && rect(p).height < 2.5 * lineH(p) &&
            p.previousElementSibling && /^H[234]$/.test(p.previousElementSibling.tagName);
          if (!head && !intro) break;
          lead = p;
        }
        item.lead = lead.dataset.n;
      } else if (rows.length) {
        item.row = Number(rows[0].dataset.r) - 1;
      }
      issues.push(item);
    });

    // 6. A heading and a lead paragraph of at most two lines closing the page while what they
    // introduce (a listing, figure or table) opens the next page. A listing is cut so that its
    // first lines join them when three lines fit; otherwise the heading goes to the next page,
    // when the page stays 60% full and the heading, lead and figure fit on one page.
    if (i + 1 < pages.length && onPage[i].length >= 2 && onPage[i + 1].length) {
      const [h, p] = onPage[i].slice(-2).map((b) => b.el);
      const nx = onPage[i + 1][0].el;
      if (/^H[234]$/.test(h.tagName) && p.tagName === 'P' && !p.className && !p.dataset.splitTo &&
          !p.dataset.splitFrom && rect(p).height < lineH(p) * 2.5 && sectionOf(nx) === sectionOf(p) &&
          !nx.dataset.splitFrom && !nx.classList.contains('cont-prev') &&
          (/^(PRE|FIGURE|TABLE)$/.test(nx.tagName) || nx.classList.contains('tcap'))) {
        const item = {page: n, kind: 'heading-lead-at-bottom', n: h.dataset.n,
                      what: `${h.tagName.toLowerCase()}: ${h.textContent.trim().slice(0, 50)} (next page opens with ${nx.tagName.toLowerCase()})`};
        const start = rect(h).top - parseFloat(getComputedStyle(h).marginTop);
        const group = rect(p).bottom - start + (nx.tagName === 'FIGURE' ? rect(nx).height + margins(nx) : 0);
        if (nx.tagName === 'PRE') Object.assign(item, cutFor(nx, a.bottom - rect(p).bottom - 16) || {});
        if (!item.split && ((start - a.top) / a.height < 0.6 || group > a.height)) item.kind = 'heading-lead-kept';
        issues.push(item);
      }
    }

    // 7. A justified line whose word spaces stretch to more than 2.4 times their natural width: inline
    // code or a long name that did not fit moved to the next line and left few spaces to fill the
    // rest. The fix spreads the extra width of the paragraph's lines over every character boundary
    // (text-justify: inter-character), which changes no line break.
    area.querySelectorAll('p[data-n]').forEach((p) => {
      const st = getComputedStyle(p);
      if (st.textAlign !== 'justify' || st.textJustify === 'inter-character') return;
      const natural = spaceWidth(st);
      let widest = 0;
      const w = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
      for (let t = w.nextNode(); t; t = w.nextNode()) {
        if (t.parentElement.closest('.nobr')) continue;
        for (let k = t.data.indexOf(' '); k !== -1; k = t.data.indexOf(' ', k + 1)) {
          const rg = document.createRange();
          rg.setStart(t, k);
          rg.setEnd(t, k + 1);
          const r = rg.getClientRects()[0];
          if (r && r.left >= a.left && r.right <= a.right + 1) widest = Math.max(widest, r.width);
        }
      }
      if (widest > 2.4 * natural) {
        add(n, 'wide-gaps', p, `(space ${(widest / natural).toFixed(1)} times its width)`);
      }
    });
  });
  seen.forEach((s) => { if (!s.visible) add(s.page, 'lost', s.el); });
  // A part opener is one page: report one whose text runs onto the next page.
  document.querySelectorAll('section.part[data-split-to]:not([data-split-from])').forEach((s) => {
    issues.push({page: pages.indexOf(s.closest('.pagedjs_page')) + 1, kind: 'part-overflow', sid: s.id,
                 what: (s.querySelector('h1') || s).textContent.trim()});
  });
  return issues;
})()
