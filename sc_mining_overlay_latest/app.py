from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
import tkinter as tk
import tkinter.font as tkfont
from tkinter import messagebox

from core.data_store import MiningDataStore
from core.search import MiningSearch

BASE_DIR = Path(__file__).resolve().parent
SETTINGS_PATH = BASE_DIR / "config" / "overlay_settings.json"
DATA_PATH = BASE_DIR / "data" / "sc_mining_dataset_latest.json"
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

        self.title("SC Mining Overlay")
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

        self.toolbar_window = tk.Toplevel(self)
        self.toolbar_window.withdraw()
        self.toolbar_window.title("SC Mining Toolbar")
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
        self.title_label = tk.Label(self.titlebar, text="SC 採礦 製作 查詢系統 浮動視窗", bg="#10202c", fg="#d9f4ff", font=self.title_font)
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

        info_row = tk.Frame(self.content, bg="#0b131b")
        info_row.pack(fill="x", padx=12, pady=(8, 2))
        dataset_name = self.meta.get("dataset_name", "Mining Dataset")
        version = self.meta.get("version", "-")
        tk.Label(info_row, text=f"資料：{dataset_name} {version}", bg="#0b131b", fg="#85a8bb", font=self.small_font).pack(side="left")
        self.alpha_label_top = tk.Label(info_row, text="", bg="#0b131b", fg="#85a8bb", font=self.small_font)
        self.alpha_label_top.pack(side="right")

        search_row = tk.Frame(self.content, bg="#0b131b")
        search_row.pack(fill="x", padx=12, pady=(2, 0))
        self.query_var = tk.StringVar(value=self.settings.get("last_query", ""))
        self.query_var.trace_add("write", self._on_query_change)
        self.search_entry = tk.Entry(search_row, textvariable=self.query_var, font=self.body_font,
                                     bg="#081118", fg="#e6fbff", insertbackground="#9fefff",
                                     relief="flat", bd=8, highlightthickness=1,
                                     highlightbackground="#2e5a72", highlightcolor="#7fd8ff")
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Down>", self._suggest_down)
        self.search_entry.bind("<Up>", self._suggest_up)
        self.search_entry.bind("<Return>", self._suggest_apply)
        self.search_entry.bind("<Escape>", lambda e: self._hide_suggestions())
        self._mk_btn(search_row, "清", self._clear_query, width=3).pack(side="left", padx=(6,0))

        self.suggest_frame = tk.Frame(self.content, bg="#10202c", highlightthickness=1, highlightbackground="#3e708d")
        self.suggest_list = tk.Listbox(self.suggest_frame, bg="#081118", fg="#e6fbff",
                                       selectbackground="#20455c", selectforeground="#ffffff",
                                       bd=0, relief="flat", highlightthickness=0, activestyle="none",
                                       font=self.body_font, exportselection=False, height=8)
        self.suggest_list.pack(fill="both", expand=True)
        self.suggest_list.bind("<ButtonRelease-1>", self._click_suggestion)
        self.suggest_list.bind("<Return>", self._suggest_enter)

        self.recent_label = tk.Label(self.content, text="上方聯想先顯示礦物；點選後左邊列出關聯區域，右邊顯示地圖/礦點資訊。",
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

        tk.Label(self.right_panel, text="地圖 / 礦點資訊", bg="#0f1b25", fg="#d9f4ff", font=self.title_font).pack(fill="x", padx=8, pady=(8,6))
        self.risk_banner = tk.Label(self.right_panel, text="風險：待判定", bg="#23465a", fg="#e6fbff", font=self.hud_font, anchor="w", padx=8, pady=4)
        self.risk_banner.pack(fill="x", padx=8, pady=(0,6))
        self.detail = tk.Text(self.right_panel, wrap="word", bg="#081118", fg="#e6fbff",
                              bd=0, relief="flat", highlightthickness=1, highlightbackground="#2e5a72",
                              font=self.body_font, padx=8, pady=8)
        self.detail.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.detail.tag_configure("item_title",
                                  foreground="#C6FFAC",
                                  background="#132514",
                                  font=(self.ui_font_name, 14, "bold"))
        self.detail.tag_configure("blueprint_name",
                                  foreground="#A8FF9E",
                                  background="#102117",
                                  font=(self.ui_font_name, 13, "bold"))
        self.detail.tag_configure("section_header",
                                  foreground="#8ED8FF",
                                  font=(self.ui_font_name, 11, "bold"))
        self.detail.tag_configure("material_line",
                                  foreground="#8EE6FF")
        self.detail.tag_configure("mission_line",
                                  foreground="#FFD98E")
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
        self.body_font.configure(size=max(10, round(11 * scale)))
        self.small_font.configure(size=max(8, round(9 * scale)))
        self.title_font.configure(size=max(11, round(12 * scale)))
        self.button_font.configure(size=max(8, round(9 * scale)))
        if hasattr(self, "hud_font"):
            self.hud_font.configure(size=max(9, round(10 * scale)))
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
        self._refresh_results(immediate=False)

    def _refresh_results(self, immediate=False):
        if self._query_job is not None:
            self.after_cancel(self._query_job)
            self._query_job = None
        if immediate:
            self._run_search()
        else:
            self._query_job = self.after(70, self._run_search)

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
            self._set_detail("請先從上方聯想選礦物、圖紙或地點。")
            self.status_var.set("可從最近紀錄、礦物、圖紙或地點聯想中選擇")
            return

        resource_candidates = self.store.find_resource_candidates(query, limit=10)
        item_candidates = self.store.find_item_candidates(query, limit=10)

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

        if resource_candidates or item_candidates:
            self._result_rows = []
            self.result_list.delete(0, tk.END)
            self._set_risk_banner(None)
            self._set_detail("請先從上方聯想中選擇正確礦物、圖紙或地點，之後才會顯示關聯資訊。")
            self.status_var.set(f"找到 {len(resource_candidates)} 個礦物候選、{len(item_candidates)} 個圖紙候選，請先選擇")
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
            prefix = "最近" if item["kind"] == "recent" else ("礦物" if item["kind"] == "resource" else ("圖紙" if item["kind"] == "item" else "地點"))
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
        self._suppress_query = True
        self.query_var.set(item["query"])
        self._suppress_query = False
        self._remember_query(item["query"])
        self._refresh_results(immediate=True)
        # 選到礦物後，自動顯示必須跟手動點左側清單完全一致
        if self._result_rows:
            self._show_detail_for_result(self._result_rows[0], resource_item=self._selected_resource)

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
        # 搜尋圖紙時，只顯示該圖紙本身，不再把材料拆成左側結果清單
        if row.get("kind") == "scc_item":
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
        lines.append("地表：" + self.store.bilingualize_known_text(self._fmt_resource_list(mining.get("known_surface_resources", []))))
        lines.append("洞穴：" + self.store.bilingualize_known_text(self._fmt_resource_list(mining.get("known_cave_resources", []))))
        lines.append("太空／小行星：" + self.store.bilingualize_known_text(self._fmt_resource_list(mining.get("known_asteroid_resources", []))))
        if blueprint_text:
            lines.append("")
            lines.append("—— 製作圖紙 ——")
            lines.append(blueprint_text)
        self._set_risk_banner(body)
        self._set_detail("\n".join(lines))

    def _show_location_detail(self, row, resource_item=None):
        lines = []
        if resource_item:
            lines.append(self.store.resource_summary_text(resource_item))
            lines.append("")
            lines.append("—— 關聯地點 ——")
        lines.append(f'【{row.get("title","-")}】')
        lines.append(f'所屬：{row.get("subtitle","-")}')
        mode = row.get("mode")
        if mode:
            lines.append(f'採集模式：{self.store.normalize_mode(mode)}')
        details = row.get("details")
        if details:
            lines.append("")
            lines.append("關聯摘要：")
            lines.append(self.store.bilingualize_known_text(details))
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

    def _set_risk_banner(self, body=None):
        if not body:
            self.risk_banner.configure(text="風險：待判定", bg="#23465a", fg="#e6fbff")
            return
        level, color, msg = self._body_risk(body)
        self.risk_banner.configure(text=f"風險：{level}｜{msg}", bg=color, fg="#f5fbff")

    def _set_detail(self, text):
        self.detail.configure(state="normal")
        self.detail.delete("1.0", tk.END)
        self.detail.insert("1.0", text)

        lines = text.splitlines()
        in_blueprint_section = False
        in_materials = False
        in_missions = False

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            start = f"{idx}.0"
            end = f"{idx}.end"

            if idx == 1 and stripped.startswith("【") and stripped.endswith("】"):
                self.detail.tag_add("item_title", start, end)

            if stripped in {"關聯製作圖紙：", "—— 製作圖紙 ——"}:
                in_blueprint_section = True
                in_materials = False
                in_missions = False
                self.detail.tag_add("section_header", start, end)
                continue

            if stripped in {"材料：", "獲取任務："}:
                self.detail.tag_add("section_header", start, end)
                in_materials = stripped == "材料："
                in_missions = stripped == "獲取任務："
                continue

            if stripped.startswith("分類：") or stripped.startswith("材料數：") or stripped.startswith("獲取任務數："):
                self.detail.tag_add("section_header", start, end)

            if in_blueprint_section and stripped.startswith("- "):
                self.detail.tag_add("blueprint_name", start, end)

            if in_materials:
                if stripped.startswith("-") or stripped.startswith("•") or stripped.startswith("－") or stripped.startswith("• "):
                    self.detail.tag_add("material_line", start, end)
                elif stripped.startswith("  - "):
                    self.detail.tag_add("material_line", start, end)
                elif not stripped:
                    in_materials = False

            if in_missions:
                if stripped.startswith("-") or stripped.startswith("•") or stripped.startswith("－"):
                    self.detail.tag_add("mission_line", start, end)
                elif stripped.startswith("  - "):
                    self.detail.tag_add("mission_line", start, end)
                elif not stripped:
                    in_missions = False

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
            return "-"
        return "；".join(self.store.translate_resource_text(x) for x in items[:10])

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
