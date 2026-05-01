<?php ?><!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0b1220">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>SC 採礦 / 製作查詢</title>
  <link rel="stylesheet" href="assets/styles.css?v=fresh-layout-v1">
</head>
<body>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand-wrap">
        <div class="brand-dot"></div>
        <div>
          <h1 class="brand-title">SC 採礦 / 製作查詢</h1>
          <p class="brand-sub">手機像 App、PC 像工作台，一樣保留完整查詢邏輯</p>
        </div>
      </div>
      <div class="header-actions">
        <div id="versionBadge" class="version-badge">採礦 － · 圖紙 －</div>
        <button id="refreshBtn" class="btn btn-primary" type="button">同步資料</button>
      </div>
    </header>

    <section class="search-card">
      <div class="search-row">
        <input id="queryInput" type="search" inputmode="search" autocomplete="off" placeholder="搜尋礦物、地點、設施、圖紙…">
        <button id="clearBtn" class="btn btn-secondary" type="button">清除</button>
        <button id="focusDetailBtn" class="btn btn-ghost" type="button">詳細</button>
      </div>
      <div class="search-meta">
        <span id="miningState" class="chip">採礦：待載入</span>
        <span id="craftingState" class="chip">圖紙：待載入</span>
      </div>
      <div class="helper-text">Enter 套用聯想、↑↓ 切換、Esc 清空/收合；手機可收合欄位避免擁擠。</div>
      <div class="view-switch" role="group" aria-label="版面顯示模式">
        <button id="toggleFiltersBtn" class="btn btn-ghost" type="button">收合篩選</button>
        <button id="toggleResultsBtn" class="btn btn-ghost" type="button">收合結果</button>
        <button id="toggleDetailBtn" class="btn btn-ghost" type="button">收合詳細</button>
      </div>
      <div id="suggestWrap" class="suggest-frame hidden" aria-live="polite">
        <div class="suggest-head">聯想結果</div>
        <div id="suggestions" class="suggest-list"></div>
      </div>
    </section>

    <main class="workspace" id="workspace">
      <aside class="panel left-panel">
        <div class="panel-head">
          <div>
            <div class="panel-title">關聯結果</div>
            <div id="resultMeta" class="panel-subtitle">目前沒有結果</div>
          </div>
          <div id="relatedCount" class="count-pill">0</div>
        </div>
        <div id="modeBar" class="mode-bar" role="tablist" aria-label="搜尋類型">
          <button class="mode-chip active" type="button" data-mode="all">全部</button>
          <button class="mode-chip" type="button" data-mode="resource">礦物</button>
          <button class="mode-chip" type="button" data-mode="body">地點</button>
          <button class="mode-chip" type="button" data-mode="facility">設施</button>
          <button class="mode-chip" type="button" data-mode="item">圖紙</button>
        </div>
        <div id="relatedAccordion" class="panel-scroll result-frame">
          <div id="results" class="result-list"></div>
        </div>
      </aside>

      <section class="panel right-panel detail-panel">
        <div class="panel-head">
          <div>
            <div id="detailTitle" class="panel-title">地圖 / 礦點資訊</div>
            <div id="detailMeta" class="panel-subtitle">請先從聯想或左側清單選擇目標</div>
          </div>
        </div>
        <div class="panel-scroll right-scroll">
          <div id="riskBanner" class="risk-banner hidden"></div>
          <div id="detailOverview" class="detail-overview hidden"></div>
          <div id="detailSections" class="detail-sections"></div>
        </div>
      </section>
    </main>

    <footer class="status-row">
      <div id="statusBar" class="status-bar">正在載入資料…</div>
    </footer>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/dayjs@1/dayjs.min.js"></script>
  <script src="assets/app.js?v=fresh-layout-v1"></script>
</body>
</html>
