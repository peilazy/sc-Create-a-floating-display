
const GOOGLE_MINING_URL = 'https://drive.google.com/uc?export=download&id=1t9L3RSl1gPQRrsltH58uBySzC4_pxWjt';
const GOOGLE_CRAFTING_URL = 'https://drive.google.com/uc?export=download&id=1-nxq45uudEsGzV7IZxddUOeOT0m4b6hx';
const EXEC_HANGAR_IFRAME_URL = 'https://exec.arkanis.cc/';
const FACILITY_IMAGE_MANIFEST_URL = 'assets/facility_guides/facility_image_paths_manifest.txt';

const state = {
  rawMining: null,
  rawCrafting: null,
  resources: [],
  items: [],
  bodies: [],
  facilities: [],
  bodyRows: [],
  resourceCatalog: [],
  suggestions: [],
  resultRows: [],
  selectedResource: null,
  selectedItem: null,
  selectedFacility: null,
  currentBodyId: null,
  selectedResultKey: '',
  recentQueries: [],
  activeMode: 'all',
  selfTimer: { label: '', endAt: 0, timerId: null },
  execTimer: { timerId: null, data: null },
  facilityImageManifest: [],
  facilityImageManifestLoaded: false,
};

const els = {
  query: document.getElementById('queryInput'),
  clearBtn: document.getElementById('clearBtn'),
  refreshBtn: document.getElementById('refreshBtn'),
  statusBar: document.getElementById('statusBar'),
  miningState: document.getElementById('miningState'),
  craftingState: document.getElementById('craftingState'),
  versionBadge: document.getElementById('versionBadge'),
  modeBar: document.getElementById('modeBar'),
  suggestWrap: document.getElementById('suggestWrap'),
  suggestions: document.getElementById('suggestions'),
  relatedAccordion: document.getElementById('relatedAccordion'),
  relatedCount: document.getElementById('relatedCount'),
  results: document.getElementById('results'),
  resultMeta: document.getElementById('resultMeta'),
  detailTitle: document.getElementById('detailTitle'),
  detailMeta: document.getElementById('detailMeta'),
  detailOverview: document.getElementById('detailOverview'),
  detailSections: document.getElementById('detailSections'),
  riskBanner: document.getElementById('riskBanner'),
};

let suggestIndex = 0;
let runTimer = null;

function norm(v) {
  return String(v || '').trim().toLowerCase().replace(/\s+/g, ' ');
}
function esc(v) {
  return String(v || '').replace(/[&<>"']/g, (m) => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[m]));
}
function dedupe(arr) {
  return [...new Set((arr || []).filter(Boolean))];
}
function loadRecent() {
  try { return JSON.parse(localStorage.getItem('sc_mobile_recent_queries_v2') || '[]'); }
  catch { return []; }
}
function saveRecent() {
  localStorage.setItem('sc_mobile_recent_queries_v2', JSON.stringify(state.recentQueries.slice(0, 10)));
}
function rememberQuery(q) {
  const value = String(q || '').trim();
  if (!value) return;
  state.recentQueries = [value, ...state.recentQueries.filter((x) => norm(x) !== norm(value))].slice(0, 10);
  saveRecent();
}
function bilingual(en, zh) {
  const e = String(en || '').trim();
  const z = String(zh || '').trim();
  if (z && e && z !== e) return `${z} / ${e}`;
  return z || e || '-';
}
function bodyTypeZh(kind) {
  return { planet:'行星', moon:'衛星', asteroid_belt:'小行星帶', asteroid_cluster:'小行星群', ring:'環帶', asteroid_world:'小行星世界' }[String(kind || '')] || String(kind || '-');
}
function normalizeType(kind) {
  return { ore:'礦石', gem:'寶石', crafting:'合成材料', resource:'資源' }[String(kind || '').toLowerCase()] || String(kind || '-');
}
function normalizeValueTier(kind) {
  return { very_high:'極高', high:'高', medium_high:'中高', medium:'中', medium_low:'中低', low:'低', watch:'關注' }[String(kind || '').toLowerCase()] || String(kind || '-');
}
function normalizeMode(mode) {
  const m = String(mode || '').trim().toLowerCase();
  return {
    ship:'船挖', roc:'ROC', hand:'手挖', handheld:'手挖', cave:'洞穴', surface:'地表', asteroid:'太空 / 小行星', asteroid_belt:'小行星帶',
    cave_exposed_by_hathor_platform:'Hathor 平台暴露洞穴', cave_exposed_by_hathor_platform_rare:'Hathor 平台暴露洞穴（稀有）',
    collection_contract:'收集合約', delivery:'送貨任務', mercenary:'傭兵任務', surface_outpost:'地表前哨', sand_cave:'沙洞', refinery_station:'精煉空間站',
    lagrange_asteroid_region:'拉格朗日小行星區', surface_location_context:'地表位置補充', ship_mining_low_confidence_community:'船挖位置（社群低信度）',
    reward_facility:'獎勵設施'
  }[m] || String(mode || '-');
}
function boolText(v) {
  if (v === true) return '是';
  if (v === false) return '否';
  return '未知';
}
function mapLevel(v) {
  return { high:'高', medium:'中', low:'低', unknown:'未知', optional:'可選' }[String(v || '').toLowerCase()] || String(v || '未知');
}
function mapCave(v) {
  return { true:'需要', false:'不需要', optional:'可選', unknown:'未知' }[String(v)] || { 'true':'需要', 'false':'不需要' }[String(v).toLowerCase()] || '未知';
}
function fmtDt(ts) {
  if (!ts) return '—';
  const d = new Date(Number(ts) * 1000);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('zh-TW', { hour12:false, month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit' });
}
function normalizeVersion(v) {
  const raw = String(v || '').trim();
  if (!raw) return '－';
  const m = raw.match(/v?(\d+\.\d+\.\d+)/i);
  return m ? m[1] : raw.replace(/^v/i, '');
}
function rowKey(row) {
  return [row.kind, row.body_id || '', row.facility_id || '', row.title || '', row.subtitle || '', row.mode || ''].join('|');
}
function getSystemZh(name) {
  const sys = (state.rawMining?.systems || []).find((s) => norm(s.name_en) === norm(name));
  return sys?.name_zh_tw || '';
}
function getBodyZh(name) {
  const body = state.bodies.find((b) => norm(b.name_en) === norm(name));
  if (body) return body.name_zh;
  return getSystemZh(name);
}
function getResourceByName(query) {
  const key = norm(query);
  if (!key) return null;
  return state.resources.find((item) => {
    const names = [item.name_en, item.name_zh_tw, ...(item.aliases || [])];
    return names.some((name) => norm(name) === key);
  }) || null;
}
function translateResourceName(name) {
  const res = getResourceByName(name);
  return res?.name_zh_tw || '';
}

function formatResourceEntryLine(raw) {
  const txt = String(raw || '').trim();
  if (!txt) return '';
  let name = txt;
  let suffix = '';
  if (txt.includes(' - ')) {
    const parts = txt.split(' - ');
    name = parts.shift() || '';
    suffix = parts.join(' - ');
  }
  const zh = translateResourceName(name);
  const label = zh && norm(zh) !== norm(name) ? `${zh} / ${name}` : name;
  return suffix ? `${label} - ${suffix}` : label;
}
function renderResourceLineHtml(raw) {
  const line = formatResourceEntryLine(raw);
  const txt = String(line || '').trim();
  if (!txt) return '<div class="list-row">-</div>';
  let name = txt;
  let suffix = '';
  if (txt.includes(' - ')) {
    const parts = txt.split(' - ');
    name = parts.shift() || '';
    suffix = parts.join(' - ');
  }
  const parts = name.split(' / ');
  const main = parts.length >= 2
    ? `<span class="resource-zh">${esc(parts[0])}</span><span class="resource-en"> / ${esc(parts.slice(1).join(' / '))}</span>`
    : esc(name);
  return `<div class="list-row">${main}${suffix ? ` - ${esc(suffix)}` : ''}</div>`;
}
function resourceAliases(res) {
  return dedupe([res.name_en, res.name_zh_tw, ...(res.aliases || [])].map((x) => String(x || '').trim()).filter(Boolean));
}
function extractResourceTerms(text) {
  const raw = String(text || '');
  const lower = raw.toLowerCase();
  const found = [];
  for (const res of state.resources) {
    const aliases = resourceAliases(res);
    for (const a of aliases) {
      const t = String(a).toLowerCase();
      if (t && lower.includes(t)) {
        found.push(res.name_en || a);
        break;
      }
    }
  }
  return dedupe(found);
}
function sequenceRatio(a, b) {
  a = String(a || '');
  b = String(b || '');
  if (!a || !b) return 0;
  if (a === b) return 1;
  let matches = 0;
  const short = a.length <= b.length ? a : b;
  const long = a.length <= b.length ? b : a;
  for (let i = 0; i < short.length; i++) {
    if (long.includes(short[i])) matches += 1;
  }
  return matches / Math.max(a.length, b.length);
}
function resourceSuggestScore(q, item) {
  let best = 0;
  for (const cand of item.aliases || []) {
    if (!cand) continue;
    if (q === cand) best = Math.max(best, 1.0);
    else if (cand.startsWith(q)) best = Math.max(best, 0.97);
    else if (q.length >= 2 && cand.includes(q)) best = Math.max(best, 0.90);
    else {
      const ratio = sequenceRatio(q, cand);
      const threshold = q.length <= 3 ? 0.86 : 0.74;
      if (ratio >= threshold) best = Math.max(best, ratio * 0.82);
    }
  }
  return best;
}
function bodySuggestScore(q, cand) {
  if (!q || !cand) return 0;
  if (q === cand) return 1.0;
  if (cand.startsWith(q)) return 0.95;
  if (q.length >= 2 && cand.includes(q)) return 0.84;
  const ratio = sequenceRatio(q, cand);
  const threshold = q.length <= 2 ? 0.88 : 0.76;
  return ratio >= threshold ? ratio * 0.72 : 0;
}
function bodyScore(q, row) {
  const exacts = [row.name_en, row.name_zh, row.system, row.system_zh].map(norm);
  const name = `${row.name_en} ${row.name_zh} ${row.system} ${row.system_zh}`.toLowerCase();
  if (exacts.includes(q)) return 1.0;
  if (name.includes(q)) return 0.95;
  if (q.length >= 2 && row.blob.includes(q)) return 0.82;
  const best = Math.max(sequenceRatio(q, name) * 0.82, sequenceRatio(q, row.blob.slice(0, Math.max(220, q.length * 26))) * 0.72);
  return best;
}

function buildIndices() {
  state.resources = Array.isArray(state.rawMining?.resources_master) ? state.rawMining.resources_master : [];
  state.items = Array.isArray(state.rawCrafting?.items) ? state.rawCrafting.items : [];
  state.facilities = Array.isArray(state.rawMining?.facility_guides) ? state.rawMining.facility_guides : [];
  state.bodies = [];
  for (const system of (state.rawMining?.systems || [])) {
    for (const body of (system.bodies || [])) {
      state.bodies.push({
        id: body.id || `${system.name_en || ''}:${body.name_en || ''}`,
        system: system.name_en || '',
        system_zh: system.name_zh_tw || '',
        name_en: body.name_en || '',
        name_zh: body.name_zh_tw || '',
        type: body.type || '',
        parent: body.parent || '',
        travel: body.travel || {},
        mining: body.mining || {},
        locations: body.locations || [],
        sources: body.sources || [],
      });
    }
  }
  state.bodyRows = state.bodies.map((body) => {
    const bag = [body.name_en, body.name_zh, body.system, body.system_zh, body.parent || '', body.type, bodyTypeZh(body.type)];
    const resourceTerms = new Set();
    for (const loc of body.locations || []) bag.push(loc);
    for (const group of [body.mining.known_surface_resources || [], body.mining.known_cave_resources || [], body.mining.known_asteroid_resources || []]) {
      for (const item of group) {
        const terms = extractResourceTerms(item);
        for (const term of terms) {
          resourceTerms.add(term);
          const zh = translateResourceName(term);
          if (zh) resourceTerms.add(zh);
        }
        bag.push(String(item || ''));
      }
    }
    return { ...body, blob: bag.filter(Boolean).join(' ').toLowerCase(), resource_terms: [...resourceTerms] };
  });
  const catalog = {};
  for (const row of state.bodyRows) {
    for (const term of row.resource_terms || []) {
      const key = norm(term);
      if (!key) continue;
      if (!catalog[key]) catalog[key] = { key, display: term, bodies: [], body_ids: new Set(), aliases: new Set() };
      const entry = catalog[key];
      const zh = translateResourceName(term);
      if (zh) entry.aliases.add(norm(zh));
      entry.aliases.add(norm(term));
      if (!entry.body_ids.has(row.id)) {
        entry.body_ids.add(row.id);
        entry.bodies.push({ id: row.id, name_zh: row.name_zh, name_en: row.name_en, system_zh: row.system_zh, system: row.system });
      }
    }
  }
  state.resourceCatalog = Object.values(catalog).map((entry) => ({ ...entry, aliases: [...entry.aliases] })).sort((a,b) => a.display.length - b.display.length || a.display.localeCompare(b.display));
}


function isExecutiveHangarQuery(query) {
  const q = norm(query).replace(/_/g, '-');
  if (!q) return false;
  const terms = [
    '行政機庫', '行政機庫任務', '機庫任務', '機庫',
    'executive hangars', 'executive hangar', 'exhang',
    'pyam-exhang', 'pyam-exhang-0-1', 'facility-executive-hangars',
    'facility_executive_hangars'
  ].map((x) => norm(x).replace(/_/g, '-'));
  return terms.includes(q) || q.includes('行政機庫') || q.includes('executive hangar') || q.includes('pyam-exhang') || q.includes('exhang');
}

function getExecutiveHangarFacilities() {
  const out = [];
  const seen = new Set();
  for (const facility of state.facilities || []) {
    const itemId = norm(facility.id).replace(/_/g, '-');
    const timerMode = norm(facility.timer_mode).replace(/_/g, '-');
    const body = norm(facility.body).replace(/_/g, '-');
    const terms = dedupe([
      facility.name_en,
      facility.name_zh_tw,
      facility.id,
      facility.timer_mode,
      facility.body,
      ...(facility.aliases || []),
    ]).map((x) => norm(x).replace(/_/g, '-'));
    const matched =
      itemId === 'facility-executive-hangars' ||
      timerMode === 'executive-hangar-live' ||
      body === 'pyam-exhang-0-1' ||
      terms.some((term) => (
        term.includes('行政機庫') ||
        term.includes('executive hangar') ||
        term.includes('executive hangars') ||
        term.includes('pyam-exhang') ||
        term.includes('exhang')
      ));
    if (!matched) continue;
    const key = itemId || norm(facility.name_en) || norm(facility.name_zh_tw) || body;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(facility);
  }
  return out;
}

function filterKindAllowed(kind) {
  return state.activeMode === 'all' || state.activeMode === kind;
}

function findResourceCandidates(query, limit = 8) {
  const q = norm(query);
  if (!q) return [];
  const scored = [];
  for (const item of state.resources) {
    let score = 0;
    for (const alias of resourceAliases(item)) {
      const cand = norm(alias);
      if (!cand) continue;
      if (q === cand) score = Math.max(score, 1.0);
      else if (cand.startsWith(q)) score = Math.max(score, 0.97);
      else if (q.length >= 2 && cand.includes(q)) score = Math.max(score, 0.9);
    }
    if (score > 0) scored.push([score, item]);
  }
  scored.sort((a,b)=>b[0]-a[0]);
  return scored.slice(0, limit).map(([, item]) => item);
}
function findItemCandidates(query, limit = 8) {
  const q = norm(query);
  if (!q) return [];
  const scored = [];
  for (const item of state.items) {
    const terms = dedupe([item.name_en, item.name_zh_tw || item.name_zh, item.name_zh, ...(item.search_terms || [])]);
    let score = 0;
    for (const term of terms) {
      const cand = norm(term);
      if (!cand) continue;
      if (q === cand) score = Math.max(score, 1.0);
      else if (cand.startsWith(q)) score = Math.max(score, 0.94);
      else if (q.length >= 2 && cand.includes(q)) score = Math.max(score, 0.84);
    }
    if (score > 0) scored.push([score, item]);
  }
  scored.sort((a,b)=>b[0]-a[0]);
  return scored.slice(0, limit).map(([, item]) => item);
}
function findFacilityCandidates(query, limit = 8) {
  const q = norm(query);
  if (!q) return [];
  const scored = [];
  for (const f of state.facilities) {
    const terms = dedupe([f.name_en, f.name_zh_tw, f.body, f.system, ...(f.aliases || [])]);
    let score = 0;
    for (const term of terms) {
      const cand = norm(term);
      if (!cand) continue;
      if (q === cand) score = Math.max(score, 1.0);
      else if (cand.startsWith(q)) score = Math.max(score, 0.96);
      else if (q.length >= 2 && cand.includes(q)) score = Math.max(score, 0.88);
    }
    if (score > 0) scored.push([score, f]);
  }
  scored.sort((a,b)=>b[0]-a[0]);
  return scored.slice(0, limit).map(([, item]) => item);
}

function buildSuggestions(query) {
  const q = norm(query);
  const out = [];
  const seen = new Set();
  if (!q) {
    for (const item of state.recentQueries) {
      out.push({ kind:'recent', display:item, query:item, meta:'最近搜尋' });
      if (out.length >= 10) break;
    }
    return out;
  }
  if (filterKindAllowed('resource')) {
    for (const item of state.resourceCatalog) {
      const score = resourceSuggestScore(q, item);
      if (score <= 0) continue;
      const res = getResourceByName(item.display) || getResourceByName(item.key);
      const label = res ? bilingual(res.name_en, res.name_zh_tw) : item.display;
      const key = `resource|${label}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ kind:'resource', display: label, query: res?.name_zh_tw || res?.name_en || item.display, meta: `${item.bodies.length} 個地點`, resource_item: res || null, _score: score + 0.25 });
    }
  }
  if (filterKindAllowed('facility')) {
    for (const item of findFacilityCandidates(q, 8)) {
      const display = bilingual(item.name_en, item.name_zh_tw);
      const key = `facility|${display}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ kind:'facility', display, query: item.name_zh_tw || item.name_en, meta: `${item.system || '-'}｜${item.body || '-'}`, facility_item:item, _score:0.96 });
    }
  }
  if (filterKindAllowed('item')) {
    for (const item of findItemCandidates(q, 8)) {
      const display = bilingual(item.name_en, item.name_zh_tw || item.name_zh);
      const key = `item|${display}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({ kind:'item', display, query: item.name_zh_tw || item.name_zh || item.name_en, meta: item.category_zh_tw || item.category_zh || item.category_en || '圖紙', scc_item:item, _score:0.94 });
    }
  }
  if (filterKindAllowed('body')) {
    const bodySuggestions = [];
    for (const row of state.bodyRows) {
      for (const cand of [row.name_zh, row.name_en, row.system_zh, row.system]) {
        const score = bodySuggestScore(q, norm(cand));
        if (score > 0) {
          bodySuggestions.push([score, { kind:'body', display: row.name_zh || row.name_en, query: row.name_zh || row.name_en, meta: row.system_zh || row.system, body_id: row.id }]);
          break;
        }
      }
    }
    bodySuggestions.sort((a,b)=>b[0]-a[0]);
    for (const [score, item] of bodySuggestions.slice(0, 8)) {
      const key = `body|${item.display}|${item.meta}`;
      if (seen.has(key)) continue;
      seen.add(key);
      item._score = score;
      out.push(item);
    }
  }
  out.sort((a,b)=>(b._score || 0) - (a._score || 0));
  return out.slice(0, 8);
}

function renderSuggestions() {
  els.suggestions.innerHTML = '';
  if (!state.suggestions.length) {
    els.suggestWrap.classList.add('hidden');
    return;
  }
  els.suggestWrap.classList.remove('hidden');
  state.suggestions.forEach((item, idx) => {
    const prefix = item.kind === 'recent' ? '最近' : item.kind === 'resource' ? '礦物' : item.kind === 'item' ? '圖紙' : item.kind === 'facility' ? '設施' : '地點';
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `suggest-item${idx === suggestIndex ? ' active' : ''}`;
    button.innerHTML = `<div class="suggest-main">${esc(prefix)}｜${esc(item.display)}</div>${item.meta ? `<div class="suggest-meta">${esc(item.meta)}</div>` : ''}`;
    button.addEventListener('click', () => applySuggestion(idx));
    els.suggestions.appendChild(button);
  });
}
function setStatus(text) {
  els.statusBar.textContent = text || '—';
}
function setRiskBanner(body) {
  if (!body) {
    els.riskBanner.textContent = '';
    els.riskBanner.classList.add('hidden');
    return;
  }
  const level = mapLevel(body.mining?.hotspot_level || body.mining?.high_quality_confidence || 'unknown');
  els.riskBanner.textContent = `風險 / 熱點：${level}`;
  els.riskBanner.classList.remove('hidden');
}
function compactVersion(raw, fallback = '－') {
  const text = String(raw || '').trim();
  if (!text) return fallback;
  const num = text.match(/v?(\d+\.\d+\.\d+)/i);
  if (num) return num[1];
  const short = text.match(/v(\d+(?:\.\d+)?)/i);
  if (short) return `v${short[1]}`;
  return text.length > 20 ? text.slice(0, 20) + '…' : text;
}
function setVersionBadge() {
  const miningVer = compactVersion(state.rawMining?.meta?.version || state.rawMining?.meta?.dataset_version || '－');
  const craftingVer = compactVersion(state.rawCrafting?.meta?.version || state.rawCrafting?.meta?.dataset_version || '－');
  els.versionBadge.textContent = `採礦 ${miningVer} · 圖紙 ${craftingVer}`;
}


function collapseRelatedAccordion() {
  if (els.relatedAccordion) els.relatedAccordion.open = false;
}
function scrollDetailIntoView() {
  const panel = document.querySelector('.detail-panel');
  if (panel && window.innerWidth < 980) panel.scrollIntoView({ block:'start', behavior:'smooth' });
}
function selectRelatedRow(row) {
  if (!row) return;
  const key = rowKey(row);
  state.selectedResultKey = key;
  if (row.title) {
    els.query.value = row.title;
  }
  showDetailForResult(row, state.selectedResource, key);
  collapseRelatedAccordion();
  scrollDetailIntoView();
}
function prettyTextBlocks(text, limit = 0) {
  const raw = String(text || '').trim();
  if (!raw) return `<div class="list-row">目前無資料。</div>`;
  let normalized = raw.replace(/\r/g, '').trim();
  normalized = normalized.replace(/\n{3,}/g, '\n\n');
  const lines = normalized.split(/\n+/).map((x) => x.trim()).filter(Boolean);
  const rows = [];
  for (const line of lines) {
    if (/^[\-•]/.test(line)) {
      rows.push({ kind:'bullet', text: line.replace(/^[\-•]\s*/, '') });
      continue;
    }
    const kv = line.match(/^([^：:]{1,18})[：:](.+)$/);
    if (kv) rows.push({ kind:'kv', label: kv[1].trim(), value: kv[2].trim() });
    else rows.push({ kind:'p', text: line });
  }
  let out = rows;
  if (limit > 0) out = out.slice(0, limit);
  const html = [];
  let bullets = [];
  const flushBullets = () => {
    if (!bullets.length) return;
    html.push(`<div class="prose-block"><ul class="note-bullet-list">${bullets.map((item) => `<li>${esc(item)}</li>`).join('')}</ul></div>`);
    bullets = [];
  };
  for (const row of out) {
    if (row.kind === 'bullet') {
      bullets.push(row.text);
      continue;
    }
    flushBullets();
    if (row.kind === 'kv') html.push(`<div class="prose-block structured-note"><div class="note-kv-label">${esc(row.label)}</div><div class="note-kv-value">${esc(row.value)}</div></div>`);
    else html.push(`<div class="prose-block note-paragraph">${esc(row.text)}</div>`);
  }
  flushBullets();
  return `<div class="prose-stack">${html.join('')}</div>`;
}
function locationCard(text) {
  const raw = String(text || '').trim();
  if (!raw) return '';
  const parts = raw.split('｜').map((x) => x.trim()).filter(Boolean);
  const title = parts.shift() || raw;
  const system = parts.shift() || '';
  const mode = parts.join('｜');
  return `<div class="location-card"><div class="location-main">${esc(title)}</div>${system ? `<div class="location-sub">${esc(system)}</div>` : ''}${mode ? `<div class="location-tag">${esc(mode)}</div>` : ''}</div>`;
}
function summaryRows(text) {
  const raw = String(text || '').trim();
  if (!raw) return `<div class="list-row">目前無資料。</div>`;
  const rows = raw
    .replace(/\r/g, '')
    .replace(/^[\-•]\s*/gm, '')
    .split(/[\n；;]+/)
    .map((x) => x.trim())
    .filter(Boolean);
  const deduped = [...new Set(rows)];
  return `<div class="location-stack">${deduped.map(locationCard).join('')}</div>`;
}
function metricCard(label, value) {
  return `<div class="metric-card"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value || '-')}</div></div>`;
}
function overviewCard(title, metricsHtml = '', extraHtml = '') {
  return `<section class="overview-card"><div class="overview-heading">${esc(title)}</div>${metricsHtml ? `<div class="metric-grid">${metricsHtml}</div>` : ''}${extraHtml ? `<div class="overview-extra">${extraHtml}</div>` : ''}</section>`;
}
function previewLocations(rows, limit = 3) {
  const list = (rows || []).slice(0, limit);
  if (!list.length) return '';
  return `<div class="overview-block"><div class="overview-block-title">重點採集位置</div><div class="location-stack compact">${list.map(locationCard).join('')}</div></div>`;
}
function resourceOverviewHtml(resourceItem) {
  const locations = collectResourceLocationRows(resourceItem);
  const metrics = [
    metricCard('類型', normalizeType(resourceItem.type)),
    metricCard('採集方式', (resourceItem.mining_modes || []).map(normalizeMode).join('、') || '-'),
    metricCard('價值級別', normalizeValueTier(resourceItem.value_tier || resourceItem.value_level)),
    metricCard('位置數', String(locations.length || (resourceItem.known_locations || []).length || 0)),
  ].join('');
  const extras = [previewLocations(locations, 3)];
  if (resourceItem.notes) extras.push(`<div class="overview-block"><div class="overview-block-title">說明摘要</div>${prettyTextBlocks(resourceItem.notes, 4)}</div>`);
  return overviewCard('基本資訊', metrics, extras.filter(Boolean).join(''));
}
function bodyOverviewHtml(body, resourceItem = null) {
  const mining = body.mining || {};
  const metrics = [
    metricCard('類型', bodyTypeZh(body.type)),
    metricCard('系統', body.system_zh || body.system || '-'),
    metricCard('母體 / 區域', body.parent ? bilingual(body.parent, getBodyZh(body.parent)) : '-'),
    metricCard('高價值可能', boolText(mining.high_quality_possible)),
    metricCard('高價值信度', mapLevel(mining.high_quality_confidence)),
    metricCard('熱點 / 風險', mapLevel(mining.hotspot_level || 'unknown')),
  ].join('');
  const extras = [];
  if (resourceItem) {
    extras.push(`<div class="overview-block"><div class="overview-block-title">目前查詢礦物</div><div class="inline-chips"><span class="info-chip strong">${esc(bilingual(resourceItem.name_en, resourceItem.name_zh_tw))}</span></div></div>`);
    extras.push(`<div class="overview-block"><div class="overview-block-title">採集位置摘要</div><div class="location-stack compact">${collectResourceLocationRows(resourceItem).slice(0, 2).map(locationCard).join('')}</div></div>`);
  }
  if (body.travel?.quick_route || (body.travel?.recommended_hubs || []).length) {
    extras.push(`<div class="overview-block"><div class="overview-block-title">快速路線</div><div class="quick-route">${esc(body.travel?.quick_route || '目前無資料')}</div>${(body.travel?.recommended_hubs || []).length ? `<div class="inline-chips">${body.travel.recommended_hubs.map((x) => `<span class="info-chip">${esc(bilingual(x, getBodyZh(x)))}</span>`).join('')}</div>` : ''}</div>`);
  }
  return overviewCard('基本資訊', metrics, extras.filter(Boolean).join(''));
}
function facilityOverviewHtml(facility) {
  const metrics = [
    metricCard('系統 / 區域', `${facility.system || '-'}｜${facility.body || '-'}`),
    metricCard('類型', facility.facility_type || '-'),
    metricCard('分類', facility.classification || '-'),
    metricCard('狀態', facility.status || '-'),
  ].join('');
  const extras = [];
  if (facility.summary) extras.push(`<div class="overview-block"><div class="overview-block-title">重點說明</div>${prettyTextBlocks(facility.summary, 2)}</div>`);
  if (facility.card_locations?.length) extras.push(`<div class="overview-block"><div class="overview-block-title">常用位置</div><div class="location-stack compact">${facility.card_locations.slice(0,3).map(locationCard).join('')}</div></div>`);
  return overviewCard('基本資訊', metrics, extras.filter(Boolean).join(''));
}
function itemOverviewHtml(item) {
  const metrics = [
    metricCard('分類', item.category_zh_tw || item.category_zh || item.category_en || '-'),
    metricCard('材料數', String(item.materials?.length || 0)),
    metricCard('獲取任務數', String(item.mission_count || 0)),
    metricCard('關鍵字', String((item.search_terms || []).length || 0)),
  ].join('');
  const materials = (item.materials || []).slice(0, 4).map((mat) => `${bilingual(mat.name_en, mat.name_zh_tw || mat.name_zh)} ×${Number(mat.quantity || 1)}`);
  const extras = materials.length ? `<div class="overview-block"></div>` : '';
  return overviewCard('基本資訊', metrics, extras);
}
function locationOverviewHtml(row, resourceItem = null) {
  const extras = [`<div class="overview-block"><div class="overview-block-title">位置</div><div class="location-stack compact">${locationCard(`${row.title || '-'}｜${row.subtitle || '-'}｜${row.mode || row.source || '位置資訊'}`)}</div></div>`];
  if (resourceItem) {
    extras.push(`<div class="overview-block"><div class="overview-block-title">礦物</div><div class="inline-chips"><span class="info-chip strong">${esc(bilingual(resourceItem.name_en, resourceItem.name_zh_tw))}</span></div></div>`);
  }
  return overviewCard('基本資訊', '', extras.join(''));
}

function updateSourceState(miningMeta = {}, craftingMeta = {}) {
  if (els.miningState) {
    const miningState = miningMeta.state || 'cache';
    els.miningState.textContent = `${miningState}｜檢查 ${fmtDt(miningMeta.last_check)}`;
  }
  if (els.craftingState) {
    const craftState = craftingMeta.state || 'cache';
    els.craftingState.textContent = `${craftState}｜檢查 ${fmtDt(craftingMeta.last_check)}`;
  }
  setVersionBadge();
}


function renderResults() {
  els.results.innerHTML = '';
  els.relatedCount.textContent = String(state.resultRows.length || 0);
  if (!state.resultRows.length) {
    els.results.innerHTML = `<div class="result-empty">目前沒有可顯示的關聯資料。</div>`;
    els.resultMeta.textContent = '預設收合｜0 筆';
    return;
  }
  els.resultMeta.textContent = `預設收合｜${state.resultRows.length} 筆`;
  state.resultRows.forEach((row, idx) => {
    const key = rowKey(row);
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = `result-item${(state.selectedResultKey ? state.selectedResultKey === key : idx === 0) ? ' active' : ''}`;
    btn.innerHTML = `<div class="result-title">${esc(row.title || '-')}</div><div class="result-sub">${esc(row.subtitle || row.mode || row.source || '')}</div>`;
    btn.addEventListener('click', () => {
      selectRelatedRow(row);
    });
    els.results.appendChild(btn);
  });
}

function kvCard(label, value) {
  return `<div class="kv-card"><div class="kv-label">${esc(label)}</div><div class="kv-value">${esc(value || '-')}</div></div>`;
}
function listRows(arr) {
  if (!arr || !arr.length) return `<div class="list-row">目前無資料。</div>`;
  return arr.map((x) => `<div class="list-row">${esc(x)}</div>`).join('');
}
function linkButtons(arr) {
  if (!arr || !arr.length) return `<div class="list-row">目前無資料。</div>`;
  return `<div class="external-links">${arr.map((x) => {
    const parts = String(x || '').split('｜');
    const label = parts[0] || x;
    let href = '';
    const t = String(x || '');
    if (/exectimer\.com/i.test(t)) href = 'https://exectimer.com/';
    else if (/pyam\.ltd/i.test(t)) href = 'https://pyam.ltd/';
    else if (/arkanis\.cc/i.test(t)) href = 'https://exec.arkanis.cc/';
    else if (/vercel\.app/i.test(t)) href = 'https://sc-exechang.vercel.app/';
    else if (/contestedzonetimers\.com/i.test(t)) href = 'https://contestedzonetimers.com/';
    return href ? `<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : `<span class="info-chip">${esc(label)}</span>`;
  }).join('')}</div>`;
}
function sectionHtml(section, index) {
  return `<section class="detail-section"><div class="detail-section-title">${esc(section.title)}</div>${section.meta ? `<div class="detail-section-meta">${esc(section.meta)}</div>` : ''}<div class="section-body">${section.html || ''}</div></section>`;
}

function renderDetail(payload) {
  els.detailTitle.textContent = payload.title || '地圖 / 礦點資訊';
  els.detailMeta.textContent = payload.meta || '—';
  setRiskBanner(payload.body || null);
  if (els.detailOverview) {
    const html = payload.overviewHtml || '';
    els.detailOverview.innerHTML = html;
    els.detailOverview.classList.toggle('hidden', !html);
  }
  if (!payload.sections || !payload.sections.length) {
    els.detailSections.innerHTML = `<div class="result-empty">目前沒有可顯示的詳細內容。</div>`;
    return;
  }
  els.detailSections.innerHTML = payload.sections.map(sectionHtml).join('');
  bindSectionInteractions();
}
function bindSectionInteractions() {
  document.querySelectorAll('.blueprint-accordion').forEach((wrap) => {
    wrap.querySelectorAll('.bp-head').forEach((btn) => {
      btn.onclick = () => {
        const card = btn.closest('.bp-card');
        wrap.querySelectorAll('.bp-card').forEach((x) => x.classList.remove('active'));
        card.classList.add('active');
      };
    });
  });
  document.querySelectorAll('.self-timer-btn').forEach((btn) => {
    btn.onclick = () => startSelfTimer(btn.dataset.label || '倒數', Number(btn.dataset.seconds || 0));
  });
}
function startSelfTimer(label, seconds) {
  if (!seconds || seconds <= 0) return;
  state.selfTimer.label = label;
  state.selfTimer.endAt = Date.now() + (seconds * 1000);
  if (state.selfTimer.timerId) clearInterval(state.selfTimer.timerId);
  state.selfTimer.timerId = setInterval(updateSelfTimerBox, 1000);
  updateSelfTimerBox();
}
function updateSelfTimerBox() {
  const box = document.querySelector('[data-self-timer]');
  if (!box) {
    if (state.selfTimer.timerId) clearInterval(state.selfTimer.timerId);
    state.selfTimer.timerId = null;
    return;
  }
  const remain = Math.max(0, state.selfTimer.endAt - Date.now());
  const total = Math.ceil(remain / 1000);
  const hh = String(Math.floor(total / 3600)).padStart(2, '0');
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
  const ss = String(total % 60).padStart(2, '0');
  box.querySelector('.self-timer-label').textContent = state.selfTimer.label || '倒數';
  box.querySelector('.self-timer-value').textContent = `${hh}:${mm}:${ss}`;
  if (total <= 0 && state.selfTimer.timerId) {
    clearInterval(state.selfTimer.timerId);
    state.selfTimer.timerId = null;
  }
}

function blueprintSummaryLines(bp) {
  const mats = (bp.materials || []).map((mat) => `${bilingual(mat.name_en, mat.name_zh_tw || mat.name_zh)} ×${Number(mat.quantity || 1)}`);
  const missions = (bp.missions || []).map((mission) => mission.name_zh_tw || mission.name_zh || mission.name_en || '-');
  return {
    title: bilingual(bp.name_en, bp.name_zh_tw || bp.name_zh),
    meta: `${bp.category_zh_tw || bp.category_zh || bp.category_en || '圖紙'}｜材料 ${bp.materials?.length || 0}｜任務 ${Number(bp.mission_count || 0)}`,
    body: `
      <div class="list-row"><strong>分類：</strong>${esc(bp.category_zh_tw || bp.category_zh || bp.category_en || '-')}</div>
      <div class="list-row"><strong>材料：</strong><br>${mats.length ? mats.map((x) => esc(x)).join('<br>') : '目前無資料'}</div>
      <div class="list-row"><strong>獲取任務：</strong><br>${missions.length ? missions.slice(0, 12).map((x) => esc(x)).join('<br>') : '目前無資料'}</div>
    `
  };
}
function renderBlueprintAccordion(blueprints) {
  if (!blueprints || !blueprints.length) return `<div class="list-row">沒有關聯圖紙。</div>`;
  return `<div class="blueprint-accordion">${blueprints.map((bp, idx) => {
    const info = blueprintSummaryLines(bp);
    return `<div class="bp-card${idx === 0 ? ' active' : ''}"><button class="bp-head" type="button"><div class="bp-head-title">${esc(info.title)}</div><div class="bp-head-meta">${esc(info.meta)}</div></button><div class="bp-body">${info.body}</div></div>`;
  }).join('')}</div>`;
}
function resourceBlueprints(resourceItem, limit = 8) {
  const names = new Set(resourceAliases(resourceItem).map((x) => norm(x)));
  const out = [];
  for (const item of state.items) {
    const materials = item.materials || [];
    if (materials.some((mat) => names.has(norm(mat.name_en)) || names.has(norm(mat.name_zh_tw || mat.name_zh)))) {
      out.push(item);
      if (out.length >= limit) break;
    }
  }
  return out;
}
function bodyMiningBuckets(body, currentResource = null) {
  const currentNames = currentResource ? new Set(resourceAliases(currentResource).map((x) => norm(x))) : new Set();
  const mapGroup = (title, rows) => {
    const cleaned = (rows || []).map((x) => String(x || '').trim()).filter(Boolean);
    const filtered = cleaned.filter((x) => {
      if (!currentNames.size) return true;
      const terms = extractResourceTerms(x);
      if (!terms.length) return true;
      return !terms.some((term) => currentNames.has(norm(term)) || currentNames.has(norm(translateResourceName(term))));
    });
    return { title, values: dedupe(filtered) };
  };
  return [
    mapGroup('地表', body.mining?.known_surface_resources || []),
    mapGroup('洞穴', body.mining?.known_cave_resources || []),
    mapGroup('太空 / 小行星', body.mining?.known_asteroid_resources || []),
  ];
}
function bodyMiningSectionHtml(body, currentResource = null) {
  const buckets = bodyMiningBuckets(body, currentResource).filter((g) => g.values.length);
  if (!buckets.length) return `<div class="list-row">目前無資料。</div>`;
  return `<div class="mineral-groups">${buckets.map((group) => `
    <div class="mineral-group">
      <div class="mineral-group-title">${esc(group.title)}</div>
      <div class="mineral-group-body">${group.values.map((v) => renderResourceLineHtml(v)).join('')}</div>
    </div>
  `).join('')}</div>`;
}

function collectResourceLocationRows(resourceItem) {
  const seen = new Set();
  const out = [];
  const push = (text) => {
    const key = norm(text);
    if (!key || seen.has(key)) return;
    seen.add(key);
    out.push(text);
  };
  const summary = String(resourceItem.known_location_summary || '').replace(/\r/g, '');
  for (const row of summary.split(/[\n；;]+/).map((x) => x.trim()).filter(Boolean)) {
    push(row.replace(/^[\-•]\s*/, ''));
  }
  for (const loc of (resourceItem.known_locations || [])) {
    const bodyDisp = bilingual(loc.body, getBodyZh(loc.body));
    const systemDisp = bilingual(loc.system, getSystemZh(loc.system));
    const mode = normalizeMode(loc.mode);
    push(`${bodyDisp}${systemDisp && systemDisp !== '-' ? `｜${systemDisp}` : ''}${mode && mode !== '-' ? `｜${mode}` : ''}`);
  }
  return out;
}
function resourceSummarySections(resourceItem, includePositions = true) {
  const sections = [];
  const bps = resourceBlueprints(resourceItem, 10);
  const locationRows = includePositions ? collectResourceLocationRows(resourceItem) : [];
  if (bps.length) sections.push({ title:'關聯製作圖紙', meta:'點標題展開，一次只顯示一個圖紙詳細', html: renderBlueprintAccordion(bps), open:false });
  if (locationRows.length) {
    sections.push({ title:'採集位置', meta:`${locationRows.length} 筆`, html:`<div class="location-stack">${locationRows.map(locationCard).join('')}</div>`, open:false });
  }
  if (resourceItem.notes) sections.push({ title:'說明', html: prettyTextBlocks(resourceItem.notes), open:false });
  return sections;
}


function resourceLocations(resourceItem) {
  const results = [];
  const seen = new Set();
  for (const loc of (resourceItem.known_locations || [])) {
    const bodyEn = String(loc.body || '').trim();
    const systemEn = String(loc.system || '').trim();
    const mode = normalizeMode(loc.mode);
    const source = String(loc.source || '').trim();
    let bodyId = null;
    let bodyLabel = bodyEn;
    let systemLabel = systemEn;
    for (const b of state.bodies) {
      if (bodyEn && norm(bodyEn) === norm(b.name_en)) {
        bodyId = b.id;
        bodyLabel = bilingual(b.name_en, b.name_zh);
        systemLabel = bilingual(b.system, b.system_zh);
        break;
      }
    }
    const key = `known|${norm(bodyLabel)}|${norm(systemLabel)}|${norm(mode)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    results.push({ kind:'location', body_id: bodyId, title: bodyLabel || '-', subtitle: systemLabel || '-', mode, source, details: source || '' });
  }
  if (!results.length) {
    for (const row of state.bodyRows) {
      for (const term of row.resource_terms || []) {
        if (norm(term) === norm(resourceItem.name_en) || norm(term) === norm(resourceItem.name_zh_tw)) {
          results.push({ kind:'body', body_id: row.id, title: row.name_zh || row.name_en, subtitle: row.system_zh || row.system });
          break;
        }
      }
    }
  }
  return results;
}

function showBodyDetail(bodyId, resourceItem = null, key = '') {
  clearExecTimerTicker();
  state.currentBodyId = bodyId || null;
  const body = state.bodies.find((b) => String(b.id) === String(bodyId));
  if (!body) {
    renderDetail({ title:'找不到資料', meta:'查無資料', overviewHtml:'', sections:[{ title:'提示', html:'<div class="list-row">找不到指定地點資料。</div>', open:true }] });
    return;
  }
  const sections = [];
  const hasResource = !!resourceItem;
  sections.push({
    title: hasResource ? '可採集的其他礦物' : '地點的所有礦產',
    meta:'依地表 / 洞穴 / 太空分類',
    html: bodyMiningSectionHtml(body, resourceItem),
    open:true,
  });
  if (hasResource) {
    sections.push(...resourceSummarySections(resourceItem, true));
  }
  if ((body.locations || []).length) {
    sections.push({ title:'常見點位', meta:`${body.locations.length} 筆`, html:`<div class="location-stack">${(body.locations || []).slice(0, 16).map((x) => locationCard(x)).join('')}</div>`, open:false });
  }
  state.selectedResultKey = key;
  renderResults();
  renderDetail({ title:bilingual(body.name_en, body.name_zh), meta: body.system_zh || body.system || '地點資訊', body, overviewHtml: bodyOverviewHtml(body, resourceItem), sections });
}


function facilityGroupRows(facility) {
  const list = [];
  if (facility.related_group) {
    const group = state.facilities.filter((f) => String(f.related_group || '') === String(facility.related_group || '')).sort((a,b)=>(Number(a.related_order || 999) - Number(b.related_order || 999)));
    for (const item of group) {
      list.push({ kind:'facility', facility_id:item.id, title:bilingual(item.name_en, item.name_zh_tw), subtitle:`${item.system || '-'}｜${item.body || '-'}`, facility:item });
    }
  }
  if (!list.length) list.push({ kind:'facility', facility_id:facility.id, title:bilingual(facility.name_en, facility.name_zh_tw), subtitle:`${facility.system || '-'}｜${facility.body || '-'}`, facility });
  return list;
}


function clearExecTimerTicker() {
  if (state.execTimer.timerId) {
    clearTimeout(state.execTimer.timerId);
    state.execTimer.timerId = null;
  }
  state.execTimer.data = null;
}
function execPhaseLabel(data) {
  const rawText = String(data?.raw_text || '');
  const phase = String(data?.phase || '').toLowerCase();
  if (/Reset in/i.test(rawText)) return '開放中（倒數關門）';
  if (/Hangar Open/i.test(rawText)) return '開放中';
  if (/Charging in/i.test(rawText)) return '充能中';
  if (/Open in/i.test(rawText)) return '尚未開放';
  if (/Closed/i.test(rawText)) return '關閉';
  return { unknown:'未知', charging:'充能中', active:'可開門', cooldown:'冷卻中', reset:'重置中', closed:'關閉', opening:'準備開啟', open:'已開啟 / 可進入', waiting:'尚未開放', closing:'即將關閉' }[phase] || '未知';
}
function updateExecTimerDom(data) {
  const statusEl = document.getElementById('execTimerStatus');
  const countEl = document.getElementById('execTimerCount');
  const noteEl = document.getElementById('execTimerNote');
  const heroEl = document.getElementById('execTimerHero');
  const lightsEl = document.getElementById('execTimerLights');
  if (!statusEl || !countEl || !noteEl || !heroEl || !lightsEl) return;
  if (!data) {
    heroEl.className = 'timer-hero phase-unknown';
    statusEl.textContent = '無法讀取即時狀態';
    countEl.textContent = '--:--:--';
    noteEl.textContent = '目前保留資料集內的循環說明與快速自訂倒數。';
    lightsEl.innerHTML = '';
    return;
  }
  const elapsed = Math.max(0, Math.floor(Date.now() / 1000 - Number(data.fetched_at || Math.floor(Date.now()/1000))));
  let remaining = data.remaining == null ? null : Math.max(0, Number(data.remaining) - elapsed);
  let lightRemaining = data.light_remaining == null ? null : Math.max(0, Number(data.light_remaining) - elapsed);
  const rawText = String(data.raw_text || '');
  const hasUsefulCountdown = Boolean(data.timer_label) || /(?:Open|Charging|Reset)\s+in\s+\d/i.test(rawText) || (remaining != null && Number(data.remaining) > 0);
  if (!hasUsefulCountdown && remaining === 0) remaining = null;
  const phase = String(data.phase || '').toLowerCase() || 'unknown';
  heroEl.className = `timer-hero phase-${phase}`;
  statusEl.textContent = `行政機庫即時狀態｜SC ExecHang｜${execPhaseLabel(data)}`;
  if (remaining != null) {
    const hh = String(Math.floor(remaining / 3600)).padStart(2,'0');
    const mm = String(Math.floor((remaining % 3600) / 60)).padStart(2,'0');
    const ss = String(remaining % 60).padStart(2,'0');
    countEl.textContent = `${hh}:${mm}:${ss}`;
  } else {
    countEl.textContent = '--:--:--';
    statusEl.textContent = '行政機庫即時狀態｜尚未取得有效倒數';
  }
  const lights = Array.isArray(data.lights_raw) ? data.lights_raw : [];
  lightsEl.innerHTML = lights.map((light) => {
    const key = String(light || '?');
    const cls = key === '綠' ? 'green' : key === '紅' ? 'red' : key === '藍' ? 'blue' : key === '熄' ? 'off' : 'unknown';
    return `<span class="timer-light ${cls}" title="${esc(key)}"></span>`;
  }).join('');
  const bits = [];
  if (data.timer_label) bits.push(`主倒數：${data.timer_label}`);
  if (lightRemaining != null) {
    const mm = String(Math.floor(lightRemaining / 60)).padStart(2,'0');
    const ss = String(lightRemaining % 60).padStart(2,'0');
    bits.push(`燈號倒數 ${mm}:${ss}`);
  }
  if (data.lights_summary) bits.push(`燈號：${data.lights_summary}`);
  bits.push(`來源：${data.source || 'SC ExecHang'}`);
  noteEl.innerHTML = `<div class="timer-subline">${bits.map(esc).join('｜')}</div>`;
  if (state.execTimer.timerId) clearTimeout(state.execTimer.timerId);
  state.execTimer.timerId = setTimeout(() => updateExecTimerDom(state.execTimer.data), 1000);
  if ((remaining != null && remaining <= 0) || (lightRemaining != null && lightRemaining <= 0)) {
    setTimeout(async () => {
      const live = await fetchExecutiveTimer();
      if (live && live.data) {
        state.execTimer.data = live.data;
        updateExecTimerDom(state.execTimer.data);
      }
    }, 1200);
  }
}


async function fetchExecutiveTimer() {
  try {
    const res = await fetch('timer_proxy.php?kind=executive_hangar', { cache:'no-store' });
    const data = await res.json();
    if (res.ok && data.ok) return data;
  } catch (_) {}
  return null;
}


function normalizeFacilityImagePath(path) {
  let value = String(path || '').trim().replace(/\\/g, '/');
  if (!value) return '';
  value = value.replace(/^\.\//, '');
  value = value.replace(/^\/sc\//i, '');
  value = value.replace(/^sc\//i, '');
  if (/^https?:\/\//i.test(value) || value.startsWith('data:')) return value;
  if (value.startsWith('/')) return value;
  if (!/^assets\//i.test(value)) value = `assets/facility_guides/${value}`;
  return value;
}

function parseFacilityManifest(text) {
  const out = [];
  const seen = new Set();
  String(text || '').split(/\r?\n/).forEach((line) => {
    let raw = String(line || '').trim();
    if (!raw || raw.startsWith('#')) return;
    raw = raw.replace(/^[-*]\s*/, '');
    const m = raw.match(/(?:^|[\s:=|,])((?:assets\/)?facility_guides\/[A-Za-z0-9_\-./%()\u4e00-\u9fff]+\.(?:png|jpe?g|webp|gif))/i)
      || raw.match(/([A-Za-z0-9_\-./%()\u4e00-\u9fff]+\.(?:png|jpe?g|webp|gif))/i);
    if (!m) return;
    const path = normalizeFacilityImagePath(m[1]);
    const key = norm(path);
    if (!path || seen.has(key)) return;
    seen.add(key);
    out.push(path);
  });
  return out;
}

async function loadFacilityImageManifest() {
  if (state.facilityImageManifestLoaded) return state.facilityImageManifest;
  state.facilityImageManifestLoaded = true;
  try {
    const res = await fetch(FACILITY_IMAGE_MANIFEST_URL, { cache:'no-store' });
    if (!res.ok) return state.facilityImageManifest;
    const text = await res.text();
    state.facilityImageManifest = parseFacilityManifest(text);
  } catch (err) {
    console.warn('設施地圖 manifest 載入失敗', err);
  }
  return state.facilityImageManifest;
}

function compactImageKey(value) {
  return norm(value).replace(/[^a-z0-9\u4e00-\u9fff]+/g, '');
}

function facilityImageSearchKeys(facility) {
  const raw = dedupe([
    facility?.id,
    facility?.name_en,
    facility?.name_zh_tw,
    facility?.body,
    facility?.related_group,
    ...(facility?.aliases || []),
  ].map((x) => String(x || '').trim()).filter(Boolean));
  const keys = [];
  raw.forEach((x) => {
    const n = norm(x).replace(/_/g, '-');
    const c = compactImageKey(x);
    if (n) keys.push(n);
    if (c) keys.push(c);
  });
  if (/executive|行政|exhang/i.test(raw.join(' '))) {
    keys.push('executive-hangar', 'executive-hangars', 'executivehangar', 'executivehangars', 'executive-hangar-chain', 'executivehangarchain');
  }
  return dedupe(keys).filter(Boolean);
}

function collectFacilityImagePaths(facility) {
  const direct = [];
  for (const key of ['image_paths', 'images', 'map_images', 'diagram_images', 'facility_images']) {
    const arr = facility?.[key];
    if (Array.isArray(arr)) direct.push(...arr);
    else if (typeof arr === 'string' && arr.trim()) direct.push(arr);
  }
  const keys = facilityImageSearchKeys(facility);
  const manifestMatches = (state.facilityImageManifest || []).filter((path) => {
    const p1 = norm(path).replace(/_/g, '-');
    const p2 = compactImageKey(path);
    return keys.some((k) => p1.includes(k) || p2.includes(compactImageKey(k)));
  });
  return dedupe([...direct, ...manifestMatches].map(normalizeFacilityImagePath).filter(Boolean));
}

function facilityImageGalleryHtml(facility) {
  const paths = collectFacilityImagePaths(facility);
  if (!paths.length) {
    return `<div class="result-empty">目前沒有找到這個設施的地圖圖片。請確認 <code>assets/facility_guides/facility_image_paths_manifest.txt</code> 內有圖片路徑，或 JSON 的 facility_guides 內有 image_paths。</div>`;
  }
  return `
    <div class="facility-map-gallery" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;">
      ${paths.map((path, idx) => `
        <a class="facility-map-card" href="${esc(path)}" target="_blank" rel="noopener noreferrer" style="display:block;background:#081118;border:1px solid #2e5a72;border-radius:14px;overflow:hidden;text-decoration:none;color:#d9f4ff;">
          <img src="${esc(path)}" alt="設施地圖 ${idx + 1}" loading="lazy" style="width:100%;height:220px;object-fit:contain;background:#050b10;display:block;">
          <div style="padding:8px 10px;font-size:12px;color:#85a8bb;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${esc(path)}</div>
        </a>
      `).join('')}
    </div>
    <div class="list-row" style="margin-top:8px;color:#85a8bb;">點圖片可開新分頁查看原圖。</div>`;
}


function facilitySections(facility) {
  const sections = [];
  if (facility.summary || facility.access || facility.state_analysis) sections.push({ title:'說明', html:listRows([`概要：${facility.summary || '-'}`, `進入方式：${facility.access || '-'}`, `重點判讀：${facility.state_analysis || '-'}`]) });
  
if (facility.id === 'facility_executive_hangars') {
    const timingHtml = `
      <div class="timer-grid exec-hangar-key-wrap">
        <div class="timer-hero phase-open" id="execTimerHero">
          <div class="timer-label">行政機庫倒數</div>
          <div class="timer-status" id="execTimerStatus">擷取原站即時倒數區</div>

          <div class="exec-hangar-crop-box" style="
            width:100%;
            height:240px;
            overflow:hidden;
            border-radius:16px;
            border:1px solid #2e5a72;
            background:#050b10;
            position:relative;
            margin-top:10px;
          ">
            <iframe
              src="https://sc-exechang.vercel.app/"
              title="Executive Hangar Countdown"
              loading="lazy"
              referrerpolicy="no-referrer-when-downgrade"
              style="
                width:100%;
                height:760px;
                border:0;
                transform:translateY(-76px);
                transform-origin:top left;
                background:#050b10;
              ">
            </iframe>
          </div>

        </div>

        <div class="list-row">${esc(facility.timing || '-').replace(/\n/g, '<br>')}</div>

        <div class="self-timers">
          <button type="button" class="self-timer-btn" data-label="主循環 185 分鐘" data-seconds="11100">主循環 185 分</button>
          <button type="button" class="self-timer-btn" data-label="工程區門 30 分鐘" data-seconds="1800">工程門 30 分</button>
          <button type="button" class="self-timer-btn" data-label="領船後機庫門 10 分鐘" data-seconds="600">機庫門 10 分</button>
        </div>

        <div class="self-timer-box" data-self-timer>
          <div class="timer-label self-timer-label">自訂倒數</div>
          <div class="self-timer-value">--:--:--</div>
        </div>
      </div>`;
    sections.push({ title:'行政機庫倒數 / 時間', meta:'裁切原站即時倒數區 + 本地快速倒數', html: timingHtml });
  } else if (facility.timing || facility.card_timing?.length) {
    sections.push({ title:'時間 / 倒數', html:listRows([facility.timing || '-', ...(facility.card_timing || [])]) });
  }
  if (facility.card_locations?.length) sections.push({ title:'卡片 / Board 位置', html:listRows(facility.card_locations) });
  if (facility.mission_steps?.length) sections.push({ title:'任務步驟', html:listRows(facility.mission_steps) });
  if (facility.rewards?.length || facility.rewards_summary) sections.push({ title:'獎勵', html:listRows([facility.rewards_summary || '-', ...(facility.rewards || [])]) });
  if (facility.countdown_reference?.length || facility.external_tools?.length) sections.push({ title:'外部工具', html:linkButtons(dedupe([...(facility.countdown_reference || []), ...(facility.external_tools || [])])) });
  if (facility.guide) sections.push({ title:'Guide', html: prettyTextBlocks(facility.guide) });
  if (facility.diagram_text) sections.push({ title:'文字圖解', html: prettyTextBlocks(facility.diagram_text) });
  sections.push({ title:'設施地圖 / 圖片', meta:'讀取 assets/facility_guides 與 manifest', html: facilityImageGalleryHtml(facility) });
  if (facility.sources?.length) sections.push({ title:'資料來源', html:listRows(facility.sources) });
  return sections;
}


async function showFacilityDetail(facility, key = '') {
  state.currentBodyId = null;
  state.selectedResultKey = key;
  renderResults();
  clearExecTimerTicker();
  renderDetail({ title:bilingual(facility.name_en, facility.name_zh_tw), meta:`${facility.system || '-'}｜${facility.body || '-'}`, overviewHtml: facilityOverviewHtml(facility), sections: facilitySections(facility) });
  if (facility.id === 'facility_executive_hangars') {
    setStatus('行政機庫倒數已嵌入原站即時區塊');
  }
}


function resourceSummaryRow(resourceItem) {
  return { kind:'resource_summary', title:bilingual(resourceItem.name_en, resourceItem.name_zh_tw), subtitle: normalizeType(resourceItem.type), resource_item: resourceItem };
}
function resourceToFacilityRows(resourceItem) {
  const haystacks = [
    String(resourceItem.notes || ''),
    String(resourceItem.known_location_summary || ''),
    ...(resourceItem.known_locations || []).map((loc) => `${loc.body || ''} ${loc.system || ''} ${loc.mode || ''} ${loc.source || ''}`),
  ].map((x) => norm(x)).filter(Boolean);
  const rows = [];
  const seen = new Set();
  for (const facility of state.facilities) {
    const terms = dedupe([facility.name_en, facility.name_zh_tw, ...(facility.aliases || [])]).map(norm).filter(Boolean);
    if (!terms.length) continue;
    const matched = haystacks.some((hay) => terms.some((term) => term && hay.includes(term)));
    if (!matched) continue;
    const row = { kind:'facility', facility_id:facility.id, title:bilingual(facility.name_en, facility.name_zh_tw), subtitle:`${facility.system || '-'}｜${facility.body || '-'}`, facility };
    const key = rowKey(row);
    if (seen.has(key)) continue;
    seen.add(key);
    rows.push(row);
  }
  return rows;
}
function itemRowsFromBlueprints(items) {
  return (items || []).map((item) => ({ kind:'scc_item', title:bilingual(item.name_en, item.name_zh_tw || item.name_zh), subtitle:item.category_zh_tw || item.category_zh || item.category_en || '圖紙', scc_item:item }));
}
function showResourceSummary(resourceItem, key = '') {
  clearExecTimerTicker();
  state.selectedResultKey = key;
  renderResults();
  renderDetail({ title:bilingual(resourceItem.name_en, resourceItem.name_zh_tw), meta:'礦物資訊', overviewHtml: resourceOverviewHtml(resourceItem), sections: resourceSummarySections(resourceItem, true) });
  setStatus(`礦物【${resourceItem.name_zh_tw || resourceItem.name_en}】資訊`);
}
function showItemDetail(item, key = '') {
  clearExecTimerTicker();
  state.selectedResultKey = key;
  renderResults();
  const materials = (item.materials || []).map((mat) => `${bilingual(mat.name_en, mat.name_zh_tw || mat.name_zh)} ×${Number(mat.quantity || 1)}`);
  const missions = (item.missions || []).map((mission) => mission.name_zh_tw || mission.name_zh || mission.name_en || '-');
  renderDetail({
    title:bilingual(item.name_en, item.name_zh_tw || item.name_zh),
    meta:item.category_zh_tw || item.category_zh || item.category_en || '圖紙',
    overviewHtml: itemOverviewHtml(item),
    sections:[
      { title:'材料', html:listRows(materials), open:true },
      { title:'獲取任務', html:listRows(missions), open:false },
    ]
  });
  setStatus(`圖紙【${item.name_zh_tw || item.name_zh || item.name_en}】｜材料 ${item.materials?.length || 0} 項｜任務 ${Number(item.mission_count || 0)} 筆`);
}
function applyRowsAndShow(rows, onShow, emptyText, statusText) {
  state.resultRows = rows || [];
  state.selectedResultKey = '';
  renderResults();
  if (state.resultRows.length) {
    const first = state.resultRows[0];
    const key = rowKey(first);
    state.selectedResultKey = key;
    onShow(first, key);
  } else {
    renderWaiting(emptyText || '目前沒有可顯示的相關資料。');
    if (statusText) setStatus(statusText);
  }
}
function applyActiveModeNow() {
  const query = String(els.query.value || '').trim();
  if (!query) {
    queueRunSearch();
    return;
  }
  if (state.selectedResource) {
    const resourceItem = state.selectedResource;
    if (state.activeMode === 'all' || state.activeMode === 'body') {
      showResourceResults(resourceItem);
      return;
    }
    if (state.activeMode === 'resource') {
      const rows = [resourceSummaryRow(resourceItem)];
      applyRowsAndShow(rows, (row, key) => showResourceSummary(resourceItem, key), '目前沒有礦物資訊。', `礦物【${resourceItem.name_zh_tw || resourceItem.name_en}】資訊`);
      return;
    }
    if (state.activeMode === 'item') {
      const rows = itemRowsFromBlueprints(resourceBlueprints(resourceItem, 50));
      applyRowsAndShow(rows, (row, key) => showItemDetail(row.scc_item, key), '此礦物目前沒有找到關聯圖紙。', `礦物【${resourceItem.name_zh_tw || resourceItem.name_en}】關聯圖紙 ${rows.length} 筆`);
      return;
    }
    if (state.activeMode === 'facility') {
      const rows = resourceToFacilityRows(resourceItem);
      applyRowsAndShow(rows, (row, key) => showFacilityDetail(row.facility, key), '此礦物目前沒有可對應的設施資料。', `礦物【${resourceItem.name_zh_tw || resourceItem.name_en}】關聯設施 ${rows.length} 筆`);
      return;
    }
  }
  if (state.selectedFacility) {
    const facility = state.selectedFacility;
    if (state.activeMode === 'all' || state.activeMode === 'facility') {
      showFacilityResults(facility);
      return;
    }
    if (state.activeMode === 'body') {
      const body = state.bodies.find((b) => norm(b.name_en) === norm(facility.body) || norm(b.name_zh) === norm(facility.body));
      const rows = body ? [{ kind:'body', body_id:body.id, title:body.name_zh || body.name_en, subtitle:body.system_zh || body.system }] : [];
      applyRowsAndShow(rows, (row, key) => showBodyDetail(row.body_id, null, key), '此設施目前沒有對應地點資料。', `設施【${facility.name_zh_tw || facility.name_en}】對應地點 ${rows.length} 筆`);
      return;
    }
    if (state.activeMode === 'resource') {
      const text = [facility.summary, facility.guide, facility.diagram_text, ...(facility.card_locations || []), ...(facility.rewards || []), ...(facility.external_tools || [])].join(' ');
      const resources = [];
      const seen = new Set();
      for (const res of state.resources) {
        const aliases = resourceAliases(res).map(norm).filter(Boolean);
        if (aliases.some((a) => norm(text).includes(a))) {
          const row = resourceSummaryRow(res);
          const key = rowKey(row);
          if (!seen.has(key)) { seen.add(key); resources.push(row); }
        }
      }
      applyRowsAndShow(resources, (row, key) => showResourceSummary(row.resource_item, key), '此設施目前沒有可對應的礦物資料。', `設施【${facility.name_zh_tw || facility.name_en}】關聯礦物 ${resources.length} 筆`);
      return;
    }
    if (state.activeMode === 'item') {
      renderWaiting('此設施目前沒有可對應的圖紙資料。');
      state.resultRows = [];
      renderResults();
      setStatus(`設施【${facility.name_zh_tw || facility.name_en}】目前無關聯圖紙`);
      return;
    }
  }
  if (state.selectedItem) {
    const item = state.selectedItem;
    if (state.activeMode === 'all' || state.activeMode === 'item') {
      showItemResults(item);
      return;
    }
    if (state.activeMode === 'resource') {
      const rows = [];
      const seen = new Set();
      for (const mat of (item.materials || [])) {
        const res = getResourceByName(mat.name_en) || getResourceByName(mat.name_zh_tw || mat.name_zh);
        if (!res) continue;
        const row = resourceSummaryRow(res);
        const key = rowKey(row);
        if (seen.has(key)) continue;
        seen.add(key);
        rows.push(row);
      }
      applyRowsAndShow(rows, (row, key) => showResourceSummary(row.resource_item, key), '此圖紙目前沒有可對應的礦物資料。', `圖紙【${item.name_zh_tw || item.name_zh || item.name_en}】關聯礦物 ${rows.length} 筆`);
      return;
    }
    if (state.activeMode === 'body') {
      const rows = [];
      const seen = new Set();
      for (const mat of (item.materials || [])) {
        const res = getResourceByName(mat.name_en) || getResourceByName(mat.name_zh_tw || mat.name_zh);
        if (!res) continue;
        for (const loc of resourceLocations(res)) {
          const key = rowKey(loc);
          if (seen.has(key)) continue;
          seen.add(key);
          rows.push(loc);
        }
      }
      applyRowsAndShow(rows, (row, key) => showDetailForResult(row, null, key), '此圖紙目前沒有可對應的地點資料。', `圖紙【${item.name_zh_tw || item.name_zh || item.name_en}】關聯地點 ${rows.length} 筆`);
      return;
    }
    if (state.activeMode === 'facility') {
      renderWaiting('此圖紙目前沒有可對應的設施資料。');
      state.resultRows = [];
      renderResults();
      setStatus(`圖紙【${item.name_zh_tw || item.name_zh || item.name_en}】目前無關聯設施`);
      return;
    }
  }
  queueRunSearch();
}



function isBlueprintListQuery(query) {
  const q = norm(query).replace(/\s+/g, '');
  if (!q) return false;
  return ['圖紙', '藍圖', '製作圖紙', '全部圖紙', '所有圖紙', 'blueprint', 'blueprints', 'crafting', '製作'].includes(q);
}

function showAllBlueprintResults() {
  clearExecTimerTicker();
  state.currentBodyId = null;
  state.selectedResource = null;
  state.selectedItem = null;
  state.selectedFacility = null;
  const rows = (state.items || []).slice().sort((a, b) => {
    const ca = String(a.category_zh_tw || a.category_zh || a.category_en || '');
    const cb = String(b.category_zh_tw || b.category_zh || b.category_en || '');
    const na = String(a.name_zh_tw || a.name_zh || a.name_en || '');
    const nb = String(b.name_zh_tw || b.name_zh || b.name_en || '');
    return ca.localeCompare(cb, 'zh-Hant') || na.localeCompare(nb, 'zh-Hant');
  }).map((item) => ({
    kind: 'scc_item',
    title: bilingual(item.name_en, item.name_zh_tw || item.name_zh),
    subtitle: item.category_zh_tw || item.category_zh || item.category_en || '圖紙',
    scc_item: item,
  }));
  state.resultRows = rows;
  state.selectedResultKey = '';
  renderResults();
  if (rows.length) {
    const first = rows[0];
    showItemDetail(first.scc_item, rowKey(first));
    setStatus(`已列出全部圖紙 ${rows.length} 筆`);
  } else {
    renderWaiting('目前沒有載入任何圖紙資料。');
    setStatus('圖紙資料為空');
  }
}

function showItemResults(item) {
  clearExecTimerTicker();
  state.currentBodyId = null;
  state.resultRows = [{ kind:'scc_item', title:bilingual(item.name_en, item.name_zh_tw || item.name_zh), subtitle:item.category_zh_tw || item.category_zh || item.category_en || '圖紙', scc_item:item }];
  state.selectedResultKey = '';
  renderResults();
  showItemDetail(item, rowKey(state.resultRows[0]));
}


function showResourceResults(resourceItem) {
  clearExecTimerTicker();
  state.currentBodyId = null;
  const rows = resourceLocations(resourceItem);
  state.resultRows = rows;
  state.selectedResultKey = '';
  renderResults();
  setStatus(`礦物【${resourceItem.name_zh_tw || resourceItem.name_en}】關聯區域 ${rows.length} 筆`);
  if (rows.length) {
    const first = rows[0];
    state.selectedResultKey = rowKey(first);
    if (first.body_id) showBodyDetail(first.body_id, resourceItem, rowKey(first));
    else showDetailForResult(first, resourceItem, rowKey(first));
  } else {
    renderDetail({ title:bilingual(resourceItem.name_en, resourceItem.name_zh_tw), meta:'礦物資訊', overviewHtml: resourceOverviewHtml(resourceItem), sections: resourceSummarySections(resourceItem, true) });
  }
}
function showFacilityResults(facility) {
  state.resultRows = facilityGroupRows(facility);
  state.selectedResultKey = '';
  renderResults();
  setStatus(`設施【${facility.name_zh_tw || facility.name_en}】關聯資料 ${state.resultRows.length} 筆`);
  showFacilityDetail(facility, rowKey(state.resultRows[0] || { kind:'facility', facility_id:facility.id, title:facility.name_zh_tw || facility.name_en, subtitle:facility.system || '' }));
}
function showLocationDetail(row, resourceItem = null, key = '') {
  clearExecTimerTicker();
  state.currentBodyId = row.body_id || null;
  state.selectedResultKey = key;
  renderResults();
  const sections = [];
  if (resourceItem) sections.push(...resourceSummarySections(resourceItem, true));
  if (row.details) sections.push({ title:'位置補充', html: prettyTextBlocks(row.details), open:false });
  renderDetail({ title: row.title || '位置資訊', meta: row.subtitle || '位置資訊', overviewHtml: locationOverviewHtml(row, resourceItem), sections });
}

function showDetailForResult(row, resourceItem = null, key = '') {
  if (row.kind === 'scc_item') showItemDetail(row.scc_item || {}, key);
  else if (row.kind === 'resource_summary') showResourceSummary(row.resource_item || resourceItem || {}, key);
  else if (row.kind === 'facility') showFacilityDetail(row.facility || state.facilities.find((f) => f.id === row.facility_id), key);
  else if (row.body_id) showBodyDetail(row.body_id, resourceItem, key);
  else showLocationDetail(row, resourceItem, key);
}

function renderWaiting(text = '請先從上方聯想中選擇正確目標。') {
  clearExecTimerTicker();
  setRiskBanner(null);
  renderDetail({ title:'地圖 / 礦點資訊', meta:'等待選擇', overviewHtml:'', sections:[{ title:'提示', html:`<div class="result-empty">${esc(text)}</div>`, open:true }] });
}

function runSearch() {
  const query = String(els.query.value || '').trim();
  state.suggestions = buildSuggestions(query);
  suggestIndex = 0;
  renderSuggestions();
  if (!query) {
    state.resultRows = [];
    state.selectedResource = null;
    state.selectedItem = null;
    state.selectedFacility = null;
    renderResults();
    renderWaiting('可從最近紀錄、礦物、設施、圖紙或地點聯想中選擇。');
    setStatus('可從最近紀錄、礦物、設施、圖紙或地點聯想中選擇');
    return;
  }
  if (isBlueprintListQuery(query)) {
    showAllBlueprintResults();
    return;
  }
  const resourceCandidates = filterKindAllowed('resource') ? findResourceCandidates(query, 10) : [];
  const itemCandidates = filterKindAllowed('item') ? findItemCandidates(query, 10) : [];
  let facilityCandidates = filterKindAllowed('facility') ? findFacilityCandidates(query, 10) : [];
  if (isExecutiveHangarQuery(query)) {
    const forcedHangars = getExecutiveHangarFacilities();
    if (forcedHangars.length) facilityCandidates = forcedHangars;
  }

  if (state.selectedResource) {
    const names = new Set(resourceAliases(state.selectedResource).map((x) => norm(x)));
    if (names.has(norm(query))) {
      showResourceResults(state.selectedResource);
      return;
    }
  }
  if (state.selectedItem) {
    const names = new Set([state.selectedItem.name_en, state.selectedItem.name_zh_tw, state.selectedItem.name_zh].map(norm));
    if (names.has(norm(query))) {
      showItemResults(state.selectedItem);
      return;
    }
  }
  if (state.selectedFacility) {
    const names = new Set(dedupe([state.selectedFacility.name_en, state.selectedFacility.name_zh_tw, ...(state.selectedFacility.aliases || [])]).map(norm));
    if (names.has(norm(query))) {
      showFacilityResults(state.selectedFacility);
      return;
    }
  }

  if (isExecutiveHangarQuery(query) && facilityCandidates.length) {
    showFacilityResults(facilityCandidates[0]);
    return;
  }

  if (resourceCandidates.length || itemCandidates.length || facilityCandidates.length) {
    state.resultRows = [];
    renderResults();
    renderWaiting('請先從上方聯想中選擇正確礦物、設施、圖紙或地點，之後才會顯示關聯資訊。');
    setStatus(`找到 ${resourceCandidates.length} 個礦物候選、${facilityCandidates.length} 個設施候選、${itemCandidates.length} 個圖紙候選，請先選擇`);
    return;
  }

  const q = norm(query);
  const scored = [];
  for (const row of state.bodyRows) {
    const score = bodyScore(q, row);
    if (score >= 0.16) scored.push([score, row]);
  }
  scored.sort((a,b)=>b[0]-a[0]);
  state.resultRows = scored.slice(0, 24).map(([, row]) => ({ kind:'body', body_id: row.id, title: row.name_zh || row.name_en, subtitle: row.system_zh || row.system }));
  state.selectedResultKey = '';
  renderResults();
  if (state.resultRows.length) {
    showDetailForResult(state.resultRows[0], null, rowKey(state.resultRows[0]));
    setStatus(`地點結果 ${state.resultRows.length} 筆`);
  } else {
    renderWaiting('查無對應資料。');
    setStatus('查無結果');
  }
}

function applySuggestion(idx) {
  const item = state.suggestions[idx];
  if (!item) return;

  if (item.kind === 'recent') {
    els.query.value = item.query;
    rememberQuery(item.query);
    state.selectedResource = null;
    state.selectedItem = null;
    state.selectedFacility = null;

    const nextSuggestions = buildSuggestions(item.query).filter((x) => x.kind !== 'recent');
    if (nextSuggestions.length) {
      state.suggestions = nextSuggestions;
      suggestIndex = 0;
      renderSuggestions();
      applySuggestion(0);
      return;
    }

    els.suggestWrap.classList.add('hidden');
    runSearch();
    scrollDetailIntoView();
    return;
  }

  state.selectedResource = item.resource_item || null;
  state.selectedItem = item.scc_item || null;
  state.selectedFacility = item.facility_item || null;
  els.query.value = item.query;
  rememberQuery(item.query);
  els.suggestWrap.classList.add('hidden');
  runSearch();
  scrollDetailIntoView();
}

async function fetchJson(kind, force = false) {
  const url = `data_proxy.php?kind=${encodeURIComponent(kind)}${force ? '&refresh=1' : ''}`;
  const res = await fetch(url, { cache:'no-store' });
  const text = await res.text();
  let data = null;
  try { data = JSON.parse(text); }
  catch { throw new Error(`${kind} 回傳不是合法 JSON`); }
  const metaFromHeaders = {
    state: res.headers.get('X-SC-State') || '',
    message: decodeURIComponent(res.headers.get('X-SC-Message') || ''),
    last_check: Number(res.headers.get('X-SC-Last-Check') || 0),
    last_update: Number(res.headers.get('X-SC-Last-Update') || 0),
    source_url: decodeURIComponent(res.headers.get('X-SC-Source-Url') || ''),
  };
  if (!res.ok) throw new Error((data && data.error) || `${kind} 載入失敗`);
  if (data && typeof data === 'object' && 'ok' in data) {
    if (!data.ok) throw new Error(data.error || `${kind} 載入失敗`);
    return { payload: data.data ?? null, meta: data.meta || metaFromHeaders };
  }
  return { payload: data, meta: metaFromHeaders };
}

async function loadAll(force = false) {
  setStatus('正在載入資料…');
  try {
    const [mining, crafting] = await Promise.all([fetchJson('mining', force), fetchJson('crafting', force), loadFacilityImageManifest()]);
    state.rawMining = mining.payload;
    state.rawCrafting = crafting.payload;
    buildIndices();
    updateSourceState(mining.meta || {}, crafting.meta || {});
    runSearch();
    const msgParts = [mining.meta?.message, crafting.meta?.message].filter(Boolean);
    setStatus(msgParts.length ? `資料已就緒：${msgParts.join('｜')}` : '資料已就緒，可直接搜尋。');
  } catch (err) {
    if (els.miningState) els.miningState.textContent = '載入失敗';
    if (els.craftingState) els.craftingState.textContent = '載入失敗';
    renderWaiting(`目前無法取得資料。\n\n${err.message}`);
    setStatus(`載入失敗：${err.message}`);
    renderResults();
  }
}

function queueRunSearch() {
  if (runTimer) clearTimeout(runTimer);
  runTimer = setTimeout(runSearch, 70);
}

function bindEvents() {
  els.query.addEventListener('input', () => {
    state.selectedResource = null;
    state.selectedItem = null;
    state.selectedFacility = null;
    queueRunSearch();
  });
  els.query.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' && state.suggestions.length) {
      e.preventDefault();
      suggestIndex = Math.min(state.suggestions.length - 1, suggestIndex + 1);
      renderSuggestions();
    } else if (e.key === 'ArrowUp' && state.suggestions.length) {
      e.preventDefault();
      suggestIndex = Math.max(0, suggestIndex - 1);
      renderSuggestions();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (state.suggestions.length) applySuggestion(suggestIndex);
      else if (state.resultRows.length) selectRelatedRow(state.resultRows[0]);
    } else if (e.key === 'Escape') {
      els.suggestWrap.classList.add('hidden');
    }
  });
  els.clearBtn.addEventListener('click', () => {
    els.query.value = '';
    state.selectedResource = null;
    state.selectedItem = null;
    state.selectedFacility = null;
    queueRunSearch();
  });
  els.refreshBtn.addEventListener('click', () => loadAll(true));
  document.addEventListener('click', (e) => {
    if (!els.suggestWrap.contains(e.target) && e.target !== els.query) els.suggestWrap.classList.add('hidden');
  });
  els.modeBar.querySelectorAll('.mode-chip').forEach((btn) => {
    btn.addEventListener('click', () => {
      els.modeBar.querySelectorAll('.mode-chip').forEach((x) => x.classList.remove('active'));
      btn.classList.add('active');
      state.activeMode = btn.dataset.mode || 'all';
      applyActiveModeNow();
    });
  });
}

window.addEventListener('DOMContentLoaded', () => {
  state.recentQueries = loadRecent();
  bindEvents();
  renderResults();
  renderWaiting('可從最近紀錄、礦物、設施、圖紙或地點聯想中選擇。');
  loadAll(false);
});
