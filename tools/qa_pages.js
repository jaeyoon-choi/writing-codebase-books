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
  const BLOCKS = 'p, li, pre, table, figure, blockquote, h1, h2, h3, h4, .chapter-head, .part-head';
  // Every block and listing line must be visible on some page. Paged.js leaves content that it
  // failed to carry over in a hidden overflow column of the page, so such content is lost.
  const seen = new Map();
  pages.forEach((pg, i) => {
    const n = i + 1;
    const area = pg.querySelector('.pagedjs_page_content');
    if (!area) return;
    const a = area.getBoundingClientRect();
    const blocks = [...area.querySelectorAll(BLOCKS)].filter((el) => el.getBoundingClientRect().height > 0);
    area.querySelectorAll(BLOCKS + ', .ln, tr').forEach((el) => {
      const ref = el.dataset.ref;
      if (!ref) return;
      const r = el.getBoundingClientRect();
      const visible = r.left < a.right && r.right > a.left;
      if (!seen.has(ref)) seen.set(ref, {visible, page: n, el});
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
    // A figure is one unit: its caption must not go to another page.
    area.querySelectorAll('figure[data-split-to]').forEach((el) => add(n, 'figure-split', el));

    // 2. A heading with nothing after it on its page.
    area.querySelectorAll('h2, h3, h4').forEach((h) => {
      const hb = h.getBoundingClientRect().bottom;
      const after = blocks.some((b) => !b.contains(h) && !h.contains(b) && b.getBoundingClientRect().top >= hb - 1);
      if (!after) add(n, 'heading-at-bottom', h);
    });

    // 3. One line of a paragraph left alone at the bottom (orphan) or top (widow) of a page.
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
        // after a heading, is cut into two listings after the `at` lines that fit here.
        const free = a.bottom - bottom - 16;
        const blocks2 = [...pages[i + 1].querySelectorAll('.pagedjs_page_content ' + BLOCKS.split(', ').join(', .pagedjs_page_content '))]
          .filter((el) => el.getBoundingClientRect().height > 0);
        const [first, second] = blocks2;
        if (first && first.tagName === 'FIGURE' && first.dataset.n) {
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
            // the next page top; an h2 or another figure stops the run, and a heading never ends it.
            item.fig = first.dataset.n;
            item.paras = [];
            let used = 0;
            const top = (el) => el.parentElement.tagName === 'SECTION' ? el
              : el.tagName === 'PRE' && el.parentElement.classList.contains('hl') &&
                el.parentElement.parentElement.tagName === 'SECTION' ? el.parentElement : null;
            for (let k = Number(first.dataset.n) + 1; k < Number(first.dataset.n) + 400; k++) {
              const els = document.querySelectorAll(`[data-n="${k}"]`);
              if (!els.length) break;
              const box = top(els[0]);
              if (!box) continue;                 // inside a block already counted
              if (els.length !== 1 || /^(H[12]|FIGURE)$/.test(els[0].tagName)) break;
              const s = getComputedStyle(els[0]);
              const h = box.getBoundingClientRect().height + parseFloat(s.marginTop) + parseFloat(s.marginBottom);
              if (used + h > free) break;
              used += h;
              item.paras.push(String(k));
            }
            while (item.paras.length && /^H[34]$/.test(document.querySelector(`[data-n="${item.paras[item.paras.length - 1]}"]`).tagName))
              item.paras.pop();
          }
        }
        const listing = first && first.tagName === 'PRE' ? first
          : first && /^H[234]$/.test(first.tagName) && second && second.tagName === 'PRE' ? second : null;
        if (listing && listing.dataset.n) {
          const box = (el) => { const s = getComputedStyle(el); return parseFloat(s.marginTop) + parseFloat(s.marginBottom); };
          const ls = getComputedStyle(listing);
          let room = free - (first === listing ? 0 : first.getBoundingClientRect().height + box(first))
            - parseFloat(ls.paddingTop) - parseFloat(ls.paddingBottom) - 2 * parseFloat(ls.borderTopWidth) - box(listing);
          const lines = [...listing.querySelectorAll('.ln')];
          let k = 0;
          for (const ln of lines) {
            const h = ln.getBoundingClientRect().height;
            if (h > room) break;
            room -= h;
            k++;
          }
          if (k >= 3 && lines.length - k >= 2) Object.assign(item, {split: listing.dataset.n, at: k});
        }
        if (item.kind === 'sparse' || (item.paras && item.paras.length) || item.split || item.shrink) issues.push(item);
      }
    }
  });
  seen.forEach((s) => { if (!s.visible) add(s.page, 'lost', s.el); });
  // A part opener is one page: report one whose text runs onto the next page.
  document.querySelectorAll('section.part[data-split-to]:not([data-split-from])').forEach((s) => {
    issues.push({page: pages.indexOf(s.closest('.pagedjs_page')) + 1, kind: 'part-overflow', sid: s.id,
                 what: (s.querySelector('h1') || s).textContent.trim()});
  });
  return issues;
})()
