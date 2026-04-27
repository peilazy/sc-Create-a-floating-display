from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import urllib.request
import urllib.error
import tempfile
import shutil
from urllib.parse import urlparse, parse_qs
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

try:
    from PIL import Image, ImageTk
except Exception:
    Image = None
    ImageTk = None

from core.data_store import MiningDataStore
from core.search import MiningSearch

def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = get_base_dir()
ASSETS_DIR = BASE_DIR / "assets"
ICON_PATH = ASSETS_DIR / "sc_mining_overlay.ico"
SETTINGS_PATH = BASE_DIR / "config" / "overlay_settings.json"
DATA_PATH = BASE_DIR / "data" / "sc_mining_dataset_latest.json"
SCC_PATH = BASE_DIR / "data" / "sccrafter_index.json"
REMOTE_DATA_URL = "https://drive.google.com/uc?export=download&id=1t9L3RSl1gPQRrsltH58uBySzC4_pxWjt"
REMOTE_SCC_URL = "https://drive.google.com/uc?export=download&id=1-nxq45uudEsGzV7IZxddUOeOT0m4b6hx"
LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "overlay.log"

DEFAULT_SETTINGS = {
    "x": 24, "y": 180, "width": 940, "height": 700, "alpha": 0.95, "font_scale": 1.0,
    "topmost": True, "collapsed": False, "toolbar_side": "right", "last_query": "",
    "safe_mode": False, "recent_queries": [], "collapsed_edge": "left",
}


def setup_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("sc_mining_overlay")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=512_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger


LOGGER = setup_logger()


def apply_window_icon(window: tk.Misc) -> None:
    try:
        if ICON_PATH.exists():
            window.iconbitmap(default=str(ICON_PATH))
    except Exception:
        LOGGER.exception("載入視窗圖示失敗")


def _extract_drive_file_id(url: str) -> str | None:
    try:
        qs = parse_qs(urlparse(url).query)
        vals = qs.get("id") or []
        return vals[0] if vals else None
    except Exception:
        return None


def _fetch_url_text(url: str, timeout: int = 15) -> tuple[str | None, str | None]:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
        text = raw.decode("utf-8", errors="ignore").lstrip("﻿")
        if text.lstrip().startswith("{") or text.lstrip().startswith("["):
            return text, None
        # google drive sometimes returns confirm/virus html page
        return None, "遠端回應不是 JSON，請確認 Google Drive 連結為公開直鏈"
    except Exception as exc:
        return None, str(exc)


def _load_remote_json(url: str) -> tuple[dict | None, str | None]:
    text, err = _fetch_url_text(url)
    if err:
        return None, err
    try:
        return json.loads(text or "{}"), None
    except Exception as exc:
        return None, f"JSON 解析失敗：{exc}"


def _read_json_file(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def _detect_json_version(payload: dict, path: Path | None = None) -> str:
    meta = payload.get("meta") if isinstance(payload, dict) else None
    if isinstance(meta, dict):
        for key in ("version", "dataset_version", "data_version", "updated_at", "last_updated"):
            val = meta.get(key)
            if val:
                return str(val)
    for key in ("version", "dataset_version", "data_version", "updated_at", "last_updated"):
        val = payload.get(key) if isinstance(payload, dict) else None
        if val:
            return str(val)
    return "未標註"


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.stem + "_", suffix=".tmp", dir=str(path.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")
        if path.exists():
            backup = path.with_suffix(path.suffix + ".bak")
            shutil.copy2(path, backup)
        os.replace(tmp_path, path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


class OverlayApp(tk.Tk):

    MIN_W = 640
    MIN_H = 440
    TOOLBAR_W = 96
    TOOLBAR_EXPANDED_H = 640
    TOOLBAR_COLLAPSED_H = 132
    RESIZE_SIZE = 24

    def __init__(self, safe_mode: bool = False) -> None:
        super().__init__()
        self.logger = LOGGER
        self.withdraw()
        self.settings = self._load_settings()
        if safe_mode:
            self.settings["safe_mode"] = True
        self.safe_mode = bool(self.settings.get("safe_mode", False))
        self._drag_start = None
        self._resize_start = None
        self._save_job = None
        self._query_job = None
        self._suppress_query = False
        self._result_rows = []
        self._suggestions = []
        self._ignore_toolbar_config = False
        self._selected_suggestion = None
        self._selected_resource = None
        self._selected_item = None
        self._selected_facility = None
        self._hangar_timer_job = None
        self._hangar_timer_fetch_job = None
        self._hangar_timer_thread = None
        self._hangar_timer_active = False
        self._hangar_timer_state = None
        self._hangar_timer_source = None
        self._hangar_timer_fetch_started = 0.0
        self._hangar_timer_anchor = time.time()
        self._selected_facility = None
        self._preview_original_image = None
        self._preview_render_image = None
        self._preview_zoom = 1.0
        self._preview_target_zoom = None
        self._preview_zoom_job = None
        self._preview_quality_job = None
        self._preview_interactive_resample = True
        self._preview_pan_x = 0
        self._preview_pan_y = 0
        self._preview_drag_last = None
        self._preview_user_changed = False
        self._preview_fit_locked = False
        self._preview_full_mode = False
        self._preview_paths = []
        self._preview_index = 0
        self._preview_cache_zoom = None
        self._preview_cache_path = None
        self._preview_item_id = None
        self._hangar_banner_blink_state = False
        self._hangar_last_light_green_blink = False

        self.title("SC Mining Overlay")
        apply_window_icon(self)
        if not self.safe_mode:
            self.overrideredirect(True)
        self.configure(bg="#0a1016")
        self.attributes("-topmost", bool(self.settings.get("topmost", True)))

        self.ui_font_name = self._pick_font()
        self.body_font = tkfont.Font(family=self.ui_font_name, size=11)
        self.small_font = tkfont.Font(family=self.ui_font_name, size=9)
        self.title_font = tkfont.Font(family=self.ui_font_name, size=12, weight="bold")
        self.button_font = tkfont.Font(family=self.ui_font_name, size=9)
        self.hud_font = tkfont.Font(family=self.ui_font_name, size=10, weight="bold")

        self.store = MiningDataStore(DATA_PATH)
        self.search = MiningSearch(self.store)
        self.meta = self.store.get_meta()
        self._update_dialog = None
        self._update_progress_var = tk.StringVar(value="")
        self._update_message_var = tk.StringVar(value="")
        self._pending_updates = []
        self._current_update_index = 0

        self.toolbar_window = tk.Toplevel(self)
        self.toolbar_window.withdraw()
        self.toolbar_window.title("SC Mining Toolbar")
        apply_window_icon(self.toolbar_window)
        if not self.safe_mode:
            self.toolbar_window.overrideredirect(True)
        self.toolbar_window.configure(bg="#0e1822")
        self.toolbar_window.attributes("-topmost", bool(self.settings.get("topmost", True)))

        self._build_ui()
        self._build_toolbar_window()
        self._apply_geometry()
        self._apply_visuals()
        self._apply_collapsed(initial=True)

        self.bind("<Configure>", self._on_main_configure)
        self.toolbar_window.bind("<Configure>", self._on_toolbar_configure)
        self.bind("<Escape>", lambda e: self._on_close())
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.toolbar_window.protocol("WM_DELETE_WINDOW", self._on_close)

        self.after(100, self._finish_startup)
        self.after(1400, self._check_remote_json_updates_background)

    def _check_remote_json_updates_background(self) -> None:
        def worker():
            updates = self._gather_json_updates()
            def done():
                if updates:
                    self._show_update_prompt(updates)
            try:
                self.after(0, done)
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def _gather_json_updates(self) -> list[dict]:
        targets = [
            {"label": "採礦資料", "path": DATA_PATH, "url": REMOTE_DATA_URL},
            {"label": "製作索引", "path": SCC_PATH, "url": REMOTE_SCC_URL},
        ]
        updates = []
        for target in targets:
            local_payload = _read_json_file(target["path"]) if target["path"].exists() else {}
            local_version = _detect_json_version(local_payload, target["path"])
            remote_payload, err = _load_remote_json(target["url"])
            if err or not isinstance(remote_payload, dict) or not remote_payload:
                self.logger.warning("update check failed for %s: %s", target["label"], err)
                continue
            remote_version = _detect_json_version(remote_payload)
            if str(remote_version).strip() != str(local_version).strip():
                updates.append({
                    "label": target["label"],
                    "path": target["path"],
                    "url": target["url"],
                    "local_version": local_version,
                    "remote_version": remote_version,
                    "remote_payload": remote_payload,
                })
        return updates

    def _show_update_prompt(self, updates: list[dict]) -> None:
        if self._update_dialog is not None:
            try:
                self._update_dialog.lift()
                self._update_dialog.focus_force()
            except Exception:
                pass
            return
        self._pending_updates = updates
        win = tk.Toplevel(self)
        self._update_dialog = win
        win.title("發現新資料版本")
        apply_window_icon(win)
        win.configure(bg="#0f1b25")
        win.attributes("-topmost", True)
        win.resizable(False, False)
        msg_lines = ["檢測到新版本資料，是否更新？", ""]
        for item in updates:
            msg_lines.append(f"{item['label']}：{item['local_version']} → {item['remote_version']}")
        self._update_message_var.set("\n".join(msg_lines))
        self._update_progress_var.set("")
        frame = tk.Frame(win, bg="#0f1b25", padx=14, pady=12)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, textvariable=self._update_message_var, justify="left", anchor="w", bg="#0f1b25", fg="#e6fbff", font=self.body_font).pack(fill="x")
        self._update_progress_label = tk.Label(frame, textvariable=self._update_progress_var, justify="left", anchor="w", bg="#0f1b25", fg="#8ed8ff", font=self.small_font)
        self._update_progress_label.pack(fill="x", pady=(10, 0))
        btns = tk.Frame(frame, bg="#0f1b25")
        btns.pack(fill="x", pady=(12, 0))
        yes = self._mk_btn(btns, "更新", self._confirm_do_updates, width=8)
        yes.pack(side="left")
        no = self._mk_btn(btns, "略過", self._close_update_dialog, width=8)
        no.pack(side="left", padx=(8, 0))
        self._update_yes_btn = yes
        self._update_no_btn = no
        win.protocol("WM_DELETE_WINDOW", self._close_update_dialog)
        try:
            win.transient(self)
            win.grab_set()
        except Exception:
            pass
        win.update_idletasks()
        x = self.winfo_x() + max(20, (self.winfo_width() - win.winfo_width()) // 2)
        y = self.winfo_y() + max(20, (self.winfo_height() - win.winfo_height()) // 2)
        win.geometry(f"+{x}+{y}")
        try:
            win.focus_force()
        except Exception:
            pass

    def _close_update_dialog(self) -> None:
        win = self._update_dialog
        self._update_dialog = None
        self._pending_updates = []
        try:
            if win is not None:
                try:
                    win.grab_release()
                except Exception:
                    pass
                win.destroy()
        except Exception:
            pass

    def _confirm_do_updates(self) -> None:
        if not self._pending_updates:
            self._close_update_dialog()
            return
        try:
            self._update_yes_btn.configure(state="disabled")
            self._update_no_btn.configure(state="disabled")
        except Exception:
            pass
        threading.Thread(target=self._perform_updates_thread, daemon=True).start()

    def _perform_updates_thread(self) -> None:
        total = len(self._pending_updates)
        done_count = 0
        errors = []

        def post_progress(text: str):
            try:
                self.after(0, lambda: self._update_progress_var.set(text))
            except Exception:
                pass

        for idx, item in enumerate(list(self._pending_updates), start=1):
            label = item["label"]
            post_progress(f"{label}：準備更新 {done_count}/{total}（{int(done_count/total*100) if total else 0}%）")
            payload = item.get("remote_payload")
            if not isinstance(payload, dict) or not payload:
                payload, err = _load_remote_json(item["url"])
                if err or not isinstance(payload, dict) or not payload:
                    errors.append(f"{label}：{err or '下載失敗'}")
                    continue
            # fake smoother progress checkpoints
            post_progress(f"{label}：下載完成，寫入中…（{int(((idx-1)+0.45)/total*100)}%）")
            try:
                _atomic_write_json(item["path"], payload)
                done_count += 1
                post_progress(f"{label}：更新完成（{int(done_count/total*100)}%）")
            except Exception as exc:
                errors.append(f"{label}：寫入失敗：{exc}")

        def finish():
            self._reload_data_files()
            if errors:
                self._update_message_var.set("更新完成，但有部分失敗：\n\n" + "\n".join(errors))
                self._update_progress_var.set(f"完成 {done_count}/{total}（{int(done_count/total*100) if total else 0}%）")
                try:
                    self._update_no_btn.configure(text="關閉", state="normal")
                except Exception:
                    pass
                return
            self._close_update_dialog()
            try:
                messagebox.showinfo("資料更新完成", f"已更新 {done_count} 個資料檔，並已熱重載。")
            except Exception:
                pass

        try:
            self.after(0, finish)
        except Exception:
            pass

    def _reload_data_files(self) -> None:
        try:
            self.store = MiningDataStore(DATA_PATH)
            self.search = MiningSearch(self.store)
            self.meta = self.store.get_meta()
            dataset_name = self.meta.get("dataset_name", "Mining Dataset")
            version = self.meta.get("version", self.meta.get("dataset_version", "-"))
            try:
                self.info_row.winfo_children()[0].configure(text=f"資料：{dataset_name} {version}")
            except Exception:
                pass
            self.status_var.set("資料已更新並重新載入")
            self._refresh_results(immediate=True)
        except Exception as exc:
            self.logger.exception("reload data failed: %s", exc)
            self.status_var.set("資料已下載，但重新載入失敗")

    def _load_settings(self) -> dict:
        if SETTINGS_PATH.exists():
            try:
                data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
                merged = dict(DEFAULT_SETTINGS)
                merged.update(data)
                return merged
            except Exception:
                LOGGER.exception("讀取設定失敗")
        return dict(DEFAULT_SETTINGS)

    def _save_settings(self) -> None:
        self._save_job = None
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not self.settings.get("collapsed", False):
            self.settings["x"] = int(self.winfo_x())
            self.settings["y"] = int(self.winfo_y())
            self.settings["width"] = int(self.winfo_width())
            self.settings["height"] = int(self.winfo_height())
        SETTINGS_PATH.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2), encoding="utf-8-sig")

    def _schedule_save(self) -> None:
        if self._save_job is not None:
            self.after_cancel(self._save_job)
        self._save_job = self.after(180, self._save_settings)

    def _pick_font(self) -> str:
        try:
            fams = {name.lower(): name for name in tkfont.families(self)}
        except Exception:
            return "TkDefaultFont"
        for cand in ["Microsoft JhengHei UI", "Microsoft JhengHei", "微軟正黑體", "PingFang TC", "Noto Sans TC", "Noto Sans CJK TC", "Arial Unicode MS", "TkDefaultFont"]:
            if cand.lower() in fams:
                return fams[cand.lower()]
        return "TkDefaultFont"

    def _build_ui(self) -> None:
        self.outer = tk.Frame(self, bg="#0b131b", highlightthickness=1, highlightbackground="#3e708d")
        self.outer.pack(fill="both", expand=True)

        self.titlebar = tk.Frame(self.outer, bg="#10202c", height=38)
        self.titlebar.pack(fill="x", side="top")
        self.titlebar.pack_propagate(False)
        self.titlebar.bind("<ButtonPress-1>", self._start_drag)
        self.titlebar.bind("<B1-Motion>", self._on_drag)
        self.titlebar.bind("<ButtonRelease-1>", lambda e: self._schedule_save())
        tk.Frame(self.titlebar, bg="#7fd8ff", width=6).pack(side="left", fill="y")
        self.title_label = tk.Label(self.titlebar, text="SC 採礦 製作 設施 查詢系統 浮動視窗", bg="#10202c", fg="#d9f4ff", font=self.title_font)
        self.title_label.pack(side="left", padx=10)
        self.title_label.bind("<ButtonPress-1>", self._start_drag)
        self.title_label.bind("<B1-Motion>", self._on_drag)
        self.title_label.bind("<ButtonRelease-1>", lambda e: self._schedule_save())

        hr = tk.Frame(self.titlebar, bg="#10202c")
        hr.pack(side="right", padx=6)
        self.pin_btn = self._mk_btn(hr, "置頂", self._toggle_topmost, width=4)
        self.pin_btn.pack(side="left", padx=(0,4), pady=4)
        self.close_btn = self._mk_btn(hr, "關", self._on_close, width=3)
        self.close_btn.pack(side="left", pady=4)

        self.content = tk.Frame(self.outer, bg="#0b131b")
        self.content.pack(fill="both", expand=True)

        self.info_row = tk.Frame(self.content, bg="#0b131b")
        self.info_row.pack(fill="x", padx=12, pady=(8, 2))
        dataset_name = self.meta.get("dataset_name", "Mining Dataset")
        version = self.meta.get("version", "-")
        tk.Label(self.info_row, text=f"資料：{dataset_name} {version}", bg="#0b131b", fg="#85a8bb", font=self.small_font).pack(side="left")
        self.alpha_label_top = tk.Label(self.info_row, text="", bg="#0b131b", fg="#85a8bb", font=self.small_font)
        self.alpha_label_top.pack(side="right")

        self.search_row = tk.Frame(self.content, bg="#0b131b")
        self.search_row.pack(fill="x", padx=12, pady=(2, 0))
        self.query_var = tk.StringVar(value=self.settings.get("last_query", ""))
        self.query_var.trace_add("write", self._on_query_change)
        self.search_entry = tk.Entry(self.search_row, textvariable=self.query_var, font=self.body_font,
                                     bg="#081118", fg="#e6fbff", insertbackground="#9fefff",
                                     relief="flat", bd=8, highlightthickness=1,
                                     highlightbackground="#2e5a72", highlightcolor="#7fd8ff")
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Down>", self._suggest_down)
        self.search_entry.bind("<Up>", self._suggest_up)
        self.search_entry.bind("<Return>", self._suggest_apply)
        self.search_entry.bind("<Escape>", lambda e: self._hide_suggestions())
        self._mk_btn(self.search_row, "清", self._clear_query, width=3).pack(side="left", padx=(6,0))

        self.suggest_frame = tk.Frame(self.content, bg="#10202c", highlightthickness=1, highlightbackground="#3e708d")
        self.suggest_list = tk.Listbox(self.suggest_frame, bg="#081118", fg="#e6fbff",
                                       selectbackground="#20455c", selectforeground="#ffffff",
                                       bd=0, relief="flat", highlightthickness=0, activestyle="none",
                                       font=self.body_font, exportselection=False, height=8)
        self.suggest_list.pack(fill="both", expand=True)
        self.suggest_list.bind("<ButtonRelease-1>", self._click_suggestion)
        self.suggest_list.bind("<Return>", self._suggest_enter)

        self.recent_label = tk.Label(self.content, text="上方聯想先顯示列表；點選後左邊列出關聯區域，右邊顯示地圖/礦點/設施資訊。",
                                     bg="#0b131b", fg="#85a8bb", font=self.small_font, anchor="w")
        self.recent_label.pack(fill="x", padx=12, pady=(6,8))

        self.main_area = tk.PanedWindow(self.content, orient="horizontal", sashwidth=6, bg="#0b131b", bd=0)
        self.main_area.pack(fill="both", expand=True, padx=12, pady=(0,10))
        self.left_panel = tk.Frame(self.main_area, bg="#0f1b25", highlightthickness=1, highlightbackground="#23465a")
        self.right_panel = tk.Frame(self.main_area, bg="#0f1b25", highlightthickness=1, highlightbackground="#23465a")
        self.main_area.add(self.left_panel, minsize=250)
        self.main_area.add(self.right_panel, minsize=360)

        tk.Label(self.left_panel, text="關聯區域", bg="#0f1b25", fg="#d9f4ff", font=self.title_font).pack(fill="x", padx=8, pady=(8,6))
        self.result_list = tk.Listbox(self.left_panel, bg="#081118", fg="#e6fbff",
                                      selectbackground="#20455c", selectforeground="white",
                                      bd=0, relief="flat", highlightthickness=1, highlightbackground="#2e5a72",
                                      font=self.body_font, activestyle="none", exportselection=False)
        self.result_list.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.result_list.bind("<<ListboxSelect>>", self._select_result)
        self.result_list.bind("<Double-Button-1>", lambda e: self._apply_result_selection())
        self.result_list.bind("<Return>", lambda e: self._apply_result_selection())

        self.right_title_label = tk.Label(self.right_panel, text="地圖 / 礦點 / 設施 資訊", bg="#0f1b25", fg="#d9f4ff", font=self.title_font)
        self.right_title_label.pack(fill="x", padx=8, pady=(8,6))
        self.timer_banner_frame = tk.Frame(self.right_panel, bg="#1b3242")
        self.timer_banner = tk.Label(
            self.timer_banner_frame,
            text="",
            bg="#1b3242",
            fg="#f4fbff",
            font=self.hud_font,
            anchor="w",
            padx=8,
            pady=5,
        )
        self.timer_banner.pack(side="left", padx=(0, 6))
        self.timer_banner_inline = tk.Frame(self.timer_banner_frame, bg="#1b3242")
        self.timer_banner_inline.pack(side="left", padx=(2, 6))
        self.timer_banner_lights = tk.Canvas(
            self.timer_banner_inline,
            width=0,
            height=18,
            bg="#1b3242",
            highlightthickness=0,
            bd=0,
        )
        self.timer_banner_lights.pack(side="left")
        self.timer_banner_tail = tk.Label(
            self.timer_banner_inline,
            text="",
            bg="#1b3242",
            fg="#f4fbff",
            font=self.hud_font,
            anchor="w",
            padx=0,
            pady=5,
        )
        self.timer_banner_tail.pack(side="left", padx=(4, 0))
        self.timer_banner_spacer = tk.Frame(self.timer_banner_frame, bg="#1b3242")
        self.timer_banner_spacer.pack(side="left", fill="x", expand=True)
        self._timer_banner_state = {"bg": "#1b3242", "fg": "#f4fbff", "text": "", "tail": "", "lights": []}
        self.risk_banner = tk.Label(self.right_panel, text="風險：待判定", bg="#23465a", fg="#e6fbff", font=self.hud_font, anchor="w", padx=8, pady=4)
        self.risk_banner.pack(fill="x", padx=8, pady=(0,6))
        self.right_split = tk.PanedWindow(self.right_panel, orient="vertical", sashwidth=8, bg="#0f1b25", bd=0, relief="flat")
        self.right_split.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.right_split.bind("<ButtonRelease-1>", self._remember_preview_sash)

        self.detail_holder = tk.Frame(self.right_split, bg="#0f1b25")
        self.detail = tk.Text(self.detail_holder, wrap="word", bg="#081118", fg="#e6fbff",
                              bd=0, relief="flat", highlightthickness=1, highlightbackground="#2e5a72",
                              font=self.body_font, padx=8, pady=8)
        self.detail.pack(fill="both", expand=True)

        self.preview_frame = tk.Frame(self.right_split, bg="#0f1b25", highlightthickness=1, highlightbackground="#2e5a72", height=320)
        self.preview_title = tk.Label(self.preview_frame, text="設施圖解（上一張／下一張／滾輪縮放／左鍵拖曳／圖片雙擊重置大小）", bg="#10202c", fg="#d9f4ff", font=self.small_font, anchor="w", padx=8, pady=4)
        self.preview_title.pack(fill="x")
        self.preview_btn_row = tk.Frame(self.preview_frame, bg="#0f1b25")
        self.preview_btn_row.pack(fill="x", padx=6, pady=(6,4))
        self.preview_prev_btn = self._mk_btn(self.preview_btn_row, "上一張", self._preview_prev_image, width=10)
        self.preview_prev_btn.pack(side="left", padx=(0,6))
        self.preview_next_btn = self._mk_btn(self.preview_btn_row, "下一張", self._preview_next_image, width=10)
        self.preview_next_btn.pack(side="left", padx=(0,6))
        self.preview_page_label = tk.Label(self.preview_btn_row, text="0 / 0", bg="#0f1b25", fg="#d9f4ff", font=self.small_font, width=8, anchor="center")
        self.preview_page_label.pack(side="left", padx=(0,10))
        self.preview_expand_btn = self._mk_btn(self.preview_btn_row, "填滿整頁", self._expand_preview_section, width=12)
        self.preview_expand_btn.pack(side="left", padx=(0,6))
        self.preview_restore_btn = self._mk_btn(self.preview_btn_row, "恢復大小", self._restore_preview_section, width=12)
        self.preview_restore_btn.pack(side="left")
        self.preview_restore_btn.configure(state="disabled")
        self.preview_canvas = tk.Canvas(self.preview_frame, bg="#081118", highlightthickness=0, bd=0, height=260, cursor="fleur")
        self.preview_canvas.pack(fill="both", expand=True)
        self.preview_path_label = tk.Label(self.preview_frame, text="", bg="#10202c", fg="#85a8bb", font=self.small_font, anchor="w", padx=8, pady=4)
        self.preview_path_label.pack(fill="x")

        self.right_split.add(self.detail_holder, minsize=40)
        try:
            self.right_split.sash_place(0, 0, 420)
        except Exception:
            pass
        self.preview_canvas.bind("<Configure>", self._on_preview_configure)
        self.preview_canvas.bind("<ButtonPress-1>", self._on_preview_press)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self._on_preview_release)
        self.preview_canvas.bind("<Double-Button-1>", self._reset_preview_view)
        self.preview_canvas.bind("<MouseWheel>", self._on_preview_wheel)
        self.preview_canvas.bind("<Button-4>", lambda e: self._on_preview_wheel(e, 120))
        self.preview_canvas.bind("<Button-5>", lambda e: self._on_preview_wheel(e, -120))
        self.preview_hidden = True
        self._preview_expanded = False
        self._preview_fit_locked = False
        self._preview_full_mode = False
        self._preview_paths = []
        self._preview_index = 0
        self._preview_cache_zoom = None
        self._preview_cache_path = None
        self._preview_item_id = None
        self.detail.tag_configure(
            "item_title",
            foreground="#D8F7A8",
            font=(self.ui_font_name, 16, "bold"),
            spacing1=4,
            spacing3=14,
        )
        self.detail.tag_configure(
            "blueprint_name",
            foreground="#B9FF95",
            font=(self.ui_font_name, 15, "bold"),
            lmargin1=8,
            lmargin2=8,
            spacing1=14,
            spacing3=8,
        )
        self.detail.tag_configure(
            "blueprint_meta",
            foreground="#B7D7E7",
            font=(self.ui_font_name, 11, "bold"),
            lmargin1=24,
            lmargin2=24,
            spacing1=2,
            spacing3=2,
        )
        self.detail.tag_configure(
            "section_header",
            foreground="#8ED8FF",
            font=(self.ui_font_name, 12, "bold"),
            spacing1=12,
            spacing3=4,
        )
        self.detail.tag_configure(
            "material_line",
            foreground="#90E8FF",
            lmargin1=34,
            lmargin2=52,
            spacing1=2,
            spacing3=1,
        )
        self.detail.tag_configure(
            "mission_line",
            foreground="#FFD792",
            lmargin1=34,
            lmargin2=52,
            spacing1=2,
            spacing3=1,
        )
        self.detail.tag_configure(
            "resource_name",
            foreground="#C6FFAC",
            font=(self.ui_font_name, 11, "bold"),
        )
        self.detail.tag_configure(
            "subtle_label",
            foreground="#9CB8C8",
            font=(self.ui_font_name, 11, "bold"),
        )
        self.detail.configure(state="disabled")

        bottom = tk.Frame(self.content, bg="#0b131b")
        bottom.pack(fill="x", padx=12, pady=(0,8))
        self.status_var = tk.StringVar(value="啟動中")
        tk.Label(bottom, textvariable=self.status_var, bg="#0b131b", fg="#85a8bb", font=self.small_font).pack(side="left")
        self.size_label = tk.Label(bottom, text="", bg="#0b131b", fg="#85a8bb", font=self.small_font)
        self.size_label.pack(side="right")

        self.resize_grip = tk.Canvas(self.outer, width=self.RESIZE_SIZE, height=self.RESIZE_SIZE, bg="#0b131b", highlightthickness=0, cursor="size_nw_se")
        self._draw_resize_grip()
        self.resize_grip.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)
        self.resize_grip.bind("<ButtonPress-1>", self._start_resize)
        self.resize_grip.bind("<B1-Motion>", self._do_resize)
        self.resize_grip.bind("<ButtonRelease-1>", lambda e: self._end_resize())

    def _build_toolbar_window(self):
        self.toolbar_outer = tk.Frame(self.toolbar_window, bg="#0e1822", highlightthickness=1, highlightbackground="#3e708d")
        self.toolbar_outer.pack(fill="both", expand=True)
        self.toolbar_outer.bind("<ButtonPress-1>", self._start_toolbar_drag)
        self.toolbar_outer.bind("<B1-Motion>", self._on_toolbar_drag)
        self.toolbar_outer.bind("<ButtonRelease-1>", lambda e: self._schedule_save())
        self.toolbar_frame = tk.Frame(self.toolbar_outer, bg="#0e1822")
        self.toolbar_frame.pack(fill="both", expand=True)
        self.toolbar_frame.bind("<ButtonPress-1>", self._start_toolbar_drag)
        self.toolbar_frame.bind("<B1-Motion>", self._on_toolbar_drag)
        self.toolbar_frame.bind("<ButtonRelease-1>", lambda e: self._schedule_save())
        self.expand_btn = tk.Button(self.toolbar_frame, text="展\n開", command=self._toggle_collapse,
                                    bg="#214259", fg="#d9f4ff", activebackground="#2d5d7c", activeforeground="white",
                                    bd=0, relief="flat", font=tkfont.Font(family=self.ui_font_name, size=16, weight="bold"),
                                    padx=12, pady=16, cursor="fleur")
        self.expand_btn.bind("<ButtonPress-1>", self._start_toolbar_drag)
        self.expand_btn.bind("<B1-Motion>", self._on_toolbar_drag)
        self.expand_btn.bind("<ButtonRelease-1>", lambda e: self._schedule_save())
        self.toolbar_buttons_frame = tk.Frame(self.toolbar_frame, bg="#0e1822")
        self.toolbar_buttons_frame.pack(fill="both", expand=True)
        self._build_toolbar_buttons()

    def _mk_btn(self, parent, text, cmd, width=5):
        return tk.Button(parent, text=text, command=cmd, width=width,
                         bg="#173245", fg="#d9f4ff", activebackground="#26516d", activeforeground="white",
                         bd=0, relief="flat", font=self.button_font, padx=4, pady=3)

    def _build_toolbar_buttons(self):
        for child in self.toolbar_buttons_frame.winfo_children():
            child.destroy()
        buttons = [("縮", self._toggle_collapse), ("置", self._toggle_topmost),
                   ("透-", lambda: self._change_alpha(-0.05)), ("透+", lambda: self._change_alpha(0.05)),
                   ("字-", lambda: self._change_font(-0.05)), ("字+", lambda: self._change_font(0.05)),
                   ("窗-", lambda: self._scale_window(0.92)), ("窗+", lambda: self._scale_window(1.08)),
                   ("關", self._on_close)]
        for label, cmd in buttons:
            self._mk_btn(self.toolbar_buttons_frame, label, cmd, width=5).pack(fill="x", padx=10, pady=(10,0), ipady=2)

    def _apply_geometry(self):
        width = max(self.MIN_W, int(self.settings.get("width", DEFAULT_SETTINGS["width"])))
        height = max(self.MIN_H, int(self.settings.get("height", DEFAULT_SETTINGS["height"])))
        x = int(self.settings.get("x", DEFAULT_SETTINGS["x"]))
        y = int(self.settings.get("y", DEFAULT_SETTINGS["y"]))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _apply_visuals(self):
        scale = max(0.8, min(2.0, float(self.settings.get("font_scale", 1.0))))
        self.settings["font_scale"] = round(scale, 2)
        body_size = max(10, round(11 * scale))
        small_size = max(8, round(9 * scale))
        title_size = max(11, round(12 * scale))
        button_size = max(8, round(9 * scale))
        hud_size = max(9, round(10 * scale))
        self.body_font.configure(size=body_size)
        self.small_font.configure(size=small_size)
        self.title_font.configure(size=title_size)
        self.button_font.configure(size=button_size)
        if hasattr(self, "hud_font"):
            self.hud_font.configure(size=hud_size)
        if hasattr(self, "detail"):
            self.detail.configure(
                font=self.body_font,
                padx=max(10, round(12 * scale)),
                pady=max(10, round(10 * scale)),
                spacing1=max(1, round(2 * scale)),
                spacing2=max(2, round(3 * scale)),
                spacing3=max(2, round(3 * scale)),
            )
            self.detail.tag_configure("item_title", font=(self.ui_font_name, max(15, round(16 * scale)), "bold"), spacing3=max(10, round(14 * scale)))
            self.detail.tag_configure("blueprint_name", font=(self.ui_font_name, max(14, round(15 * scale)), "bold"), spacing1=max(10, round(14 * scale)), spacing3=max(6, round(8 * scale)))
            self.detail.tag_configure("blueprint_meta", font=(self.ui_font_name, max(10, round(11 * scale)), "bold"), lmargin1=max(22, round(24 * scale)), lmargin2=max(22, round(24 * scale)))
            self.detail.tag_configure("section_header", font=(self.ui_font_name, max(11, round(12 * scale)), "bold"), spacing1=max(8, round(12 * scale)), spacing3=max(3, round(4 * scale)))
            self.detail.tag_configure("material_line", lmargin1=max(28, round(34 * scale)), lmargin2=max(42, round(52 * scale)))
            self.detail.tag_configure("mission_line", lmargin1=max(28, round(34 * scale)), lmargin2=max(42, round(52 * scale)))
            self.detail.tag_configure("resource_name", font=(self.ui_font_name, max(10, round(11 * scale)), "bold"))
            self.detail.tag_configure("subtle_label", font=(self.ui_font_name, max(10, round(11 * scale)), "bold"))
        alpha = max(0.35, min(1.0, float(self.settings.get("alpha", 0.95))))
        self.settings["alpha"] = round(alpha, 2)
        self.attributes("-alpha", alpha)
        self.toolbar_window.attributes("-alpha", min(1.0, alpha))
        self.attributes("-topmost", bool(self.settings.get("topmost", True)))
        self.toolbar_window.attributes("-topmost", bool(self.settings.get("topmost", True)))
        self.alpha_label_top.configure(text=f"透明 {int(alpha*100)}%")
        self._build_toolbar_buttons()
        try:
            self.expand_btn.configure(font=tkfont.Font(family=self.ui_font_name, size=max(16, round(16 * scale)), weight="bold"))
        except Exception:
            pass
        self._refresh_size_label()

    def _finish_startup(self):
        if not self.settings.get("collapsed", False):
            self.deiconify()
        self.toolbar_window.deiconify()
        self.update_idletasks()
        self._sync_toolbar_position()
        if not self.settings.get("collapsed", False):
            self.lift()
        self.toolbar_window.lift()
        self.after(40, self._bring_focus)
        self._refresh_results(immediate=True)
        self.status_var.set("就緒")

    def _bring_focus(self):
        if not self.settings.get("collapsed", False):
            try:
                self.focus_force()
                self.search_entry.focus_set()
                self.search_entry.icursor(tk.END)
            except Exception:
                pass

    def _compute_toolbar_side(self):
        center = self.settings.get("x", self.winfo_x()) + (self.settings.get("width", self.winfo_width()) // 2)
        return "right" if center < self.winfo_screenwidth() // 2 else "left"

    def _sync_toolbar_position(self):
        self.update_idletasks()
        side = self._compute_toolbar_side()
        self.settings["toolbar_side"] = side
        x = int(self.settings.get("x", self.winfo_x()))
        y = int(self.settings.get("y", self.winfo_y()))
        width = int(self.settings.get("width", self.winfo_width()))
        if self.settings.get("collapsed", False):
            edge = self.settings.get("collapsed_edge", "left")
            tb_h = self.TOOLBAR_COLLAPSED_H
            tb_y = max(0, min(self.winfo_screenheight() - tb_h, y + 100))
            tb_x = self.winfo_screenwidth() - self.TOOLBAR_W if edge == "right" else 0
        else:
            tb_h = min(self.TOOLBAR_EXPANDED_H, max(260, self.winfo_height() - 50))
            tb_y = y + 42
            tb_x = x + width + 6 if side == "right" else x - self.TOOLBAR_W - 6
        self._ignore_toolbar_config = True
        self.toolbar_window.geometry(f"{self.TOOLBAR_W}x{tb_h}+{tb_x}+{tb_y}")
        self._ignore_toolbar_config = False

    def _apply_collapsed(self, initial=False):
        collapsed = bool(self.settings.get("collapsed", False))
        if collapsed:
            center = self.settings.get("x", 24) + self.settings.get("width", 900) // 2
            self.settings["collapsed_edge"] = "right" if center >= self.winfo_screenwidth() // 2 else "left"
            self.withdraw()
            self.toolbar_buttons_frame.pack_forget()
            self.expand_btn.pack(fill="both", expand=True, padx=8, pady=8)
        else:
            self.deiconify()
            self.expand_btn.pack_forget()
            self.toolbar_buttons_frame.pack(fill="both", expand=True)
            self._apply_geometry()
            self.resize_grip.place(relx=1.0, rely=1.0, anchor="se", x=-4, y=-4)
        self.toolbar_window.deiconify()
        self._sync_toolbar_position()
        self._build_toolbar_buttons()
        if not initial:
            self._schedule_save()

    def _toggle_collapse(self):
        self.settings["collapsed"] = not bool(self.settings.get("collapsed", False))
        self._apply_collapsed()
        if not self.settings["collapsed"]:
            self.after(30, self._bring_focus)

    def _toggle_topmost(self):
        self.settings["topmost"] = not bool(self.settings.get("topmost", True))
        top = bool(self.settings["topmost"])
        self.attributes("-topmost", top)
        self.toolbar_window.attributes("-topmost", top)
        self.status_var.set("已開啟置頂" if top else "已取消置頂")
        self._schedule_save()

    def _start_drag(self, event):
        self._drag_start = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _on_drag(self, event):
        if not self._drag_start:
            return
        x = max(0, event.x_root - self._drag_start[0])
        y = max(0, event.y_root - self._drag_start[1])
        self.geometry(f"+{x}+{y}")
        self.settings["x"] = x
        self.settings["y"] = y
        self._sync_toolbar_position()
        self._refresh_size_label()

    def _start_toolbar_drag(self, event):
        self._drag_start = (event.x_root - self.toolbar_window.winfo_x(), event.y_root - self.toolbar_window.winfo_y())

    def _on_toolbar_drag(self, event):
        if not self._drag_start:
            return
        tb_x = max(0, event.x_root - self._drag_start[0])
        tb_y = max(0, event.y_root - self._drag_start[1])

        if self.settings.get("collapsed", False):
            screen_w = self.winfo_screenwidth()
            edge = "right" if (tb_x + self.TOOLBAR_W // 2) >= screen_w // 2 else "left"
            self.settings["collapsed_edge"] = edge
            self.settings["x"] = 0 if edge == "left" else max(0, screen_w - int(self.settings.get("width", self.winfo_width())))
            self.settings["y"] = max(0, tb_y - 100)
        else:
            side = self.settings.get("toolbar_side") or self._compute_toolbar_side()
            if side == "right":
                x = max(0, tb_x - int(self.settings.get("width", self.winfo_width())) - 6)
            else:
                x = max(0, tb_x + self.TOOLBAR_W + 6)
            y = max(0, tb_y - 42)
            self.settings["x"] = x
            self.settings["y"] = y
            self.geometry(f"+{x}+{y}")

        self._sync_toolbar_position()
        self._schedule_save()

    def _start_resize(self, event):
        if self.settings.get("collapsed"):
            return
        self._resize_start = (event.x_root, event.y_root, self.winfo_width(), self.winfo_height(), self.winfo_x(), self.winfo_y())

    def _do_resize(self, event):
        if not self._resize_start or self.settings.get("collapsed"):
            return
        sx, sy, sw, sh, x, y = self._resize_start
        new_w = max(self.MIN_W, sw + (event.x_root - sx))
        new_h = max(self.MIN_H, sh + (event.y_root - sy))
        self.geometry(f"{int(new_w)}x{int(new_h)}+{x}+{y}")
        self.settings["width"] = int(new_w)
        self.settings["height"] = int(new_h)
        self._refresh_size_label()
        self._sync_toolbar_position()

    def _end_resize(self):
        self._resize_start = None
        self._schedule_save()

    def _draw_resize_grip(self):
        self.resize_grip.delete("all")
        c = "#7fd8ff"
        for i in range(3):
            o = 5 + i * 5
            self.resize_grip.create_line(o, self.RESIZE_SIZE - 2, self.RESIZE_SIZE - 2, o, fill=c, width=2)

    def _clear_query(self):
        self.query_var.set("")
        self._selected_suggestion = None
        self._selected_resource = None
        self.search_entry.focus_set()

    def _remember_query(self, text: str):
        t = (text or "").strip()
        if not t:
            return
        recent = list(self.settings.get("recent_queries", []))
        recent = [x for x in recent if x.strip().lower() != t.lower()]
        recent.insert(0, t)
        self.settings["recent_queries"] = recent[:20]
        self._schedule_save()

    def _on_query_change(self, *_):
        if self._suppress_query:
            return
        self.settings["last_query"] = self.query_var.get()
        self._selected_suggestion = None
        self._selected_resource = None
        self._selected_item = None
        self._selected_facility = None
        self._hangar_timer_job = None
        self._hangar_timer_fetch_job = None
        self._hangar_timer_thread = None
        self._hangar_timer_active = False
        self._hangar_timer_state = None
        self._hangar_timer_source = None
        self._hangar_timer_fetch_started = 0.0
        self._hangar_timer_anchor = time.time()
        self._refresh_results(immediate=False)

    def _refresh_results(self, immediate=False):
        if self._query_job is not None:
            self.after_cancel(self._query_job)
            self._query_job = None
        if immediate:
            self._run_search()
        else:
            self._query_job = self.after(70, self._run_search)


    def _is_executive_hangar_query(self, query: str) -> bool:
        q = (query or "").strip().lower()
        if not q:
            return False
        terms = {
            "行政機庫", "行政機庫任務", "機庫任務", "機庫",
            "executive hangars", "executive hangar", "exhang",
            "pyam-exhang", "pyam-exhang-0-1", "facility_executive_hangars",
        }
        q_norm = q.replace("_", "-")
        return q in {x.lower() for x in terms} or q_norm in {x.lower().replace("_", "-") for x in terms}

    def _get_executive_hangar_facilities(self):
        out = []
        seen = set()
        payload = getattr(self.store, "payload", {}) or {}
        for item in (payload.get("facility_guides") or []):
            name_en = str(item.get("name_en") or "").strip().lower()
            name_zh = str(item.get("name_zh_tw") or "").strip().lower()
            aliases = {str(x).strip().lower() for x in (item.get("aliases") or []) if str(x).strip()}
            item_id = str(item.get("id") or "").strip().lower()
            timer_mode = str(item.get("timer_mode") or "").strip().lower()
            body = str(item.get("body") or "").strip().lower()

            haystack = {name_en, name_zh, item_id, timer_mode, body} | aliases
            if (
                "executive hangar" in name_en
                or "executive hangars" in haystack
                or "executive hangar" in haystack
                or "行政機庫" in haystack
                or "行政機庫任務" in haystack
                or "機庫任務" in haystack
                or item_id == "facility_executive_hangars"
                or timer_mode == "executive_hangar_live"
                or body == "pyam-exhang-0-1"
                or "pyam-exhang" in haystack
                or "pyam-exhang-0-1" in haystack
                or "exhang" in haystack
            ):
                key = item_id or name_en or name_zh or body
                if key and key not in seen:
                    seen.add(key)
                    out.append(item)

        if out:
            return out

        # Fallback: ask the store search with multiple known names and merge results.
        probes = [
            "行政機庫", "行政機庫任務", "機庫任務",
            "Executive Hangars", "Executive Hangar",
            "EXHANG", "PYAM-EXHANG", "PYAM-EXHANG-0-1"
        ]
        for probe in probes:
            try:
                results = self.store.find_facility_candidates(probe, limit=8) or []
            except Exception:
                results = []
            for item in results:
                key = str(item.get("id") or item.get("name_en") or item.get("name_zh_tw") or "").strip().lower()
                if key and key not in seen:
                    seen.add(key)
                    out.append(item)
        return out

    def _run_search(self):
        query = self.query_var.get().strip()
        self._suggestions = self._build_suggestions(query)
        self._render_suggestions()

        if not query:
            self._result_rows = []
            self.result_list.delete(0, tk.END)
            self._selected_resource = None
            self._selected_item = None
            self._set_risk_banner(None)
            self._set_detail("請先從上方聯想選礦物、圖紙、設施或地點。")
            self.status_var.set("可從最近紀錄、礦物、圖紙、設施或地點聯想中選擇")
            return

        resource_candidates = self.store.find_resource_candidates(query, limit=10)
        item_candidates = self.store.find_item_candidates(query, limit=10)
        facility_limit = 32 if query in {"設施", "facility", "facilities"} else 12
        facility_candidates = self.store.find_facility_candidates(query, limit=facility_limit)

        if self._is_executive_hangar_query(query):
            forced_hangar = self._get_executive_hangar_facilities()
            if forced_hangar:
                facility_candidates = forced_hangar

        if self._selected_resource is not None:
            sel_names = {str(self._selected_resource.get("name_en","")).lower(), str(self._selected_resource.get("name_zh_tw","")).lower()}
            sel_names.update(str(a).lower() for a in (self._selected_resource.get("aliases") or []))
            if query.lower() in sel_names:
                self._show_resource_results(self._selected_resource)
                return

        if self._selected_item is not None:
            sel_names = {str(self._selected_item.get("name_en","")).lower(), str(self._selected_item.get("name_zh_tw","")).lower(), str(self._selected_item.get("name_zh","")).lower()}
            if query.lower() in sel_names:
                self._show_item_results(self._selected_item)
                return

        if self._selected_facility is not None:
            sel_names = {
                str(self._selected_facility.get("name_en","")).lower(),
                str(self._selected_facility.get("name_zh_tw","")).lower(),
            }
            sel_names.update(str(a).lower() for a in (self._selected_facility.get("aliases") or []))
            if query.lower() in sel_names:
                self._show_facility_results([self._selected_facility])
                return

        if self._is_executive_hangar_query(query) and facility_candidates:
            self._show_facility_results(facility_candidates)
            return

        if ("行政機庫" in query or "executive hangar" in query.lower() or "exhang" in query.lower()) and not facility_candidates:
            forced_hangar = self._get_executive_hangar_facilities()
            if forced_hangar:
                self._show_facility_results(forced_hangar)
                return

        if resource_candidates or item_candidates:
            self._result_rows = []
            self.result_list.delete(0, tk.END)
            self._set_risk_banner(None)
            self._set_detail("請先從上方聯想中選擇正確礦物、圖紙、設施或地點，之後才會顯示關聯資訊。")
            self.status_var.set(f"找到 {len(resource_candidates)} 個礦物候選、{len(item_candidates)} 個圖紙候選、{len(facility_candidates)} 個設施候選，請先選擇")
            return

        if facility_candidates:
            self._show_facility_results(facility_candidates)
            return

        rows = self.search.search(query, limit=24)
        self._result_rows = [{"kind":"body","body_id":row["id"],"title":row["name_zh"] or row["name_en"],"subtitle":row["system_zh"] or row["system"]} for row in rows]
        self._render_results()
        if self._result_rows:
            self._show_detail_for_result(self._result_rows[0])
            self.status_var.set(f"地點結果 {len(self._result_rows)} 筆")
        else:
            self._set_risk_banner(None)
            self._set_detail("查無對應地點")
            self.status_var.set("查無結果")

    def _build_suggestions(self, query: str):
        q = (query or "").strip()
        out = []
        seen = set()
        if not q:
            for item in self.settings.get("recent_queries", [])[:10]:
                if item and item not in seen:
                    seen.add(item)
                    out.append({"kind":"recent","display":item,"query":item})
            return out

        for item in self.store.find_resource_candidates(q, limit=8):
            display = self.store.bilingual_resource(item.get("name_en"), item.get("name_zh_tw"))
            meta = self.store.normalize_type(item.get("type") or "")
            key = ("resource", display)
            if key not in seen:
                seen.add(key)
                out.append({"kind":"resource","display":display,"query":item.get("name_zh_tw") or item.get("name_en") or display,"meta":meta,"resource_item":item})

        for item in self.store.find_item_candidates(q, limit=8):
            display = self.store.bilingual_blueprint(item.get("name_en"), item.get("name_zh_tw") or item.get("name_zh"))
            meta = item.get("category_zh_tw") or item.get("category_zh") or item.get("category_en") or "圖紙"
            key = ("item", display)
            if key not in seen:
                seen.add(key)
                out.append({"kind":"item","display":display,"query":item.get("name_zh_tw") or item.get("name_zh") or item.get("name_en") or display,"meta":meta,"scc_item":item})

        facility_items = self.store.find_facility_candidates(q, limit=8)
        if self._is_executive_hangar_query(q):
            forced_hangar = self._get_executive_hangar_facilities()
            if forced_hangar:
                facility_items = forced_hangar

        for item in facility_items:
            display = self.store.bilingual_facility(item.get("name_en"), item.get("name_zh_tw"))
            meta = item.get("facility_type") or "設施"
            key = ("facility", display)
            if key not in seen:
                seen.add(key)
                out.append({"kind":"facility","display":display,"query":item.get("name_zh_tw") or item.get("name_en") or display,"meta":meta,"facility_item":item})

        for item in self.search.suggest(q, recent=[], limit=12):
            if item.get("kind") != "body":
                continue
            key = ("body", item["display"], item.get("meta",""))
            if key not in seen:
                seen.add(key)
                out.append(item)
            if len(out) >= 12:
                break
        return out[:12]

    def _render_suggestions(self):
        self.suggest_list.delete(0, tk.END)
        if not self._suggestions:
            self._hide_suggestions()
            return
        for item in self._suggestions:
            prefix = "最近" if item["kind"] == "recent" else ("礦物" if item["kind"] == "resource" else ("圖紙" if item["kind"] == "item" else ("設施" if item["kind"] == "facility" else "地點")))
            meta = f'｜{item.get("meta","")}' if item.get("meta") else ""
            self.suggest_list.insert(tk.END, f"{prefix}｜{item['display']}{meta}")
        self._show_suggestions()
        self.suggest_list.selection_clear(0, tk.END)
        self.suggest_list.selection_set(0)
        self.suggest_list.activate(0)

    def _show_suggestions(self):
        if self.suggest_frame.winfo_manager():
            return
        self.suggest_frame.pack(fill="x", padx=12, pady=(4, 0), after=self.search_entry.master)

    def _hide_suggestions(self):
        if self.suggest_frame.winfo_manager():
            self.suggest_frame.pack_forget()

    def _suggest_down(self, _event):
        if not self._suggestions:
            return "break"
        cur = self.suggest_list.curselection()
        idx = cur[0] if cur else -1
        idx = min(len(self._suggestions)-1, idx+1)
        self.suggest_list.selection_clear(0, tk.END)
        self.suggest_list.selection_set(idx)
        self.suggest_list.activate(idx)
        self.suggest_list.see(idx)
        return "break"

    def _suggest_up(self, _event):
        if not self._suggestions:
            return "break"
        cur = self.suggest_list.curselection()
        idx = cur[0] if cur else 0
        idx = max(0, idx-1)
        self.suggest_list.selection_clear(0, tk.END)
        self.suggest_list.selection_set(idx)
        self.suggest_list.activate(idx)
        self.suggest_list.see(idx)
        return "break"

    def _suggest_apply(self, _event):
        if self._suggestions:
            cur = self.suggest_list.curselection()
            idx = cur[0] if cur else 0
            self._apply_suggestion(idx)
        elif self._result_rows:
            self._apply_result_selection()
        return "break"

    def _click_suggestion(self, _event):
        cur = self.suggest_list.curselection()
        if cur:
            self._apply_suggestion(cur[0])

    def _suggest_enter(self, _event):
        cur = self.suggest_list.curselection()
        if cur:
            self._apply_suggestion(cur[0])
        return "break"

    def _apply_suggestion(self, idx):
        if not (0 <= idx < len(self._suggestions)):
            return
        item = self._suggestions[idx]
        self._selected_suggestion = item
        self._selected_resource = item.get("resource_item")
        self._selected_item = item.get("scc_item")
        self._selected_facility = item.get("facility_item")
        self._suppress_query = True
        self.query_var.set(item["query"])
        self._suppress_query = False
        self._remember_query(item["query"])
        self._refresh_results(immediate=True)
        # 選到礦物後，自動顯示必須跟手動點左側清單完全一致
        if self._result_rows:
            self._show_detail_for_result(self._result_rows[0], resource_item=self._selected_resource)

    def _show_facility_results(self, items):
        rows = []
        for item in items:
            title = self.store.bilingual_facility(item.get("name_en"), item.get("name_zh_tw"))
            subtitle = item.get("facility_type") or item.get("classification") or "設施"
            rows.append({
                "kind": "facility",
                "title": title,
                "subtitle": subtitle,
                "facility_item": item,
            })
        self._result_rows = rows
        self._render_results()
        self.status_var.set(f"設施結果 {len(rows)} 筆")
        if rows:
            self._show_detail_for_result(rows[0])

    def _show_resource_results(self, resource_item):
        rows = self.store.resource_locations(resource_item)
        self._result_rows = rows
        self._render_results()
        self.status_var.set(f'礦物【{resource_item.get("name_zh_tw") or resource_item.get("name_en")}】關聯區域 {len(rows)} 筆')
        if rows:
            first = rows[0]
            if first.get("body_id"):
                self._show_body_detail(first["body_id"], resource_item=resource_item)
            else:
                self._show_detail_for_result(first, resource_item=resource_item)
        else:
            self._set_risk_banner(None)
            self._set_detail(self.store.resource_summary_text(resource_item) + "\n\n目前資料尚未綁定具體區域。")

    def _show_item_results(self, item):
        title = self.store.bilingual_blueprint(item.get("name_en"), item.get("name_zh_tw") or item.get("name_zh"))
        subtitle = item.get("category_zh_tw") or item.get("category_zh") or item.get("category_en") or "圖紙"
        self._result_rows = [{
            "kind": "scc_item",
            "title": title,
            "subtitle": subtitle,
            "scc_item": item,
        }]
        self._render_results()
        self.status_var.set(f'圖紙【{item.get("name_zh_tw") or item.get("name_zh") or item.get("name_en")}】｜材料 {len(item.get("materials", []))} 項｜任務 {int(item.get("mission_count") or 0)} 筆')
        self._set_risk_banner(None)
        self._set_detail(self.store.scc_item_detail_text(item))

    def _render_results(self):
        self.result_list.delete(0, tk.END)
        for row in self._result_rows:
            title = row.get("title","-")
            sub = row.get("subtitle","")
            self.result_list.insert(tk.END, f"{title}  [{sub}]")
        if self._result_rows:
            self.result_list.selection_clear(0, tk.END)
            self.result_list.selection_set(0)
            self.result_list.activate(0)

    def _select_result(self, _event):
        cur = self.result_list.curselection()
        if cur:
            idx = cur[0]
            if 0 <= idx < len(self._result_rows):
                self._show_detail_for_result(self._result_rows[idx], resource_item=self._selected_resource)

    def _apply_result_selection(self):
        cur = self.result_list.curselection()
        if cur:
            idx = cur[0]
            if 0 <= idx < len(self._result_rows):
                self._show_detail_for_result(self._result_rows[idx], resource_item=self._selected_resource)

    def _show_detail_for_result(self, row, resource_item=None):
        self._set_preview_image(None)
        self._clear_hangar_timer()
        # 搜尋圖紙時，只顯示該圖紙本身，不再把材料拆成左側結果清單
        if row.get("kind") == "facility":
            self._show_facility_detail(row.get("facility_item") or {})
        elif row.get("kind") == "scc_item":
            self._set_risk_banner(None)
            self._set_detail(self.store.scc_item_detail_text(row.get("scc_item") or {}))
        elif row.get("kind") == "item_material":
            res = row.get("resource_item")
            if res:
                self._selected_resource = res
                self._show_resource_results(res)
            else:
                self._set_risk_banner(None)
                title = row.get("title", "-")
                self._set_detail(f"【{title}】\n\n目前沒有已驗證採集地點資料。")
        elif row.get("body_id"):
            self._show_body_detail(row["body_id"], resource_item)
        elif row.get("kind") == "body":
            self._show_body_detail(row["body_id"], resource_item)
        else:
            self._show_location_detail(row, resource_item)

    def _show_body_detail(self, body_id, resource_item=None):
        body = self.store.get_body(body_id)
        if not body:
            self._set_detail("找不到資料")
            return
        mining = body.get("mining", {})
        travel = body.get("travel", {})
        lines = []
        blueprint_text = ""
        if resource_item:
            head, blueprint_text = self.store.resource_summary_parts(resource_item, include_positions=False)
            lines.append(head)
            lines.append("")
            lines.append("—— 關聯地點 ——")
        lines.append(f'【{self.store.bilingual_body(body["name_en"], body["name_zh"])}】')
        lines.append(f'系統：{self.store.bilingual_body(body["system"], body["system_zh"])}')
        lines.append(f'類型：{self._map_body_type(body.get("type", "-"))}')
        parent = body.get("parent")
        lines.append(f'母星：{self.store.bilingual_body(parent, self.store.get_body_zh(parent)) if parent else "-"}')
        lines.append("")
        lines.append(f'高品質：{self._bool_text(mining.get("high_quality_possible"))}')
        lines.append(f'信心：{self._map_level(mining.get("high_quality_confidence"))}')
        reasons = mining.get("high_quality_reasons", [])
        if reasons:
            lines.append("判斷理由：")
            for r in reasons[:4]:
                lines.append(f"- {self.store.bilingualize_known_text(r)}")
        lines.append(f'需要下礦坑：{self._map_cave(mining.get("need_cave_for_best_tier"))}')
        lines.append(f'採集方式：{self._format_modes(mining.get("recommended_modes", []))}')
        lines.append(f'熱點程度：{self._map_level(mining.get("hotspot_level"))}')
        lines.append(f'可達性：{self._map_level(mining.get("accessibility"))}')
        lines.append("")
        lines.append("到達方式")
        lines.append(f'快速路線：{self.store.bilingualize_known_text(travel.get("quick_route", "-"))}')
        hubs = travel.get("recommended_hubs", [])
        if hubs:
            lines.append("建議出發：" + "、".join(self.store.bilingual_location_name(self.store.bilingual_body(x, self.store.get_body_zh(x))) for x in hubs))
        if travel.get("special_access"):
            lines.append("特殊接近：" + self.store.bilingualize_known_text(travel["special_access"]))
        locs = body.get("locations", [])
        if locs:
            lines.append("常見點位：")
            for loc in locs[:12]:
                lines.append(f"- {self.store.bilingualize_known_text(self.store.bilingual_location_name(loc))}")
        lines.append("")
        lines.append("資源概況")
        lines.append("")
        lines.append("【地表】")
        lines.append(self._fmt_resource_list(mining.get("known_surface_resources", [])))
        lines.append("")
        lines.append("【洞穴】")
        lines.append(self._fmt_resource_list(mining.get("known_cave_resources", [])))
        lines.append("")
        lines.append("【太空／小行星】")
        lines.append(self._fmt_resource_list(mining.get("known_asteroid_resources", [])))
        if blueprint_text:
            lines.append("")
            lines.append("—— 製作圖紙 ——")
            lines.append(blueprint_text)
        self._set_risk_banner(body)
        self._set_detail("\n".join(lines))

    def _show_location_detail(self, row, resource_item=None):
        lines = []
        blueprint_text = ""
        if resource_item:
            head, blueprint_text = self.store.resource_summary_parts(resource_item, include_positions=False)
            lines.append(head)
            lines.append("")
            lines.append("—— 關聯地點 ——")
        if row.get("kind") == "generic_asteroid_profile" and row.get("details"):
            lines.append(self.store.bilingualize_known_text(row.get("details")))
            if blueprint_text:
                lines.append("")
                lines.append("—— 製作圖紙 ——")
                lines.append(blueprint_text)
            self._set_risk_banner(None)
            self._set_detail("\n".join(lines))
            return
        title = row.get("title","-")
        subtitle = row.get("subtitle","-")
        if self.store.is_generic_asteroid_field(title):
            title = self.store.bilingual_location_name(title)
            subtitle = self.store.bilingual_location_name(subtitle)
        lines.append(f'【{title}】')
        lines.append(f'所屬：{subtitle}')
        mode = row.get("mode")
        if mode:
            lines.append(f'採集模式：{self.store.normalize_mode(mode)}')
        details = row.get("details")
        if details:
            lines.append("")
            lines.append("關聯摘要：")
            lines.append(self.store.bilingualize_known_text(details))
        elif self.store.is_generic_asteroid_field(row.get("title")):
            lines.append("")
            lines.append("說明：")
            lines.append("此項目是小行星成分類型，不是固定地點。")
        if blueprint_text:
            lines.append("")
            lines.append("—— 製作圖紙 ——")
            lines.append(blueprint_text)
        body = self.store.get_body(row.get("body_id")) if row.get("body_id") else None
        self._set_risk_banner(body)
        self._set_detail("\n".join(lines))


    def _peak_info(self):
        from datetime import datetime
        hour = datetime.now().hour
        if 8 <= hour < 15:
            return ("尖峰時段", "美服活躍", 2)
        if 1 <= hour < 7:
            return ("尖峰時段", "歐服活躍", 2)
        if 20 <= hour or hour < 1:
            return ("普通偏高", "亞洲活躍", 1)
        return ("離峰時段", "整體較分散", 0)

    def _body_risk(self, body):
        mining = body.get("mining", {})
        peak_label, peak_region, peak_level = self._peak_info()
        hotspot = str(mining.get("hotspot_level") or "unknown").lower()
        access = str(mining.get("accessibility") or "unknown").lower()
        hotspot_score = {"high": 2, "medium": 1, "low": 0}.get(hotspot, 0)
        access_score = {"high": 1, "medium": 1, "low": 0}.get(access, 0)
        total = peak_level + hotspot_score + access_score
        if total >= 4:
            return ("高風險", "#7a1f2b", f"{peak_label}｜採集熱區｜{peak_region}")
        if total >= 2:
            return ("中風險", "#6d5618", f"{peak_label}｜注意熱門路線｜{peak_region}")
        return ("低風險", "#1f5a3a", f"{peak_label}｜相對分散｜{peak_region}")


    def _set_timer_banner(self, text: str | None = None, bg: str = "#1b3242", fg: str = "#f4fbff", lights=None, tail_text: str = "") -> None:
        if not text:
            try:
                self.timer_banner_frame.pack_forget()
            except Exception:
                pass
            self.timer_banner.configure(text="", bg="#1b3242", fg="#f4fbff")
            self.timer_banner_tail.configure(text="", bg="#1b3242", fg="#f4fbff")
            self.timer_banner_lights.configure(bg="#1b3242", width=0)
            self.timer_banner_inline.configure(bg="#1b3242")
            self.timer_banner_spacer.configure(bg="#1b3242")
            self.timer_banner_lights.delete("all")
            self._timer_banner_state = {"bg": "#1b3242", "fg": "#f4fbff", "text": "", "tail": "", "lights": []}
            return

        lights = list(lights or [])
        self._timer_banner_state = {"bg": bg, "fg": fg, "text": text, "tail": tail_text, "lights": lights}
        self.timer_banner_frame.configure(bg=bg)
        self.timer_banner.configure(text=text, bg=bg, fg=fg)
        self.timer_banner_inline.configure(bg=bg)
        self.timer_banner_spacer.configure(bg=bg)
        self.timer_banner_tail.configure(text=tail_text, bg=bg, fg=fg)
        self.timer_banner_lights.configure(bg=bg)
        self.timer_banner_lights.delete("all")

        if lights:
            radius = 8
            gap = 7
            x = 8
            y = 8.3
            color_map = {"綠": "#23d14d", "紅": "#ff4d4f", "藍": "#4da3ff", "熄": "#2a2a2a", "亮": "#ffd24d", "?": "#cfcfcf"}
            blink_last_green = len(lights) == 5 and str(lights[-1]) == "綠" and bool(getattr(self, "_hangar_last_light_green_blink", False))
            for idx, light in enumerate(lights[:5]):
                key = str(light)
                fill = color_map.get(key, "#cfcfcf")
                outline = "#8a8a8a" if fill == "#2a2a2a" else fill
                if blink_last_green and idx == 4:
                    fill = bg if getattr(self, "_hangar_banner_blink_state", False) else "#23d14d"
                    outline = "#23d14d"
                self.timer_banner_lights.create_oval(
                    x - radius, y - radius, x + radius, y + radius,
                    fill=fill, outline=outline, width=1
                )
                x += radius * 2 + gap
            self.timer_banner_lights.configure(width=max(38, x - gap - 5))
        else:
            self.timer_banner_lights.configure(width=0)

        try:
            self.timer_banner_frame.pack_forget()
        except Exception:
            pass

        before_widget = None
        try:
            if self.risk_banner.winfo_manager() == "pack":
                before_widget = self.risk_banner
            elif self.right_split.winfo_manager() == "pack":
                before_widget = self.right_split
        except Exception:
            before_widget = None

        try:
            if before_widget is not None:
                self.timer_banner_frame.pack(fill="x", padx=8, pady=(0,6), before=before_widget)
            else:
                self.timer_banner_frame.pack(fill="x", padx=8, pady=(0,6))
        except Exception:
            self.timer_banner_frame.pack(fill="x", padx=8, pady=(0,6))

    def _clear_hangar_timer(self) -> None:
        self._hangar_timer_active = False
        if self._hangar_timer_job is not None:
            try:
                self.after_cancel(self._hangar_timer_job)
            except Exception:
                pass
            self._hangar_timer_job = None
        if self._hangar_timer_fetch_job is not None:
            try:
                self.after_cancel(self._hangar_timer_fetch_job)
            except Exception:
                pass
            self._hangar_timer_fetch_job = None
        self._hangar_timer_state = None
        self._hangar_timer_source = None
        self._set_timer_banner(None)


    def _start_hangar_timer(self, facility: dict) -> None:
        self.logger.info("start hangar timer via SC ExecHang: %s", facility.get("name_en"))
        self._clear_hangar_timer()
        self._hangar_timer_active = True
        self._set_timer_banner("行政機庫即時狀態｜正在從 SC ExecHang 讀取一次校正時間…", bg="#214c66")
        self._schedule_hangar_fetch(force=True)


    def _schedule_hangar_fetch(self, force: bool = False) -> None:
        if not self._hangar_timer_active:
            return

        if self._hangar_timer_fetch_job is not None:
            if force:
                try:
                    self.after_cancel(self._hangar_timer_fetch_job)
                except Exception:
                    pass
                self._hangar_timer_fetch_job = None
            else:
                return

        if self._hangar_timer_thread is not None and self._hangar_timer_thread.is_alive() and not force:
            return

        delay_ms = 0 if force else 900

        def kickoff():
            self._hangar_timer_fetch_job = None
            if not self._hangar_timer_active:
                return
            if self._hangar_timer_thread is not None and self._hangar_timer_thread.is_alive():
                return

            self._hangar_timer_fetch_started = time.time()

            def worker():
                state = self._fetch_hangar_external_state()

                def apply():
                    if not self._hangar_timer_active:
                        return
                    if state:
                        state["refetch_requested"] = False
                    self._hangar_timer_state = state
                    self._hangar_timer_source = state.get("source") if state else None
                    self._hangar_timer_thread = None
                    self._hangar_timer_tick()

                try:
                    self.after(0, apply)
                except Exception:
                    pass

            t = threading.Thread(target=worker, daemon=True)
            self._hangar_timer_thread = t
            t.start()

        self._hangar_timer_fetch_job = self.after(delay_ms, kickoff)

    def _fetch_hangar_external_state(self, force: bool = False) -> None:
        return

    def _hangar_browser_candidates(self) -> list[str]:
        candidates: list[str] = []

        env_path = str((os.environ.get("SC_HANGAR_BROWSER") or "")).strip()
        if env_path:
            candidates.append(env_path)

        local_roots = [BASE_DIR, BASE_DIR.parent]
        local_names = [
            "chrome.exe",
            "msedge.exe",
            "chromium.exe",
            "GoogleChromePortable.exe",
        ]
        for root in local_roots:
            for name in local_names:
                path = root / name
                if path.exists():
                    candidates.append(str(path))

        common_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Chromium\Application\chrome.exe",
            r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
        ]
        for path in common_paths:
            if Path(path).exists():
                candidates.append(path)

        seen = set()
        ordered = []
        for item in candidates:
            key = item.lower()
            if not key or key in seen:
                continue
            seen.add(key)
            ordered.append(item)
        return ordered

    def _fetch_hangar_external_state(self) -> dict | None:
        source = "scexechang"
        url = "https://sc-exechang.vercel.app/"

        # 先用瀏覽器渲染後 DOM，因為此站有時候直接抓原始 HTML 只會拿到前端殼。
        try:
            from playwright.sync_api import sync_playwright  # type: ignore
            with sync_playwright() as pw:
                html = None
                last_exc = None

                launch_attempts: list[dict] = []
                if getattr(sys, "frozen", False):
                    for browser_path in self._hangar_browser_candidates():
                        launch_attempts.append({"headless": True, "executable_path": browser_path})
                launch_attempts.append({"headless": True})

                for launch_kwargs in launch_attempts:
                    browser = None
                    try:
                        self.logger.info("hangar playwright launch attempt: %s", launch_kwargs)
                        browser = pw.chromium.launch(**launch_kwargs)
                        page = browser.new_page(viewport={"width": 1280, "height": 900})
                        page.goto(url, wait_until="domcontentloaded", timeout=12000)
                        try:
                            page.wait_for_timeout(1600)
                            page.wait_for_load_state("networkidle", timeout=5000)
                        except Exception:
                            pass
                        try:
                            page.wait_for_selector("h2, .font-mono, [style*='background-color']", timeout=5000)
                        except Exception:
                            pass
                        html = page.content()
                        if html:
                            break
                    except Exception as exc:
                        last_exc = exc
                        self.logger.warning("hangar playwright launch failed: %s | kwargs=%s", exc, launch_kwargs)
                    finally:
                        if browser is not None:
                            try:
                                browser.close()
                            except Exception:
                                pass

                if not html and last_exc is not None:
                    raise last_exc

            state = self._parse_hangar_external_state(html or "", source)
            if state:
                self.logger.info("hangar source ok (playwright): %s | state=%s", source, state)
                return state
            self.logger.warning("hangar source parsed empty after playwright: %s", source)
        except Exception as exc:
            self.logger.warning("hangar playwright unavailable or failed: %s", exc)

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            state = self._parse_hangar_external_state(html, source)
            if state:
                self.logger.info("hangar source ok (urllib): %s | state=%s", source, state)
                return state
            self.logger.warning("hangar source parsed empty: %s", source)
            return None
        except Exception as exc:
            self.logger.exception("hangar source failed: %s | %s", source, exc)
            return None

    def _hangar_phase_from_text(self, text: str | None) -> str | None:
        lowered = str(text or "").strip().lower()
        if not lowered:
            return None
        if "closed" in lowered:
            return "closed"
        if "charging" in lowered:
            return "charging"
        if "opening" in lowered:
            return "opening"
        if lowered == "open" or "hangar open" in lowered or "ready" in lowered:
            return "open"
        if "active" in lowered:
            return "active"
        if "cooldown" in lowered:
            return "cooldown"
        if "reset" in lowered:
            return "reset"
        if "closing" in lowered:
            return "closing"
        return None

    def _classify_hangar_light(self, style_text: str | None) -> str:
        style = str(style_text or "").strip().lower()
        if not style:
            return "?"
        if "green" in style:
            return "綠"
        if "red" in style:
            return "紅"
        if "blue" in style:
            return "藍"
        m = re.search(r"rgb[a]?\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\)", style, re.I)
        if not m:
            return "?"
        r, g, b = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if max(r, g, b) < 60:
            return "熄"
        if g > r + 40 and g > b + 40:
            return "綠"
        if r > g + 40 and r > b + 40:
            return "紅"
        if b > r + 40 and b > g + 40:
            return "藍"
        return "亮"

    def _summarize_hangar_lights(self, text: str) -> str:
        styles = re.findall(r"background-color\s*:\s*([^;\"\']+)", text or "", re.I)
        if not styles:
            return "-"
        labels = [self._classify_hangar_light(x) for x in styles[:5]]
        return " / ".join(labels) if labels else "-"

    def _parse_hangar_external_state(self, text: str, source: str) -> dict | None:
        raw = text or ""
        clean = re.sub(r"<[^>]+>", " ", raw)
        clean = re.sub(r"\s+", " ", clean).strip()
        phase = None
        remaining = None
        status_text = None
        timer_label = None
        light_remaining = None

        light_styles = re.findall(r"background-color\s*:\s*([^;\"\']+)", raw, re.I)[:5]
        light_labels = [self._classify_hangar_light(x) for x in light_styles]
        lights_summary = " / ".join(light_labels) if light_labels else "-"

        # 直接抓畫面上的狀態標題
        m = re.search(r">\s*(Hangar\s+(?:Closed|Open|Opening|Charging|Active|Ready|Closing))\s*<", raw, re.I)
        if m:
            status_text = m.group(1).strip()
            phase = self._hangar_phase_from_text(status_text)
        elif re.search(r"hangar\s+closed", clean, re.I):
            status_text = "Hangar Closed"
            phase = "closed"
        elif re.search(r"hangar\s+open", clean, re.I):
            status_text = "Hangar Open"
            phase = "open"

        # 主倒數：Open in / Charging in / Reset in
        m = re.search(r">\s*((?:Open|Charging|Reset)\s+in)\s+([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?\s*<", raw, re.I)
        if not m:
            m = re.search(r"((?:Open|Charging|Reset)\s+in)\s+([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?", clean, re.I)
        if m:
            timer_label = m.group(1).strip()
            if m.group(4) is not None:
                remaining = int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4))
            else:
                remaining = int(m.group(2)) * 60 + int(m.group(3))

            timer_label_lower = timer_label.lower()
            if timer_label_lower.startswith("charging"):
                phase = "charging"
            elif timer_label_lower.startswith("reset"):
                phase = "open"
            elif timer_label_lower.startswith("open"):
                phase = "waiting"
            elif phase is None:
                phase = "closed"

        # 燈號旁小倒數，例如 <span class="... font-mono">03:19</span>
        m = re.search(r"<span[^>]*font-mono[^>]*>\s*([0-9]{1,2}):([0-9]{2})\s*</span>", raw, re.I)
        if m:
            light_remaining = int(m.group(1)) * 60 + int(m.group(2))
        else:
            candidates = re.findall(r">\s*([0-9]{1,2}):([0-9]{2})\s*<", raw, re.I)
            vals = []
            for a, b in candidates:
                sec = int(a) * 60 + int(b)
                if remaining is not None and sec == remaining:
                    continue
                vals.append(sec)
            if vals:
                light_remaining = vals[-1]

        if phase is None and remaining is not None:
            phase = "unknown"

        if phase is None and remaining is None and lights_summary == "-" and light_remaining is None:
            return None

        return {
            "source": source,
            "phase": phase or "unknown",
            "remaining": remaining,
            "fetched_at": time.time(),
            "status_text": status_text,
            "timer_label": timer_label,
            "lights_summary": lights_summary,
            "lights_raw": light_labels,
            "light_remaining": light_remaining,
            "raw_text": clean,
        }



    def _hangar_timer_tick(self) -> None:
        if not self._hangar_timer_active:
            return

        self.logger.info("hangar tick active=%s state=%s", self._hangar_timer_active, self._hangar_timer_state)
        self._hangar_banner_blink_state = not bool(getattr(self, "_hangar_banner_blink_state", False))
        self._hangar_last_light_green_blink = False

        if not self._hangar_timer_state:
            self._set_timer_banner("行政機庫即時狀態｜無法從 SC ExecHang 讀取時間", bg="#665028")
            self._hangar_timer_job = self.after(3000, lambda: self._schedule_hangar_fetch(force=True))
            return

        elapsed = int(time.time() - float(self._hangar_timer_state.get("fetched_at", time.time())))
        text = str(self._hangar_timer_state.get("raw_text") or "")
        remaining_raw = self._hangar_timer_state.get("remaining")

        if "Reset in" in text:
            phase = "open"
            label = "開放中（倒數關門）"
        elif "Hangar Open" in text:
            phase = "open"
            label = "開放中"
        elif "Charging in" in text:
            phase = "charging"
            label = "充能中"
        elif "Open in" in text:
            phase = "waiting"
            label = "尚未開放"
        elif "Closed" in text:
            phase = "closed"
            label = "關閉"
        else:
            phase = str(self._hangar_timer_state.get("phase") or "unknown").lower()
            phase_labels = {
                "unknown": "未知",
                "charging": "充能中",
                "active": "可開門",
                "cooldown": "冷卻中",
                "reset": "重置中",
                "closed": "機庫關閉",
                "opening": "準備開啟",
                "open": "已開啟 / 可進入",
                "waiting": "尚未開放",
                "closing": "即將關閉",
            }
            label = phase_labels.get(phase, "未知")

        remaining = None
        if remaining_raw is not None:
            remaining = max(0, int(remaining_raw) - elapsed)

        lights = list(self._hangar_timer_state.get("lights_raw") or [])
        if not lights:
            summary = str(self._hangar_timer_state.get("lights_summary") or "")
            lights = [x.strip() for x in summary.split("/") if x.strip()] if summary else []

        if len(lights) == 5 and str(lights[-1]) == "綠":
            self._hangar_last_light_green_blink = True

        light_remaining = self._hangar_timer_state.get("light_remaining")
        light_left = None
        if light_remaining is not None:
            light_left = max(0, int(light_remaining) - elapsed)

        refetch_requested = bool(self._hangar_timer_state.get("refetch_requested", False))

        time_text = ""
        if remaining is not None:
            hh = remaining // 3600
            mm = (remaining % 3600) // 60
            ss = remaining % 60
            if phase == "open":
                time_text = f"關門倒數 {hh:02d}:{mm:02d}:{ss:02d}"
            elif phase in ("waiting", "charging"):
                time_text = f"開啟倒數 {hh:02d}:{mm:02d}:{ss:02d}"
            else:
                time_text = f"剩餘 {hh:02d}:{mm:02d}:{ss:02d}"

        if phase == "open":
            if remaining is not None and remaining <= 180:
                bg = "#d13438" if self._hangar_banner_blink_state else "#6d2d34"
            else:
                bg = "#24583f"
        elif phase == "charging":
            bg = "#7a5d1a"
        elif phase == "waiting":
            bg = "#235e7d"
        else:
            bg = "#6d2d34"

        parts = [f"行政機庫即時狀態｜SC ExecHang｜{label}"]
        if time_text:
            parts.append(time_text)
        if refetch_requested:
            parts.append("同步中…")

        tail_text = ""
        if light_left is not None:
            tail_text = f"燈號倒數 {light_left // 60:02d}:{light_left % 60:02d}"

        self._set_timer_banner("｜".join(parts), bg=bg, lights=lights, tail_text=tail_text)

        should_refetch = False
        if remaining is not None and remaining <= 0:
            should_refetch = True
        # 燈號旁的小倒數歸零時，也要重抓一次外部狀態，
        # 否則畫面會停在 00:00 不更新。
        if light_left is not None and light_left <= 0:
            should_refetch = True

        if should_refetch:
            if not refetch_requested:
                self._hangar_timer_state["refetch_requested"] = True
                self._schedule_hangar_fetch(force=True)
            self._hangar_timer_job = self.after(1000, self._hangar_timer_tick)
            return

        self._hangar_timer_job = self.after(1000, self._hangar_timer_tick)

    def _set_risk_banner(self, body=None):

        if not body:
            self.risk_banner.configure(text="風險：待判定", bg="#23465a", fg="#e6fbff")
            return
        level, color, msg = self._body_risk(body)
        self.risk_banner.configure(text=f"風險：{level}｜{msg}", bg=color, fg="#f5fbff")

    def _update_preview_nav(self):
        total = len(getattr(self, '_preview_paths', []) or [])
        idx = int(getattr(self, '_preview_index', 0) or 0)
        if hasattr(self, 'preview_page_label'):
            self.preview_page_label.configure(text=(f"{idx + 1} / {total}" if total else "0 / 0"))
        state = "normal" if total > 1 else "disabled"
        if hasattr(self, 'preview_prev_btn'):
            self.preview_prev_btn.configure(state=state)
        if hasattr(self, 'preview_next_btn'):
            self.preview_next_btn.configure(state=state)

    def _set_preview_images(self, rel_paths):
        paths = []
        for x in (rel_paths or []):
            rel = str(x).strip()
            if not rel:
                continue
            try:
                if (BASE_DIR / rel).exists():
                    paths.append(rel)
            except Exception:
                continue
        self._preview_paths = paths
        self._preview_index = 0
        if not self._preview_paths:
            self._hide_preview_image()
            return
        self._show_current_preview(reset_view=True)

    def _show_current_preview(self, reset_view=False):
        if not getattr(self, '_preview_paths', None):
            self._hide_preview_image()
            return
        self._preview_index = max(0, min(int(self._preview_index), len(self._preview_paths) - 1))
        self._set_preview_image(self._preview_paths[self._preview_index], reset_view=reset_view)
        self._update_preview_nav()

    def _preview_prev_image(self):
        total = len(getattr(self, '_preview_paths', []) or [])
        if total <= 1:
            return
        self._preview_index = (self._preview_index - 1) % total
        self._show_current_preview(reset_view=False)

    def _preview_next_image(self):
        total = len(getattr(self, '_preview_paths', []) or [])
        if total <= 1:
            return
        self._preview_index = (self._preview_index + 1) % total
        self._show_current_preview(reset_view=False)

    def _expand_preview_section(self):
        if getattr(self, "preview_hidden", True):
            return
        if getattr(self, "_preview_full_mode", False):
            return

        try:
            self._preview_restore_sash_y = self.right_split.sash_coord(0)[1]
        except Exception:
            self._preview_restore_sash_y = None
        self._preview_restore_timer_text = self._timer_banner_state.get("text", "")
        self._preview_restore_timer_bg = self._timer_banner_state.get("bg", "#1b3242")
        self._preview_restore_timer_fg = self._timer_banner_state.get("fg", "#f4fbff")
        self._preview_restore_timer_visible = bool(self.timer_banner_frame.winfo_ismapped())
        self._preview_restore_timer_tail = self._timer_banner_state.get("tail", "")
        self._preview_restore_timer_lights = list(self._timer_banner_state.get("lights", []))
        self._preview_restore_risk_visible = bool(self.risk_banner.winfo_ismapped())
        self._preview_restore_right_title_visible = bool(self.right_title_label.winfo_ismapped())
        self._preview_restore_suggest_visible = bool(self.suggest_frame.winfo_manager())

        for widget in (self.info_row, self.search_row, self.recent_label):
            try:
                widget.pack_forget()
            except Exception:
                pass
        try:
            self.suggest_frame.pack_forget()
        except Exception:
            pass
        try:
            self.right_title_label.pack_forget()
        except Exception:
            pass
        try:
            self.timer_banner_frame.pack_forget()
        except Exception:
            pass
        try:
            self.risk_banner.pack_forget()
        except Exception:
            pass

        try:
            for pane in list(self.main_area.panes()):
                self.main_area.forget(pane)
            self.main_area.add(self.right_panel, minsize=360)
        except Exception:
            pass

        try:
            for pane in list(self.right_split.panes()):
                self.right_split.forget(pane)
            self.right_split.add(self.preview_frame, minsize=160)
        except Exception:
            pass

        self._preview_full_mode = True
        self._preview_expanded = True
        self.preview_expand_btn.configure(state="disabled")
        self.preview_restore_btn.configure(state="normal")
        self.preview_canvas.after_idle(self._render_preview_image)
        self._update_preview_nav()

    def _restore_preview_section(self):
        if not getattr(self, "_preview_full_mode", False):
            if not getattr(self, "preview_hidden", True):
                try:
                    sash_y = getattr(self, "_preview_restore_sash_y", None) or getattr(self, "_preview_last_sash_y", None) or int(max(500, self.right_panel.winfo_height() or 700) * 0.62)
                    self.right_split.sash_place(0, 0, int(sash_y))
                except Exception:
                    pass
            self.preview_restore_btn.configure(state="disabled")
            self.preview_expand_btn.configure(state="normal")
            self._preview_expanded = False
            return

        try:
            self.info_row.pack(fill="x", padx=12, pady=(8, 2), before=self.main_area)
        except Exception:
            pass
        try:
            self.search_row.pack(fill="x", padx=12, pady=(2, 0), before=self.main_area)
        except Exception:
            pass
        if getattr(self, "_preview_restore_suggest_visible", False):
            try:
                self._show_suggestions()
            except Exception:
                pass
        try:
            self.recent_label.pack(fill="x", padx=12, pady=(6,8), before=self.main_area)
        except Exception:
            pass

        try:
            for pane in list(self.main_area.panes()):
                self.main_area.forget(pane)
            self.main_area.add(self.left_panel, minsize=250)
            self.main_area.add(self.right_panel, minsize=360)
        except Exception:
            pass

        try:
            self.right_title_label.pack_forget()
        except Exception:
            pass
        try:
            self.timer_banner_frame.pack_forget()
        except Exception:
            pass
        try:
            self.risk_banner.pack_forget()
        except Exception:
            pass

        if getattr(self, "_preview_restore_right_title_visible", True):
            try:
                self.right_title_label.pack(fill="x", padx=8, pady=(8,6), before=self.right_split)
            except Exception:
                try:
                    self.right_title_label.pack(fill="x", padx=8, pady=(8,6))
                except Exception:
                    pass

        if getattr(self, "_preview_restore_risk_visible", True):
            try:
                self.risk_banner.pack(fill="x", padx=8, pady=(0,6), before=self.right_split)
            except Exception:
                pass

        if getattr(self, "_preview_restore_timer_visible", False) and str(getattr(self, "_preview_restore_timer_text", "") or "").strip():
            try:
                self._set_timer_banner(self._preview_restore_timer_text, bg=self._preview_restore_timer_bg, fg=self._preview_restore_timer_fg, lights=getattr(self, "_preview_restore_timer_lights", []), tail_text=getattr(self, "_preview_restore_timer_tail", ""))
            except Exception:
                try:
                    self.timer_banner.pack(fill="x", padx=8, pady=(0,6), before=self.right_split)
                except Exception:
                    pass

        try:
            for pane in list(self.right_split.panes()):
                self.right_split.forget(pane)
            self.right_split.add(self.detail_holder, minsize=40)
            if not getattr(self, "preview_hidden", False):
                self.right_split.add(self.preview_frame, minsize=180)
        except Exception:
            pass

        if not getattr(self, "preview_hidden", False):
            try:
                sash_y = getattr(self, "_preview_restore_sash_y", None) or getattr(self, "_preview_last_sash_y", None) or int(max(500, self.right_panel.winfo_height() or 700) * 0.62)
                self.right_split.sash_place(0, 0, int(sash_y))
            except Exception:
                pass

        self._preview_full_mode = False
        self._preview_expanded = False
        self.preview_expand_btn.configure(state="normal")
        self.preview_restore_btn.configure(state="disabled")
        self.preview_canvas.after_idle(self._render_preview_image)
        self._update_preview_nav()

    def _remember_preview_sash(self, event=None):
        try:
            y = self.right_split.sash_coord(0)[1]
            self._preview_last_sash_y = int(y)
            self._preview_pane_initialized = True
        except Exception:
            pass

    def _hide_preview_image(self):
        if getattr(self, "_preview_full_mode", False):
            self._restore_preview_section()
        self.preview_canvas.delete("all")
        self.preview_path_label.configure(text="")
        self._preview_original_image = None
        self._preview_render_image = None
        self._preview_cache_zoom = None
        self._preview_cache_path = None
        self._preview_item_id = None
        self._preview_drag_last = None
        self._preview_user_changed = False
        self._preview_auto_fit_pending = False
        self._preview_current_path = None
        self._preview_paths = []
        self._preview_index = 0
        self._preview_expanded = False
        self._preview_fit_locked = False
        self._update_preview_nav()
        if hasattr(self, "preview_restore_btn"):
            self.preview_restore_btn.configure(state="disabled")
        if hasattr(self, "preview_expand_btn"):
            self.preview_expand_btn.configure(state="normal")
        if not getattr(self, "preview_hidden", False):
            try:
                self.right_split.forget(self.preview_frame)
            except Exception:
                pass
            self.preview_hidden = True

    def _fit_preview_zoom(self):
        if self._preview_original_image is None:
            self._preview_zoom = 1.0
            return
        try:
            cw = max(1, int(self.preview_canvas.winfo_width()))
            ch = max(1, int(self.preview_canvas.winfo_height()))
        except Exception:
            cw, ch = 520, 260
        ow, oh = self._preview_original_image.size
        if ow <= 0 or oh <= 0:
            self._preview_zoom = 1.0
            return
        self._preview_zoom = min(cw / ow, ch / oh, 1.0)
        if self._preview_zoom <= 0:
            self._preview_zoom = 1.0

    def _render_preview_image(self):
        if self._preview_original_image is None:
            self.preview_canvas.delete("all")
            self._preview_item_id = None
            return
        img = self._preview_original_image
        ow, oh = img.size
        zoom = max(0.1, min(6.0, float(self._preview_zoom)))
        nw = max(1, int(ow * zoom))
        nh = max(1, int(oh * zoom))
        try:
            need_reraster = (
                self._preview_render_image is None
                or self._preview_cache_zoom != (nw, nh)
                or self._preview_cache_path != str(self._preview_current_path)
            )
            if need_reraster:
                if Image is not None and ImageTk is not None:
                    resample = Image.BILINEAR if getattr(self, "_preview_interactive_resample", True) else Image.LANCZOS
                    resized = img.resize((nw, nh), resample)
                    self._preview_render_image = ImageTk.PhotoImage(resized)
                else:
                    self._preview_render_image = tk.PhotoImage(file=str(self._preview_current_path))
                self._preview_cache_zoom = (nw, nh)
                self._preview_cache_path = str(self._preview_current_path)
        except Exception:
            self.logger.exception("預覽圖縮放失敗")
            return

        cx = max(1, int(self.preview_canvas.winfo_width())) // 2 + int(self._preview_pan_x)
        cy = max(1, int(self.preview_canvas.winfo_height())) // 2 + int(self._preview_pan_y)
        if self._preview_item_id is None:
            self.preview_canvas.delete("all")
            self._preview_item_id = self.preview_canvas.create_image(cx, cy, image=self._preview_render_image, anchor="center", tags="preview")
        else:
            try:
                self.preview_canvas.itemconfigure(self._preview_item_id, image=self._preview_render_image)
                self.preview_canvas.coords(self._preview_item_id, cx, cy)
            except Exception:
                self.preview_canvas.delete("all")
                self._preview_item_id = self.preview_canvas.create_image(cx, cy, image=self._preview_render_image, anchor="center", tags="preview")

    def _set_preview_image(self, rel_path, reset_view=False):
        if not rel_path:
            self._hide_preview_image()
            return
        try:
            path = BASE_DIR / str(rel_path)
            if not path.exists():
                self._hide_preview_image()
                return
            same_path = (self._preview_current_path == path) and (self._preview_original_image is not None)
            if (not same_path) or reset_view:
                keep_zoom = (
                    (not reset_view)
                    and self._preview_original_image is not None
                    and self._preview_user_changed
                )
                prev_zoom = self._preview_zoom
                prev_fit_locked = self._preview_fit_locked
                self._preview_current_path = path
                if Image is not None:
                    self._preview_original_image = Image.open(path).convert("RGBA")
                else:
                    return
                self._preview_pan_x = 0
                self._preview_pan_y = 0
                self._preview_render_image = None
                self._preview_cache_zoom = None
                self._preview_cache_path = None
                self._preview_item_id = None
                self._preview_target_zoom = None
                self._preview_interactive_resample = True
                if keep_zoom and prev_zoom:
                    self._preview_zoom = prev_zoom
                    self._preview_user_changed = True
                    self._preview_auto_fit_pending = False
                    self._preview_fit_locked = prev_fit_locked or True
                else:
                    self._preview_zoom = None
                    self._preview_user_changed = False
                    self._preview_auto_fit_pending = True
                    self._preview_fit_locked = False

            self.preview_path_label.configure(text=str(rel_path))
            if not getattr(self, "_preview_full_mode", False):
                self.preview_expand_btn.configure(state="normal")
                self.preview_restore_btn.configure(state="disabled")
            else:
                self.preview_expand_btn.configure(state="disabled")
                self.preview_restore_btn.configure(state="normal")
            if getattr(self, "preview_hidden", True):
                try:
                    self.right_split.add(self.preview_frame, minsize=160)
                except Exception:
                    pass
                self.preview_hidden = False
                try:
                    total_h = max(500, self.right_panel.winfo_height() or 700)
                    sash_y = self._preview_last_sash_y if getattr(self, "_preview_pane_initialized", False) and getattr(self, "_preview_last_sash_y", None) else int(total_h * 0.62)
                    self.right_split.sash_place(0, 0, sash_y)
                except Exception:
                    pass
            self.preview_frame.update_idletasks()
            if (self._preview_auto_fit_pending or self._preview_zoom is None) and not self._preview_fit_locked:
                self._fit_preview_zoom()
                self._preview_auto_fit_pending = False
            self._render_preview_image()
        except Exception:
            self.logger.exception("預覽圖片載入失敗: %s", rel_path)

    def _on_preview_configure(self, event=None):
        if self._preview_original_image is None:
            return
        if (not self._preview_fit_locked) and (not self._preview_user_changed) and (self._preview_auto_fit_pending or self._preview_zoom is None):
            self._fit_preview_zoom()
            self._preview_pan_x = 0
            self._preview_pan_y = 0
            self._preview_auto_fit_pending = False
        self._render_preview_image()

    def _on_preview_press(self, event):
        if self._preview_original_image is None:
            return
        self._preview_user_changed = True
        self._preview_fit_locked = True
        self._preview_auto_fit_pending = False
        self._preview_drag_last = (event.x, event.y)

    def _on_preview_drag(self, event):
        if self._preview_original_image is None or not self._preview_drag_last:
            return
        if self._preview_quality_job is not None:
            try:
                self.after_cancel(self._preview_quality_job)
            except Exception:
                pass
            self._preview_quality_job = None
        lx, ly = self._preview_drag_last
        dx = (event.x - lx)
        dy = (event.y - ly)
        self._preview_pan_x += dx
        self._preview_pan_y += dy
        self._preview_drag_last = (event.x, event.y)
        self._preview_user_changed = True
        if self._preview_item_id is not None:
            try:
                self.preview_canvas.move(self._preview_item_id, dx, dy)
                return
            except Exception:
                self._preview_item_id = None
        self._render_preview_image()

    def _on_preview_release(self, event=None):
        self._preview_drag_last = None

    def _apply_preview_zoom(self):
        self._preview_zoom_job = None
        if self._preview_original_image is None:
            return
        if self._preview_target_zoom is None:
            return
        self._preview_zoom = self._preview_target_zoom
        self._preview_user_changed = True
        self._preview_fit_locked = True
        self._preview_interactive_resample = True
        self._preview_render_image = None
        self._preview_cache_zoom = None
        self._render_preview_image()
        if self._preview_quality_job is not None:
            try:
                self.after_cancel(self._preview_quality_job)
            except Exception:
                pass
        self._preview_quality_job = self.after(120, self._finalize_preview_quality)

    def _finalize_preview_quality(self):
        self._preview_quality_job = None
        if self._preview_original_image is None:
            return
        self._preview_interactive_resample = False
        self._preview_render_image = None
        self._preview_cache_zoom = None
        self._render_preview_image()

    def _on_preview_wheel(self, event, delta=None):
        if self._preview_original_image is None:
            return
        d = delta if delta is not None else getattr(event, 'delta', 0)
        if d == 0:
            return
        base_zoom = self._preview_target_zoom if self._preview_target_zoom else self._preview_zoom
        factor = 1.09 if d > 0 else (1 / 1.09)
        new_zoom = max(0.1, min(6.0, base_zoom * factor))
        if abs(new_zoom - base_zoom) < 1e-6:
            return
        self._preview_target_zoom = new_zoom
        self._preview_user_changed = True
        self._preview_fit_locked = True
        if self._preview_zoom_job is not None:
            try:
                self.after_cancel(self._preview_zoom_job)
            except Exception:
                pass
        self._preview_zoom_job = self.after(12, self._apply_preview_zoom)

    def _reset_preview_view(self, event=None):
        if self._preview_original_image is None:
            return
        self._preview_pan_x = 0
        self._preview_pan_y = 0
        self._preview_user_changed = False
        self._preview_fit_locked = False
        self._fit_preview_zoom()
        self._preview_target_zoom = None
        self._preview_interactive_resample = False
        self._preview_render_image = None
        self._preview_cache_zoom = None
        self._preview_cache_path = None
        self._preview_item_id = None
        self._render_preview_image()


    def _show_facility_detail(self, facility):
        self.logger.info("facility detail opened: %s", facility.get("name_en") if facility else None)
        if not facility:
            self._set_risk_banner(None)
            self._set_detail("找不到設施資料")
            return
        images = facility.get("image_paths") or []
        self._set_preview_images(images)
        self._set_risk_banner(None)
        name_en = (facility.get("name_en") or "").strip()
        if name_en == "Executive Hangars":
            self._start_hangar_timer(facility)
        else:
            self._clear_hangar_timer()
            timing_lines = list(facility.get("card_timing") or [])
            if facility.get("timing"):
                timing_lines.extend(str(facility.get("timing")).splitlines())
            if timing_lines:
                first_line = str(timing_lines[0]).strip()
                self._set_timer_banner(f"設施時間｜{first_line}", bg="#304d5c")
            else:
                self._set_timer_banner(None)
        self._set_detail(self.store.facility_detail_text(facility))

    def _set_detail(self, text):
        filtered_lines = [line for line in text.splitlines() if not line.strip().startswith("[[IMAGE:")]

        formatted_lines = []
        in_blueprint_section = False
        for raw_line in filtered_lines:
            stripped = raw_line.strip()
            if stripped == "—— 製作圖紙 ——":
                in_blueprint_section = True
            elif stripped.startswith("—— ") and stripped.endswith(" ——") and stripped != "—— 製作圖紙 ——":
                in_blueprint_section = False

            is_top_blueprint = in_blueprint_section and raw_line.startswith("- ")
            if is_top_blueprint and formatted_lines and formatted_lines[-1].strip():
                formatted_lines.append("")
            formatted_lines.append(raw_line)

        clean_text = "\n".join(formatted_lines)
        self.detail.configure(state="normal")
        self.detail.delete("1.0", tk.END)
        self.detail.insert("1.0", clean_text)

        lines = clean_text.splitlines()
        in_blueprint_section = False
        in_materials = False
        in_missions = False

        general_headers = {
            "摘要：", "狀態分析：", "進入方式：", "1–7 任務順序：", "拿卡片位置：", "卡片時間：", "最後插卡位置：",
            "開啟時間：", "倒數參考：", "固定獎勵：", "獎勵：", "外部倒數：", "文字圖解：", "說明：", "補充：",
            "已知採集位置摘要：", "資源概況", "到達方式", "判斷理由："
        }

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            start = f"{idx}.0"
            end = f"{idx}.end"

            if idx == 1 and stripped.startswith("【") and stripped.endswith("】"):
                self.detail.tag_add("item_title", start, end)

            if not stripped or stripped.startswith("[[IMAGE:"):
                continue

            if stripped in {"—— 製作圖紙 ——", "關聯製作圖紙："}:
                in_blueprint_section = True
                in_materials = False
                in_missions = False
                self.detail.tag_add("section_header", start, end)
                continue

            if stripped.startswith("—— ") and stripped.endswith(" ——") and stripped != "—— 製作圖紙 ——":
                in_blueprint_section = False
                in_materials = False
                in_missions = False
                self.detail.tag_add("section_header", start, end)
                continue

            if stripped in general_headers or stripped in {"【地表】", "【洞穴】", "【太空／小行星】"}:
                self.detail.tag_add("section_header", start, end)
                continue

            if in_blueprint_section and stripped in {"材料：", "獲取任務："}:
                self.detail.tag_add("section_header", start, end)
                in_materials = stripped == "材料："
                in_missions = stripped == "獲取任務："
                continue

            is_top_blueprint = in_blueprint_section and line.startswith("- ")
            is_nested_bullet = line.startswith("    - ") or line.startswith("  - ")

            if is_top_blueprint:
                in_materials = False
                in_missions = False
                self.detail.tag_add("blueprint_name", start, end)
                continue

            if in_blueprint_section and (stripped.startswith("分類：") or stripped.startswith("材料數：") or stripped.startswith("獲取任務數：")):
                self.detail.tag_add("blueprint_meta", start, end)
                continue

            if in_materials and is_nested_bullet:
                self.detail.tag_add("material_line", start, end)
                continue

            if in_missions and is_nested_bullet:
                self.detail.tag_add("mission_line", start, end)
                continue

            if stripped.startswith("- ") and not in_blueprint_section:
                resource_match = re.match(r"^-\s+([^｜\n]+)", stripped)
                if resource_match:
                    name_text = resource_match.group(1)
                    line_start_index = f"{idx}.0+2c"
                    line_name_end = f"{idx}.0+{2 + len(name_text)}c"
                    try:
                        self.detail.tag_add("resource_name", line_start_index, line_name_end)
                    except Exception:
                        pass

        self.detail.configure(state="disabled")

    def _change_alpha(self, delta):
        alpha = max(0.35, min(1.0, float(self.settings.get("alpha", 0.95)) + delta))
        self.settings["alpha"] = round(alpha, 2)
        self.attributes("-alpha", alpha)
        self.toolbar_window.attributes("-alpha", min(1.0, alpha))
        self.alpha_label_top.configure(text=f"透明 {int(alpha*100)}%")
        self.status_var.set(f"透明度 {int(alpha*100)}%")
        self._schedule_save()

    def _change_font(self, delta):
        scale = max(0.8, min(2.0, float(self.settings.get("font_scale", 1.0)) + delta))
        self.settings["font_scale"] = round(scale, 2)
        self._apply_visuals()
        self.status_var.set(f"字體大小 {int(scale*100)}%")
        self._schedule_save()

    def _scale_window(self, factor):
        if self.settings.get("collapsed", False):
            self.settings["collapsed"] = False
            self._apply_collapsed()
        w = max(self.MIN_W, round(self.winfo_width() * factor))
        h = max(self.MIN_H, round(self.winfo_height() * factor))
        self.geometry(f"{w}x{h}+{self.winfo_x()}+{self.winfo_y()}")
        self.settings["width"] = w
        self.settings["height"] = h
        self._refresh_size_label()
        self._sync_toolbar_position()
        self._schedule_save()

    def _fmt_resource_list(self, items):
        if not items:
            return "- 無已確認資料"

        lines = []
        seen = set()

        for raw in items:
            if raw is None:
                continue

            txt = str(raw).strip()
            if not txt:
                continue

            name_part = txt
            desc_part = ""

            if " - " in txt:
                name_part, desc_part = txt.split(" - ", 1)

            name_part = str(name_part).strip()
            desc_part = str(desc_part).strip()

            zh = str(self.store.translate_resource_text(name_part) or "").strip()
            zh_only = zh

            if " / " in zh:
                parts = [p.strip() for p in zh.split(" / ", 1)]
                if len(parts) == 2 and parts[1].lower() == name_part.lower():
                    zh_only = parts[0].strip()

            if zh_only and zh_only.lower() != name_part.lower():
                display_name = f"{zh_only} / {name_part}"
            else:
                display_name = name_part

            dedup_key = (display_name.lower(), desc_part.lower())
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            if desc_part:
                lines.append(f"- {display_name}｜{desc_part}")
            else:
                lines.append(f"- {display_name}")

        return "\n".join(lines) if lines else "- 無已確認資料"

    def _format_modes(self, modes):
        mapping = {"ship": "船挖", "roc": "ROC", "hand": "手挖", "cave": "洞穴"}
        if not modes:
            return "-"
        return " / ".join(mapping.get(x.lower(), x) for x in modes)

    def _bool_text(self, value):
        if value is True:
            return "可能會出"
        if value is False:
            return "目前未確認"
        return "待補"

    def _map_level(self, value):
        return {"high": "高", "medium": "中", "low": "低"}.get(str(value).lower(), "待補")

    def _map_cave(self, value):
        return {"yes": "需要", "no": "不需要", "optional": "視情況"}.get(str(value).lower(), "待補")

    def _map_body_type(self, kind):
        return {"planet": "行星", "moon": "衛星", "asteroid_belt": "小行星帶", "asteroid_cluster": "小行星群", "ring": "環帶", "asteroid_world": "小行星世界"}.get(kind, kind)

    def _refresh_size_label(self):
        if self.settings.get("collapsed", False):
            edge = "右側" if self.settings.get("collapsed_edge") == "right" else "左側"
            self.size_label.configure(text=f"已收合｜吸附{edge}")
        else:
            self.size_label.configure(text=f"{self.winfo_width()} × {self.winfo_height()}")

    def _on_main_configure(self, _event=None):
        if self.settings.get("collapsed", False):
            return
        self.settings["x"] = int(self.winfo_x())
        self.settings["y"] = int(self.winfo_y())
        self.settings["width"] = int(max(self.MIN_W, self.winfo_width()))
        self.settings["height"] = int(max(self.MIN_H, self.winfo_height()))
        self._refresh_size_label()
        self._sync_toolbar_position()

    def _on_toolbar_configure(self, _event=None):
        if self._ignore_toolbar_config:
            return

    def _on_close(self):
        try:
            self._close_update_dialog()
        except Exception:
            pass
        try:
            self._save_settings()
        finally:
            try:
                self.toolbar_window.destroy()
            except Exception:
                pass
            self.destroy()


def main():
    safe = "--safe" in sys.argv
    app = OverlayApp(safe_mode=safe)
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        LOGGER.exception("啟動失敗: %s", exc)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("SC Mining Overlay 啟動失敗", "程式未能啟動，已寫入 logs/overlay.log")
            root.destroy()
        except Exception:
            pass
        raise
