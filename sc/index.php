<?php ?><!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover, maximum-scale=1, user-scalable=no">
  <meta name="theme-color" content="#09111a">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>SC 採礦 製作 查詢系統</title>
  <link rel="stylesheet" href="assets/styles.css?v=appstyle3b">
</head>
<body>
  <div class="bg-grid"></div>
  <div class="bg-glow glow-a"></div>
  <div class="bg-glow glow-b"></div>

  <div class="overlay-shell">
    <header class="titlebar">
      <div class="titlebar-accent"></div>
      <div class="title-wrap">
        <div class="title-main">SC 採礦 製作 查詢系統</div>
        <div class="title-sub">浮動視窗風格 Web 版</div>
      </div>
      <div class="title-actions">
        <div id="versionBadge" class="version-badge">採礦 － · 圖紙 －</div>
        <button id="refreshBtn" class="title-btn" type="button">重新同步</button>
      </div>
    </header>

    <div class="content-wrap">
      <div class="info-row">
        <div class="info-left">資料會先從 Google Drive 讀取，失敗時退回本機快取。</div>
        <div class="info-right">
          <span id="miningState" class="state-chip">採礦：待載入</span>
          <span id="craftingState" class="state-chip">圖紙：待載入</span>
        </div>
      </div>

      <section class="search-block">
        <div class="search-row">
          <input id="queryInput" type="search" inputmode="search" autocomplete="off" placeholder="搜尋礦物、地點、設施、圖紙…">
          <button id="clearBtn" class="search-clear" type="button">清</button>
        </div>
        <div id="suggestWrap" class="suggest-frame hidden" aria-live="polite">
          <div class="suggest-head">聯想</div>
          <div id="suggestions" class="suggest-list"></div>
        </div>
      </section>

      <div class="hint-row">上方聯想先顯示礦物 / 圖紙 / 設施 / 地點；選擇後左邊列出關聯區域，右邊顯示地圖 / 礦點資訊。</div>

      <div class="main-stage">
        <aside class="panel left-panel">
          <div class="panel-head">
            <div>
              <div class="panel-title">關聯區域</div>
              <div id="resultMeta" class="panel-subtitle">目前沒有結果</div>
            </div>
            <div id="relatedCount" class="count-pill">0</div>
          </div>
          <div class="panel-scroll left-scroll">
            <div id="modeBar" class="mode-bar" role="tablist" aria-label="搜尋類型">
              <button class="mode-chip active" type="button" data-mode="all">全部</button>
              <button class="mode-chip" type="button" data-mode="resource">礦物</button>
              <button class="mode-chip" type="button" data-mode="body">地點</button>
              <button class="mode-chip" type="button" data-mode="facility">設施</button>
              <button class="mode-chip" type="button" data-mode="item">圖紙</button>
            </div>
            <div id="relatedAccordion" class="result-frame">
              <div id="results" class="result-list"></div>
            </div>
          </div>
        </aside>

        <section class="panel right-panel detail-panel">
          <div class="panel-head">
            <div>
              <div id="detailTitle" class="panel-title">地圖 / 礦點資訊</div>
              <div id="detailMeta" class="panel-subtitle">請先從上方聯想選擇正確目標</div>
            </div>
          </div>
          <div class="panel-scroll right-scroll">
            <div id="riskBanner" class="risk-banner hidden"></div>
            <div id="detailOverview" class="detail-overview hidden"></div>
            <div id="detailSections" class="detail-sections"></div>
          </div>
        </section>
      </div>
    </div>

    <footer class="status-row">
      <div id="statusBar" class="status-bar">正在載入資料…</div>
    </footer>
  </div>

  <script src="assets/app.js?v=appstyle2b"></script>
</body>
</html>
