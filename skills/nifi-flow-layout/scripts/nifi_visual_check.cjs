#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (e) {
  console.error('Playwright is required for NiFi visual checks. Install it with: npm install -D playwright && npx playwright install chromium');
  console.error(e && e.message ? e.message : e);
  process.exit(2);
}

function arg(name, fallback = undefined) {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 ? process.argv[i + 1] : fallback;
}
function has(name) { return process.argv.includes(`--${name}`); }

function readPassphrase() {
  const direct = arg('passphrase');
  if (direct) return direct;
  const file = arg('passphrase-file');
  if (!file) return '';
  const key = arg('passphrase-key');
  const lines = fs.readFileSync(file, 'utf8').split(/\r?\n/).map(s => s.trim());
  if (!key) return lines.find(Boolean) || '';
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].toUpperCase().startsWith(key.toUpperCase())) {
      return lines[i + 2] || lines[i + 1] || '';
    }
  }
  return '';
}

(async () => {
  const url = arg('url');
  if (!url) throw new Error('--url is required');
  const out = arg('out', path.resolve(process.cwd(), 'nifi-layout-screenshot.png'));
  const jsonOut = arg('json');
  const origin = arg('origin') || new URL(url).origin;
  const viewport = { width: Number(arg('width', '1800')), height: Number(arg('height', '1200')) };
  const launch = { headless: !has('headed') };
  const contextOptions = { ignoreHTTPSErrors: true, viewport };
  const p12 = arg('p12');
  if (p12) {
    contextOptions.clientCertificates = [{ origin, pfx: fs.readFileSync(p12), passphrase: readPassphrase() }];
  }
  const cert = arg('cert');
  const key = arg('key');
  if (cert && key) {
    contextOptions.clientCertificates = [{ origin, cert: fs.readFileSync(cert), key: fs.readFileSync(key), passphrase: readPassphrase() }];
  }

  const browser = await chromium.launch(launch);
  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(Number(arg('wait', '8000')));

  if (has('hide-controls')) {
    await page.addStyleTag({ content: `
      graph-controls,
      .graph-controls,
      navigation-control,
      operation-control {
        display: none !important;
        visibility: hidden !important;
      }
    ` });
    await page.waitForTimeout(300);
  }

  const data = await page.evaluate(() => {
    const box = el => {
      const r = el.getBoundingClientRect();
      return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) };
    };
    const intersects = (a, b, pad = 0) => !(a.x + a.w <= b.x - pad || a.x >= b.x + b.w + pad || a.y + a.h <= b.y - pad || a.y >= b.y + b.h + pad);
    const dataIds = el => {
      const d = el.__data__ || {};
      const e = d.entity || {};
      const c = e.component || e || {};
      return {
        sourceId: c.source?.id || c.sourceId || '',
        destId: c.destination?.id || c.destinationId || '',
        sourceGroupId: c.sourceGroupId || c.source?.groupId || '',
        destGroupId: c.destinationGroupId || c.destination?.groupId || ''
      };
    };
    const components = [...document.querySelectorAll('g.component')].map(el => ({
      id: el.id,
      rawId: el.id.replace(/^id-/, ''),
      cls: el.getAttribute('class'),
      text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 120),
      box: box(el)
    }));
    const labels = [...document.querySelectorAll('g.connection-label-container')].map(el => {
      const g = el.closest('g.connection');
      return {
        id: g?.id || el.id,
        text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 120),
        box: box(el)
      };
    });
    const connections = [...document.querySelectorAll('g.connection')].map(el => ({
      id: el.id,
      cls: el.getAttribute('class'),
      text: (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 120),
      box: box(el),
      ...dataIds(el)
    }));
    const issues = [];
    for (const l of labels) {
      for (const c of components) {
        if (intersects(l.box, c.box, -1)) {
          issues.push({ type: 'label_overlaps_component', connection: l.id, component: c.id, label: l.box, componentBox: c.box });
        }
      }
    }
    for (let i = 0; i < labels.length; i++) {
      for (let j = i + 1; j < labels.length; j++) {
        if (intersects(labels[i].box, labels[j].box, -1)) {
          issues.push({ type: 'label_overlaps_label', a: labels[i].id, b: labels[j].id, boxA: labels[i].box, boxB: labels[j].box });
        }
      }
    }
    for (const g of [...document.querySelectorAll('g.connection')]) {
      const ids = dataIds(g);
      const path = g.querySelector('path.connection-path');
      if (!path || !path.getTotalLength) continue;
      const toScreen = p => {
        const svg = path.ownerSVGElement;
        const m = path.getScreenCTM();
        if (!svg || !m) return p;
        const pt = svg.createSVGPoint();
        pt.x = p.x; pt.y = p.y;
        const q = pt.matrixTransform(m);
        return { x: q.x, y: q.y };
      };
      const len = path.getTotalLength();
      const steps = Math.max(12, Math.min(200, Math.ceil(len / 10)));
      for (let i = 2; i < steps - 2; i++) {
        const p = toScreen(path.getPointAtLength((len * i) / steps));
        const probe = { x: p.x - 1, y: p.y - 1, w: 2, h: 2 };
        for (const c of components) {
          const rid = c.rawId;
          if (rid === ids.sourceId || rid === ids.destId || rid === ids.sourceGroupId || rid === ids.destGroupId) continue;
          if (intersects(probe, c.box, 2)) {
            const nearBoundary =
              Math.abs(p.x - c.box.x) <= 5 ||
              Math.abs(p.x - (c.box.x + c.box.w)) <= 5 ||
              Math.abs(p.y - c.box.y) <= 5 ||
              Math.abs(p.y - (c.box.y + c.box.h)) <= 5;
            if (nearBoundary) continue;
            issues.push({ type: 'path_crosses_component', connection: g.id, component: c.id, at: { x: Math.round(p.x), y: Math.round(p.y) } });
            i = steps;
            break;
          }
        }
      }
    }
    // Detect the “one thick wire” defect: several connection paths using the same
    // horizontal or vertical segment for a meaningful distance. Intersections are
    // sometimes acceptable; long collinear overlap is not informative.
    const normSeg = (a, b) => {
      if (Math.abs(a.x - b.x) < 2 && Math.abs(a.y - b.y) > 8) return ['v', Math.round((a.x + b.x) / 2), Math.min(a.y, b.y), Math.max(a.y, b.y)];
      if (Math.abs(a.y - b.y) < 2 && Math.abs(a.x - b.x) > 8) return ['h', Math.round((a.y + b.y) / 2), Math.min(a.x, b.x), Math.max(a.x, b.x)];
      return null;
    };
    const overlap = (a, b) => {
      if (!a || !b || a[0] !== b[0] || Math.abs(a[1] - b[1]) > 3) return 0;
      return Math.max(0, Math.min(a[3], b[3]) - Math.max(a[2], b[2]));
    };
    const segs = [];
    for (const g of [...document.querySelectorAll('g.connection')]) {
      const path = g.querySelector('path.connection-path');
      if (!path || !path.getTotalLength) continue;
      const toScreen = p => {
        const svg = path.ownerSVGElement;
        const m = path.getScreenCTM();
        if (!svg || !m) return p;
        const pt = svg.createSVGPoint();
        pt.x = p.x; pt.y = p.y;
        const q = pt.matrixTransform(m);
        return { x: q.x, y: q.y };
      };
      const len = path.getTotalLength();
      const steps = Math.max(8, Math.min(240, Math.ceil(len / 8)));
      let prev = toScreen(path.getPointAtLength(0));
      for (let i = 1; i <= steps; i++) {
        const cur = toScreen(path.getPointAtLength((len * i) / steps));
        const n = normSeg(prev, cur);
        if (n) segs.push({ id: g.id, seg: n });
        prev = cur;
      }
    }
    for (let i = 0; i < segs.length; i++) {
      for (let j = i + 1; j < segs.length; j++) {
        if (segs[i].id === segs[j].id) continue;
        const ol = overlap(segs[i].seg, segs[j].seg);
        if (ol > 40) {
          issues.push({ type: 'path_overlaps_path', a: segs[i].id, b: segs[j].id, overlap: Math.round(ol), orientation: segs[i].seg[0] });
          break;
        }
      }
    }
    return { title: document.title, url: location.href, components, connections, labels, issues };
  });

  await page.screenshot({ path: out, fullPage: false });
  data.screenshot = out;
  if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(data, null, 2));
  console.log(JSON.stringify(data, null, 2));
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
