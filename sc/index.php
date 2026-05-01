<?php ?><!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>SC 資料探索站</title>
  <link rel="stylesheet" href="assets/styles.css?v=redesign-20260501">
</head>
<body>
  <div class="bg-orb orb-a"></div><div class="bg-orb orb-b"></div>
  <div class="layout">
    <header class="topbar glass">
      <div>
        <p class="eyebrow">Star Citizen 工具</p>
        <h1>SC 資料探索站</h1>
      </div>
      <div class="top-actions">
        <button id="refreshBtn" class="btn primary" type="button">重新同步</button>
      </div>
    </header>

    <section class="control glass">
      <div class="tab-row" id="tabRow">
        <button class="tab active" data-tab="all" type="button">全部</button>
        <button class="tab" data-tab="resource" type="button">礦物</button>
        <button class="tab" data-tab="body" type="button">星體</button>
        <button class="tab" data-tab="facility" type="button">設施</button>
        <button class="tab" data-tab="item" type="button">製作</button>
      </div>
      <div class="search-row">
        <input id="queryInput" type="search" placeholder="輸入關鍵字：礦物、地點、設施、物品...">
        <button id="clearBtn" class="btn" type="button">清除</button>
      </div>
      <p id="statusBar" class="status">載入中...</p>
    </section>

    <main class="grid">
      <section class="panel glass">
        <div class="panel-head">
          <h2>搜尋結果</h2><span id="resultCount" class="pill">0</span>
        </div>
        <div id="resultList" class="result-list"></div>
      </section>
      <section class="panel glass">
        <div class="panel-head"><h2 id="detailTitle">詳細資料</h2></div>
        <div id="detailView" class="detail">請先選擇一筆結果。</div>
      </section>
    </main>
  </div>
  <script src="assets/app.js?v=redesign-20260501"></script>
</body>
</html>
