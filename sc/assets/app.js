const state={mining:null,crafting:null,rows:[],tab:'all',selected:null};
const els={query:document.getElementById('queryInput'),clear:document.getElementById('clearBtn'),refresh:document.getElementById('refreshBtn'),list:document.getElementById('resultList'),detail:document.getElementById('detailView'),title:document.getElementById('detailTitle'),count:document.getElementById('resultCount'),status:document.getElementById('statusBar'),tabs:[...document.querySelectorAll('.tab')]};
const n=v=>String(v??'').toLowerCase().trim();
const esc=s=>String(s??'').replace(/[&<>"]/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[m]));

async function fetchData(kind,refresh=false){
  const r=await fetch(`data_proxy.php?kind=${kind}${refresh?'&refresh=1':''}`);
  if(!r.ok) throw new Error(`${kind} 載入失敗`);
  return r.json();
}

function buildRows(){
  const rows=[];
  for(const s of (state.mining?.systems||[])) for(const b of (s.bodies||[])) rows.push({kind:'body',title:b.name_zh_tw||b.name_en,sub:`${s.name_zh_tw||s.name_en} / ${b.type||'-'}`,blob:n(JSON.stringify(b)+s.name_en+s.name_zh_tw),raw:b});
  for(const r of (state.mining?.resources_master||[])) rows.push({kind:'resource',title:r.name_zh_tw||r.name_en,sub:r.name_en||'',blob:n(JSON.stringify(r)),raw:r});
  for(const f of (state.mining?.facility_guides||[])) rows.push({kind:'facility',title:f.name_zh_tw||f.name_en||f.facility_name||'未命名設施',sub:f.type||'facility',blob:n(JSON.stringify(f)),raw:f});
  for(const i of (state.crafting?.items||[])) rows.push({kind:'item',title:i.name_zh_tw||i.name_en,sub:i.category||'item',blob:n(JSON.stringify(i)),raw:i});
  state.rows=rows;
}

function matchesTab(kind){return state.tab==='all'||state.tab===kind;}
function render(){
  const q=n(els.query.value); const filtered=state.rows.filter(r=>matchesTab(r.kind)&&(!q||r.blob.includes(q)||n(r.title).includes(q)||n(r.sub).includes(q)));
  els.count.textContent=filtered.length;
  els.list.innerHTML=filtered.map((r,i)=>`<button class="item ${state.selected===r?'active':''}" data-i="${i}"><b>${esc(r.title)}</b><small>${esc(r.kind)} · ${esc(r.sub)}</small></button>`).join('')||'<div class="detail">沒有符合結果</div>';
  [...els.list.querySelectorAll('.item')].forEach(btn=>btn.onclick=()=>show(filtered[Number(btn.dataset.i)]));
}
function show(row){state.selected=row;els.title.textContent=`${row.title}（${row.kind}）`;els.detail.innerHTML=Object.entries(row.raw||{}).map(([k,v])=>`<div class="kv"><b>${esc(k)}</b><br>${esc(typeof v==='object'?JSON.stringify(v,null,2):v)}</div>`).join('');render();}

async function init(refresh=false){
  els.status.textContent='正在同步 mining / crafting...';
  try{const [m,c]=await Promise.all([fetchData('mining',refresh),fetchData('crafting',refresh)]);state.mining=m.data||m;state.crafting=c.data||c;buildRows();els.status.textContent=`完成，共 ${state.rows.length} 筆資料`;state.selected=null;els.detail.textContent='請先選擇一筆結果。';render();}
  catch(e){els.status.textContent=e.message;}
}

els.query.oninput=render;els.clear.onclick=()=>{els.query.value='';render();};els.refresh.onclick=()=>init(true);
els.tabs.forEach(t=>t.onclick=()=>{els.tabs.forEach(x=>x.classList.remove('active'));t.classList.add('active');state.tab=t.dataset.tab;render();});
init();
