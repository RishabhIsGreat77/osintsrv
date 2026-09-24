// web/static/app.js — front-end for osint-srv web UI

const tabs = document.querySelectorAll('.tab');
const form = document.getElementById('scan-form');
const targetInput = document.getElementById('target');
const runBtn = document.getElementById('run-btn');
const statusEl = document.getElementById('status');
const statusText = document.getElementById('status-text');
const resultEl = document.getElementById('result');

let currentModule = 'username';

const PLACEHOLDERS = {
  username: 'johndoe',
  phone: '+919876543210',
  email: 'john@example.com',
  domain: 'example.com'
};

tabs.forEach(t => {
  t.addEventListener('click', () => {
    tabs.forEach(x => x.classList.remove('active'));
    t.classList.add('active');
    currentModule = t.dataset.module;
    targetInput.placeholder = PLACEHOLDERS[currentModule] || '';
    targetInput.focus();
  });
});

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s == null ? '' : String(s);
  return d.innerHTML;
}

function renderUsername(res) {
  if (res.error) return `<p class="dim">${esc(res.error)}</p>`;
  const found = res.found || [];
  const total = res.total || 0;
  let html = `<h3>username: <span class="mono">${esc(res.username)}</span></h3>`;
  html += `<p class="dim">found ${found.length}/${total}</p>`;
  if (!found.length) {
    html += `<p class="dim">no profiles found.</p>`;
    return html;
  }
  html += `<table class="result-table"><thead><tr><th>site</th><th>status</th><th>url</th></tr></thead><tbody>`;
  for (const r of found) {
    html += `<tr><td class="site">${esc(r.site)}</td><td class="found">${esc(r.status)}</td><td class="mono"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.url)}</a></td></tr>`;
  }
  html += `</tbody></table>`;
  return html;
}

function renderPhone(res) {
  if (!res.valid) return `<p class="dim">invalid number: ${esc(res.error || '')}</p>`;
  const info = res.info || {};
  let html = `<h3>phone: <span class="mono">${esc(res.input)}</span></h3>`;
  html += `<dl class="kv">`;
  for (const [k, v] of Object.entries({
    'e164': info.e164, 'national': info.national,
    'country': '+' + info.country_code, 'region': info.region,
    'carrier': info.carrier, 'line type': info.line_type,
    'timezones': (info.timezones || []).join(', ')
  })) {
    html += `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`;
  }
  html += `</dl>`;
  if (res.checks?.length) {
    html += `<h4>platform presence</h4><table class="result-table"><thead><tr><th>platform</th><th>status</th><th>url</th></tr></thead><tbody>`;
    for (const c of res.checks) {
      const cls = c.exists === true ? 'found' : c.exists === false ? 'notfound' : 'unknown';
      const txt = c.exists === true ? 'exists' : c.exists === false ? 'no' : 'unknown';
      html += `<tr><td class="site">${esc(c.platform)}</td><td class="${cls}">${txt}</td><td class="mono"><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.url)}</a></td></tr>`;
    }
    html += `</tbody></table>`;
  }
  if (res.dorks?.length) {
    html += `<h4>manual search</h4><ul>`;
    for (const d of res.dorks) {
      html += `<li>${esc(d.site)} — <a href="${esc(d.url)}" target="_blank" rel="noopener" class="mono">${esc(d.url)}</a></li>`;
    }
    html += `</ul>`;
  }
  return html;
}

function renderEmail(res) {
  if (!res.valid) return `<p class="dim">invalid email.</p>`;
  let html = `<h3>email: <span class="mono">${esc(res.email)}</span></h3>`;
  const mx = res.mx || {};
  html += `<dl class="kv">`;
  html += `<dt>mx records</dt><dd>${esc((mx.mx || []).join(', ') || mx.error || '-')}</dd>`;
  html += `<dt>disposable</dt><dd>${res.disposable ? 'yes' : 'no'}</dd>`;
  if (res.gravatar?.exists) html += `<dt>gravatar</dt><dd>${esc(res.gravatar.name || 'found')} — <a href="${esc(res.gravatar.url)}" target="_blank" rel="noopener">open</a></dd>`;
  if (res.pgp?.exists) html += `<dt>pgp key</dt><dd>found (${esc(res.pgp.size)} bytes)</dd>`;
  if (res.github?.exists) html += `<dt>github commits</dt><dd><a href="${esc(res.github.url)}" target="_blank" rel="noopener">search</a></dd>`;
  if (res.pastebin?.exists) html += `<dt>pastebin</dt><dd>${esc(res.pastebin.count)} hits — <a href="${esc(res.pastebin.url)}" target="_blank" rel="noopener">open</a></dd>`;
  html += `</dl>`;
  if (res.dorks?.length) {
    html += `<h4>manual search</h4><ul>`;
    for (const d of res.dorks) {
      html += `<li>${esc(d.site)} — <a href="${esc(d.url)}" target="_blank" rel="noopener" class="mono">${esc(d.url)}</a></li>`;
    }
    html += `</ul>`;
  }
  return html;
}

function renderDomain(res) {
  if (!res.valid) return `<p class="dim">invalid domain.</p>`;
  let html = `<h3>domain: <span class="mono">${esc(res.domain)}</span></h3>`;
  const whois = res.whois || {};
  if (Object.keys(whois).length && !whois.error) {
    html += `<h4>whois</h4><dl class="kv">`;
    for (const [k, v] of Object.entries(whois)) {
      html += `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`;
    }
    html += `</dl>`;
  }
  const dns = res.dns || {};
  const dnsRows = Object.entries(dns).filter(([_, v]) => v && v.length);
  if (dnsRows.length) {
    html += `<h4>dns</h4><table class="result-table"><thead><tr><th>type</th><th>value</th></tr></thead><tbody>`;
    for (const [t, vals] of dnsRows) {
      html += `<tr><td class="site">${esc(t)}</td><td class="mono">${esc(vals.join('\n'))}</td></tr>`;
    }
    html += `</tbody></table>`;
  }
  const subs = res.subdomains || [];
  if (subs.length) {
    html += `<h4>subdomains (${subs.length} via crt.sh)</h4><ul class="mono">`;
    for (const s of subs.slice(0, 200)) html += `<li>${esc(s)}</li>`;
    if (subs.length > 200) html += `<li class="dim">… and ${subs.length - 200} more</li>`;
    html += `</ul>`;
  }
  return html;
}

const RENDERERS = {
  username: renderUsername,
  phone: renderPhone,
  email: renderEmail,
  domain: renderDomain
};

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const target = targetInput.value.trim();
  if (!target) return;

  resultEl.hidden = true;
  resultEl.innerHTML = '';
  statusEl.hidden = false;
  statusText.textContent = `scanning ${currentModule}: ${target}…`;
  runBtn.disabled = true;

  const body = {
    module: currentModule,
    target,
    proxy: document.getElementById('opt-proxy').value.trim() || undefined,
    timeout: parseFloat(document.getElementById('opt-timeout').value) || undefined,
    concurrent: parseInt(document.getElementById('opt-concurrent').value) || undefined,
    region: document.getElementById('opt-region').value.trim() || undefined,
    aggressive: document.getElementById('opt-aggressive').checked,
    use_content: document.getElementById('opt-content').checked
  };

  const t0 = performance.now();
  try {
    const r = await fetch('/api/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    });
    const res = await r.json();
    const dt = ((performance.now() - t0) / 1000).toFixed(2);
    statusEl.hidden = true;
    resultEl.hidden = false;
    const render = RENDERERS[currentModule] || (() => '<p>no renderer</p>');
    resultEl.innerHTML = render(res) + `<p class="dim">completed in ${dt}s</p>`;
  } catch (err) {
    statusEl.hidden = true;
    resultEl.hidden = false;
    resultEl.innerHTML = `<p class="dim">error: ${esc(err.message)}</p>`;
  } finally {
    runBtn.disabled = false;
  }
});
