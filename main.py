"""
Batch Translator — Dark Premium UI
Пакетный переводчик Word/TXT файлов через Google Translate / DeepL.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import queue
import sys
from pathlib import Path

_ROOT_TB = Path(__file__).resolve().parent
_AI_TB = _ROOT_TB
if str(_AI_TB) not in sys.path:
    sys.path.insert(0, str(_AI_TB))
from env_loader import load_env_stack

load_env_stack(_ROOT_TB)

from core import BatchTranslator, LANGUAGES, DEEPL_MAP

# ── Palette ──────────────────────────────────────────────────────────────
BG       = "#0F172A"   # slate-900
CARD     = "#1E293B"   # slate-800
CARD2    = "#263347"   # slightly lighter
INPUT_BG = "#0F172A"
ACCENT   = "#6366F1"   # indigo-500
HOVER    = "#4F46E5"   # indigo-600
ACCENT_L = "#A5B4FC"   # indigo-300
SEL_BG   = "#312E81"   # indigo-900
BORDER   = "#334155"   # slate-700
TEXT     = "#E2E8F0"   # slate-200
MUTED    = "#94A3B8"   # slate-400
DIM      = "#475569"   # slate-600
SUCCESS  = "#10B981"   # emerald-500
DANGER   = "#EF4444"   # red-500
LOG_BG   = "#020617"   # slate-950
CHK_ON   = "#6366F1"
CHK_OFF  = "#1E293B"

# ── Fonts ────────────────────────────────────────────────────────────────
FN = "Segoe UI"


# ── Custom widgets ───────────────────────────────────────────────────────

def _rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Draw a rounded rectangle on a Canvas."""
    pts = [
        x1+r, y1,  x2-r, y1,
        x2, y1,    x2, y1+r,
        x2, y2-r,  x2, y2,
        x2-r, y2,  x1+r, y2,
        x1, y2,    x1, y2-r,
        x1, y1+r,  x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


class PillBtn(tk.Frame):
    """Pill-shaped button drawn on canvas with hover animation."""

    def __init__(self, parent, text, command=None, w=180, h=40,
                 clr=ACCENT, clr_h=HOVER, fg="white", fsize=10, bold=True):
        bg = parent.cget("bg") if hasattr(parent, "cget") else BG
        super().__init__(parent, bg=bg, width=w, height=h)
        self.pack_propagate(False)

        self._t     = text
        self._cmd   = command
        self._clr   = clr
        self._clrh  = clr_h
        self._fg    = fg
        self._font  = (FN, fsize, "bold" if bold else "normal")
        self._bw    = w
        self._bh    = h
        self._enabled = True
        self._current_clr = clr

        self._cv = tk.Canvas(self, width=w, height=h, bg=bg,
                             highlightthickness=0, cursor="hand2")
        self._cv.pack(fill="both", expand=True)

        self._cv.bind("<Configure>",       lambda e: self._redraw(self._current_clr))
        self._cv.bind("<Enter>",           lambda e: self._hover(True))
        self._cv.bind("<Leave>",           lambda e: self._hover(False))
        self._cv.bind("<ButtonRelease-1>", lambda e: self._fire())
        self.bind("<ButtonRelease-1>",     lambda e: self._fire())

    def _redraw(self, clr):
        self._current_clr = clr
        self._cv.delete("all")
        w, h = self._bw, self._bh
        fill = clr if self._enabled else BORDER
        _rounded_rect(self._cv, 1, 1, w-1, h-1, h//2, fill=fill, outline="")
        self._cv.create_text(w//2, h//2, text=self._t,
                             fill=self._fg if self._enabled else DIM,
                             font=self._font)

    def _hover(self, on):
        if self._enabled:
            self._redraw(self._clrh if on else self._clr)

    def _fire(self):
        if self._enabled and self._cmd:
            self._cmd()

    def set_enabled(self, v: bool):
        self._enabled = v
        self._cv.config(cursor="hand2" if v else "arrow")
        self._redraw(self._clr)


class SmallBtn(tk.Label):
    """Lightweight text button (underline style)."""

    def __init__(self, parent, text, command=None, clr=ACCENT_L, **kw):
        super().__init__(parent, text=text, fg=clr, bg=parent.cget("bg"),
                         font=(FN, 9), cursor="hand2", **kw)
        self.bind("<Enter>", lambda e: self.config(fg=TEXT))
        self.bind("<Leave>", lambda e: self.config(fg=clr))
        self.bind("<Button-1>", lambda e: command() if command else None)


class CheckItem(tk.Frame):
    """Custom canvas checkbox with label."""

    def __init__(self, parent, text, var: tk.BooleanVar, on_change=None, **kw):
        super().__init__(parent, bg=CARD, **kw)
        self._var = var
        self._cb  = on_change

        self._cv = tk.Canvas(self, width=16, height=16, bg=CARD,
                             highlightthickness=0, cursor="hand2")
        self._cv.grid(row=0, column=0, padx=(4, 6), pady=3)

        self._lbl = tk.Label(self, text=text, bg=CARD, fg=DIM,
                              font=(FN, 9), cursor="hand2", anchor="w")
        self._lbl.grid(row=0, column=1, sticky="w")

        self._draw()
        for w in (self, self._cv, self._lbl):
            w.bind("<Button-1>", self._toggle)

    def _draw(self):
        self._cv.delete("all")
        on = self._var.get()
        fill = CHK_ON if on else CHK_OFF
        _rounded_rect(self._cv, 1, 1, 15, 15, 3, fill=fill, outline=BORDER)
        if on:
            self._cv.create_line(4, 8, 7, 11, fill="white", width=1.5, capstyle="round")
            self._cv.create_line(7, 11, 12, 5, fill="white", width=1.5, capstyle="round")
        self._lbl.config(fg=TEXT if on else DIM)

    def _toggle(self, _=None):
        self._var.set(not self._var.get())
        self._draw()
        if self._cb:
            self._cb()


class SectionTitle(tk.Frame):
    """Section header with accent left-border."""

    def __init__(self, parent, text, **kw):
        super().__init__(parent, bg=CARD, **kw)
        tk.Frame(self, width=3, bg=ACCENT).pack(side="left", fill="y", padx=(0, 10))
        tk.Label(self, text=text, bg=CARD, fg=TEXT,
                 font=(FN, 10, "bold")).pack(side="left")


class Card(tk.Frame):
    """Rounded card panel (simulated with padding)."""

    def __init__(self, parent, **kw):
        super().__init__(parent, bg=CARD, padx=16, pady=14, **kw)


# ── Main App ─────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Batch Translator")
        self.geometry("1280x860")
        self.minsize(1000, 700)
        self.configure(bg=BG)
        try:
            ico_path = Path(__file__).parent / "static" / "favicon.ico"
            if ico_path.exists():
                self.iconbitmap(default=str(ico_path))
        except Exception:
            pass

        self._files: list[str]            = []
        self._lang_vars: dict[str, tk.BooleanVar] = {}
        self._out_fmt   = tk.StringVar(value="docx")
        self._out_dir   = tk.StringVar(value=str(Path.home() / "Downloads" / "translations"))
        self._engine    = tk.StringVar(value="google_cloud")
        self._gc_creds  = tk.StringVar(value=os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", ""))
        self._deepl_key = tk.StringVar(value=os.environ.get("DEEPL_API_KEY", ""))
        self._running   = False
        self._q: queue.Queue = queue.Queue()

        self._build_styles()
        self._build_ui()
        self._poll_queue()

    # ── Styles ───────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TScrollbar", background=CARD2, troughcolor=CARD,
                    borderwidth=0, arrowsize=12, arrowcolor=DIM)
        s.map("TScrollbar", background=[("active", BORDER)])
        s.configure("Horizontal.TProgressbar",
                    troughcolor=CARD2, background=ACCENT,
                    thickness=8, borderwidth=0, lightcolor=ACCENT, darkcolor=ACCENT)
        s.configure("TCombobox", fieldbackground=INPUT_BG, background=INPUT_BG,
                    foreground=TEXT, selectbackground=SEL_BG,
                    insertcolor=TEXT, font=(FN, 9))
        s.map("TCombobox", fieldbackground=[("readonly", INPUT_BG)],
              foreground=[("readonly", TEXT)])
        s.configure("TEntry", fieldbackground=INPUT_BG, foreground=TEXT,
                    insertcolor=TEXT, font=(FN, 9), borderwidth=0)

    # ── UI skeleton ──────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, minsize=260)
        body.grid_columnconfigure(1, weight=3)
        body.grid_columnconfigure(2, minsize=300)
        body.grid_rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_center(body)
        self._build_langs_panel(body)

        self._build_bottom()

    # ── Header ───────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg="#1A1040", height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Logo dot + title
        logo_fr = tk.Frame(hdr, bg="#1A1040")
        logo_fr.pack(side="left", padx=22, pady=10)
        cv = tk.Canvas(logo_fr, width=28, height=28, bg="#1A1040", highlightthickness=0)
        cv.pack(side="left", padx=(0, 12))
        cv.create_oval(2, 2, 26, 26, fill=ACCENT, outline="")
        cv.create_text(14, 14, text="T", fill="white", font=(FN, 13, "bold"))
        tk.Label(logo_fr, text="Batch Translator", bg="#1A1040", fg=TEXT,
                 font=(FN, 14, "bold")).pack(side="left")
        tk.Label(logo_fr, text="·  52 языка", bg="#1A1040", fg=ACCENT_L,
                 font=(FN, 10)).pack(side="left", padx=10)

        # Live stats on the right
        stats = tk.Frame(hdr, bg="#1A1040")
        stats.pack(side="right", padx=22)
        self._stat_files = self._stat_chip(stats, "📄", "0 файлов")
        self._stat_langs = self._stat_chip(stats, "🌐", "0 языков")
        self._stat_total = self._stat_chip(stats, "⚡", "0 переводов")

    def _stat_chip(self, parent, icon, text):
        fr = tk.Frame(parent, bg=SEL_BG, padx=12, pady=5)
        fr.pack(side="left", padx=6)
        tk.Label(fr, text=icon, bg=SEL_BG, font=(FN, 9)).pack(side="left")
        lbl = tk.Label(fr, text=text, bg=SEL_BG, fg=ACCENT_L, font=(FN, 9, "bold"))
        lbl.pack(side="left", padx=(4, 0))
        return lbl

    def _update_stats(self):
        nf = len(self._files)
        nl = sum(1 for v in self._lang_vars.values() if v.get())
        self._stat_files.config(text=f"{nf} файл{'ов' if nf!=1 else ''}")
        self._stat_langs.config(text=f"{nl} язык{'ов' if nl not in (1,) else ''}")
        self._stat_total.config(text=f"{nf*nl} переводов")

    # ── Left Sidebar: Settings ────────────────────────────────────────────
    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=CARD, padx=18, pady=18)
        sb.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)

        # ── Engine
        SectionTitle(sb, "Движок перевода").pack(anchor="w", pady=(0, 10))
        engines = [
            ("Google Cloud API",         "google_cloud"),
            ("DeepL API",                "deepl"),
        ]
        for lbl, val in engines:
            self._radio(sb, lbl, self._engine, val, self._toggle_creds)

        # Credentials
        self._creds_box = tk.Frame(sb, bg=CARD)
        self._creds_box.pack(fill="x", pady=(8, 0))
        tk.Label(self._creds_box, text="credentials.json (Google Cloud)",
                 bg=CARD, fg=DIM, font=(FN, 8)).pack(anchor="w")
        gc_row = tk.Frame(self._creds_box, bg=CARD)
        gc_row.pack(fill="x", pady=(2, 6))
        self._gc_entry = self._entry(gc_row, self._gc_creds)
        self._gc_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        SmallBtn(gc_row, "…", lambda: self._pick_file(self._gc_creds)).pack(side="left")

        tk.Label(self._creds_box, text="DeepL API Key",
                 bg=CARD, fg=DIM, font=(FN, 8)).pack(anchor="w")
        self._dl_entry = self._entry(self._creds_box, self._deepl_key, show="•")
        self._dl_entry.pack(fill="x", pady=(2, 0))
        self._toggle_creds()

        self._hsep(sb)

        # ── Format
        SectionTitle(sb, "Формат вывода").pack(anchor="w", pady=(0, 10))
        for lbl, val in [("Word  .docx", "docx"), ("Текст  .txt", "txt")]:
            self._radio(sb, lbl, self._out_fmt, val)

        self._hsep(sb)

        # ── Source language
        SectionTitle(sb, "Язык оригинала").pack(anchor="w", pady=(0, 8))
        src_opts = [("Определить автоматически", "auto")] + list(LANGUAGES)
        self._src_labels = {n: c for n, c in src_opts}
        self._src_combo = ttk.Combobox(sb, values=[n for n, _ in src_opts],
                                        state="readonly", font=(FN, 9))
        self._src_combo.set("Определить автоматически")
        self._src_combo.pack(fill="x", ipady=4)

        self._hsep(sb)

        # ── Output folder
        SectionTitle(sb, "Папка сохранения").pack(anchor="w", pady=(0, 8))
        dir_row = tk.Frame(sb, bg=CARD)
        dir_row.pack(fill="x")
        self._entry(dir_row, self._out_dir).pack(side="left", fill="x", expand=True, padx=(0, 4))
        SmallBtn(dir_row, "…", self._browse_dir).pack(side="left")
        SmallBtn(sb, "Открыть папку →", self._open_output,
                 clr=MUTED).pack(anchor="w", pady=(8, 0))

        tk.Label(sb,
                 text="output/\n  es/  файл_es.docx\n  en/  файл_en.docx",
                 bg=CARD, fg=DIM, font=("Consolas", 8), justify="left"
                 ).pack(anchor="w", pady=(10, 0))

    # ── Center: Files ────────────────────────────────────────────────────
    def _build_center(self, parent):
        ctr = tk.Frame(parent, bg=BG)
        ctr.grid(row=0, column=1, sticky="nsew", padx=4, pady=8)
        ctr.grid_rowconfigure(1, weight=1)
        ctr.grid_columnconfigure(0, weight=1)

        # Drop zone
        dz = tk.Frame(ctr, bg=CARD2, height=110)
        dz.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        dz.grid_propagate(False)
        dz.bind("<Button-1>", lambda e: self._add_files())

        dz_cv = tk.Canvas(dz, bg=CARD2, highlightthickness=0)
        dz_cv.pack(fill="both", expand=True, padx=2, pady=2)
        dz_cv.bind("<Button-1>", lambda e: self._add_files())
        dz_cv.bind("<Configure>", lambda e: self._draw_dropzone(dz_cv))
        self._dz_cv = dz_cv

        # File list card
        fc = Card(ctr)
        fc.grid(row=1, column=0, sticky="nsew")
        fc.grid_rowconfigure(1, weight=1)
        fc.grid_columnconfigure(0, weight=1)

        hdr_row = tk.Frame(fc, bg=CARD)
        hdr_row.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        SectionTitle(hdr_row, "Файлы для перевода").pack(side="left")
        self._file_lbl = tk.Label(hdr_row, text="нет файлов", bg=CARD, fg=DIM, font=(FN, 9))
        self._file_lbl.pack(side="right")

        lb_fr = tk.Frame(fc, bg=CARD)
        lb_fr.grid(row=1, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(lb_fr, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._listbox = tk.Listbox(
            lb_fr, yscrollcommand=vsb.set, selectmode="extended",
            bg=CARD2, fg=TEXT, selectbackground=SEL_BG, selectforeground=TEXT,
            font=(FN, 10), relief="flat", borderwidth=0,
            highlightthickness=0, activestyle="none",
            cursor="arrow")
        self._listbox.pack(fill="both", expand=True)
        vsb.config(command=self._listbox.yview)

        btn_row = tk.Frame(fc, bg=CARD)
        btn_row.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        SmallBtn(btn_row, "＋ Добавить файлы", self._add_files, clr=ACCENT_L).pack(side="left")
        SmallBtn(btn_row, "✕ Удалить", self._remove_files, clr=DIM).pack(side="left", padx=16)
        SmallBtn(btn_row, "Очистить всё", self._clear_files, clr=DIM).pack(side="left")

    def _draw_dropzone(self, cv):
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 10: return
        _rounded_rect(cv, 4, 4, w-4, h-4, 10,
                      fill=CARD2, outline=BORDER)
        # Dashed border simulation via dots
        for x in range(16, w-8, 12):
            cv.create_rectangle(x, 4, x+6, 6, fill=BORDER, outline="")
            cv.create_rectangle(x, h-6, x+6, h-4, fill=BORDER, outline="")
        for y in range(16, h-8, 12):
            cv.create_rectangle(4, y, 6, y+6, fill=BORDER, outline="")
            cv.create_rectangle(w-6, y, w-4, y+6, fill=BORDER, outline="")
        # Icon + text
        cy = h // 2
        cv.create_text(w//2, cy - 14, text="📂",
                       font=(FN, 20), fill=ACCENT_L)
        cv.create_text(w//2, cy + 18,
                       text="Нажмите, чтобы добавить файлы  (.docx · .txt)",
                       font=(FN, 10), fill=MUTED)

    # ── Right: Languages ─────────────────────────────────────────────────
    def _build_langs_panel(self, parent):
        lp = Card(parent)
        lp.grid(row=0, column=2, sticky="nsew", padx=(4, 8), pady=8)
        lp.grid_rowconfigure(2, weight=1)
        lp.grid_columnconfigure(0, weight=1)

        # Header row
        hdr = tk.Frame(lp, bg=CARD)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        SectionTitle(hdr, "Языки перевода").pack(side="left")

        # Count badge
        self._lang_badge = tk.Canvas(hdr, width=40, height=22, bg=CARD, highlightthickness=0)
        self._lang_badge.pack(side="right")
        self._update_lang_badge(0)

        # Quick select buttons
        qs = tk.Frame(lp, bg=CARD)
        qs.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        SmallBtn(qs, "Выбрать все",  self._sel_all).pack(side="left")
        SmallBtn(qs, "Снять все", self._sel_none, clr=DIM).pack(side="left", padx=12)

        # Scrollable language list
        outer = tk.Frame(lp, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        outer.grid(row=2, column=0, sticky="nsew")

        canvas = tk.Canvas(outer, bg=CARD, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scroll_f = tk.Frame(canvas, bg=CARD)
        scroll_f.bind("<Configure>",
                      lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_f, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # 2-column grid of checkboxes
        scroll_f.grid_columnconfigure(0, weight=1)
        scroll_f.grid_columnconfigure(1, weight=1)
        for idx, (name, code) in enumerate(LANGUAGES):
            var = tk.BooleanVar()
            self._lang_vars[code] = var
            ci = CheckItem(scroll_f, name, var, self._on_lang_change)
            ci.grid(row=idx // 2, column=idx % 2, sticky="ew", padx=2, pady=1)

        canvas.bind("<Enter>", lambda e: canvas.bind_all(
            "<MouseWheel>", lambda ev: canvas.yview_scroll(-1*(ev.delta//120), "units")))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

    def _update_lang_badge(self, n):
        self._lang_badge.delete("all")
        _rounded_rect(self._lang_badge, 1, 1, 39, 21, 10,
                      fill=SEL_BG if n > 0 else CARD2, outline="")
        self._lang_badge.create_text(20, 11, text=str(n),
                                     fill=ACCENT_L if n > 0 else DIM,
                                     font=(FN, 9, "bold"))

    # ── Bottom: progress + log ───────────────────────────────────────────
    def _build_bottom(self):
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=8, pady=(0, 8))

        # Progress card
        pc = Card(bottom)
        pc.pack(fill="x", pady=(0, 6))

        top_row = tk.Frame(pc, bg=CARD)
        top_row.pack(fill="x", pady=(0, 6))

        self._prog_lbl = tk.Label(top_row, text="Готов к работе",
                                   bg=CARD, fg=TEXT, font=(FN, 10))
        self._prog_lbl.pack(side="left")

        right_stats = tk.Frame(top_row, bg=CARD)
        right_stats.pack(side="right")
        self._eta_lbl = tk.Label(right_stats, text="", bg=CARD, fg=DIM, font=(FN, 9))
        self._eta_lbl.pack(side="left", padx=(0, 16))
        self._pct_lbl = tk.Label(right_stats, text="", bg=CARD, fg=ACCENT_L,
                                  font=(FN, 11, "bold"))
        self._pct_lbl.pack(side="left")

        # Custom progress bar (canvas)
        self._pbar_cv = tk.Canvas(pc, height=10, bg=CARD2, highlightthickness=0)
        self._pbar_cv.pack(fill="x", ipady=0)
        self._pbar_cv.bind("<Configure>", lambda e: self._draw_pbar(0, 1))
        self._pbar_total = 1
        self._pbar_done  = 0

        # Button row
        btn_row = tk.Frame(pc, bg=CARD)
        btn_row.pack(fill="x", pady=(12, 0))

        self._start_btn = PillBtn(btn_row, "▶  Начать перевод",
                                  command=self._start, w=200, h=42,
                                  clr=ACCENT, clr_h=HOVER, fsize=11)
        self._start_btn.pack(side="left", padx=(0, 10))

        self._stop_btn = PillBtn(btn_row, "■  Остановить",
                                 command=self._stop, w=160, h=42,
                                 clr="#7F1D1D", clr_h=DANGER, fsize=11)
        self._stop_btn.pack(side="left")
        self._stop_btn.set_enabled(False)

        # Log
        log_card = tk.Frame(bottom, bg=LOG_BG, padx=12, pady=10)
        log_card.pack(fill="x")

        log_hdr = tk.Frame(log_card, bg=LOG_BG)
        log_hdr.pack(fill="x", pady=(0, 6))
        tk.Label(log_hdr, text="ЛОГ", bg=LOG_BG, fg=DIM, font=(FN, 8, "bold")).pack(side="left")
        SmallBtn(log_hdr, "Очистить", self._clear_log, clr=DIM).pack(side="right")

        self._log = tk.Text(log_card, height=7, font=("Cascadia Code", 9),
                            bg=LOG_BG, fg="#ABB2BF", relief="flat",
                            wrap="word", state="disabled", padx=4,
                            selectbackground=SEL_BG, insertbackground=TEXT,
                            highlightthickness=0)
        self._log.pack(fill="both")
        self._log.tag_config("ok",   foreground="#4EC9B0")
        self._log.tag_config("err",  foreground="#F44747")
        self._log.tag_config("info", foreground="#569CD6")
        self._log.tag_config("warn", foreground="#CE9178")

    def _draw_pbar(self, done, total):
        self._pbar_cv.delete("all")
        w = self._pbar_cv.winfo_width()
        if w < 10: return
        h = 10
        _rounded_rect(self._pbar_cv, 0, 0, w, h, 5, fill=CARD2, outline="")
        if done > 0 and total > 0:
            fill_w = max(int(w * done / total), 10)
            _rounded_rect(self._pbar_cv, 0, 0, fill_w, h, 5, fill=ACCENT, outline="")

    # ── Actions: files ───────────────────────────────────────────────────
    def _add_files(self):
        paths = filedialog.askopenfilenames(
            title="Выберите файлы",
            filetypes=[("Документы", "*.docx *.txt"), ("Word", "*.docx"),
                       ("Text", "*.txt"), ("Все", "*.*")])
        added = 0
        for fp in paths:
            if fp not in self._files:
                if Path(fp).suffix.lower() == ".doc":
                    self._log_write(f"⚠  {Path(fp).name}: .doc не поддерживается — используйте .docx", "warn")
                    continue
                self._files.append(fp)
                self._listbox.insert("end", f"  {Path(fp).name}")
                added += 1
        n = len(self._files)
        self._file_lbl.config(text=f"{n} файл{'ов' if n != 1 else ''}")
        if added:
            self._log_write(f"+ Добавлено файлов: {added}", "info")
        self._update_stats()

    def _remove_files(self):
        for i in reversed(self._listbox.curselection()):
            self._listbox.delete(i)
            self._files.pop(i)
        n = len(self._files)
        self._file_lbl.config(text=f"{n} файл{'ов' if n != 1 else ''}" if n else "нет файлов")
        self._update_stats()

    def _clear_files(self):
        self._listbox.delete(0, "end")
        self._files.clear()
        self._file_lbl.config(text="нет файлов")
        self._update_stats()

    # ── Actions: languages ───────────────────────────────────────────────
    def _sel_all(self):
        for v in self._lang_vars.values(): v.set(True)
        self._on_lang_change()
        # Redraw all checkitems
        for w in self._iter_checkitems():
            w._draw()

    def _sel_none(self):
        for v in self._lang_vars.values(): v.set(False)
        self._on_lang_change()
        for w in self._iter_checkitems():
            w._draw()

    def _iter_checkitems(self):
        for widget in self.winfo_children():
            yield from self._find_checkitems(widget)

    def _find_checkitems(self, parent):
        for w in parent.winfo_children():
            if isinstance(w, CheckItem):
                yield w
            else:
                yield from self._find_checkitems(w)

    def _on_lang_change(self):
        n = sum(1 for v in self._lang_vars.values() if v.get())
        self._update_lang_badge(n)
        self._update_stats()

    # ── Actions: settings ────────────────────────────────────────────────
    def _toggle_creds(self):
        e = self._engine.get()
        self._gc_entry.config(state="normal" if e == "google_cloud" else "disabled")
        self._dl_entry.config(state="normal" if e == "deepl" else "disabled")

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self._out_dir.get())
        if d: self._out_dir.set(d)

    def _pick_file(self, var):
        fp = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("Все", "*.*")])
        if fp: var.set(fp)

    def _open_output(self):
        path = self._out_dir.get()
        Path(path).mkdir(parents=True, exist_ok=True)
        os.startfile(path)

    # ── Translation ──────────────────────────────────────────────────────
    def _start(self):
        langs = [c for c, v in self._lang_vars.items() if v.get()]
        if not self._files:
            messagebox.showwarning("Нет файлов", "Добавьте файлы для перевода")
            return
        if not langs:
            messagebox.showwarning("Нет языков", "Выберите хотя бы один язык")
            return

        src_label = self._src_combo.get()
        src_code  = self._src_labels.get(src_label, "auto")
        if src_code == "auto": src_code = None

        engine  = self._engine.get()
        gc_cred = self._gc_creds.get() or None
        dl_key  = self._deepl_key.get() or None
        fmt     = self._out_fmt.get()
        out_dir = self._out_dir.get()

        total = len(self._files) * len(langs)
        self._pbar_total = total
        self._pbar_done  = 0

        self._log_write(
            f"▶  Запуск:  {len(self._files)} файл(ов) × {len(langs)} яз. = {total} переводов  "
            f"[{engine} · {fmt}]", "info")

        self._running = True
        self._start_btn.set_enabled(False)
        self._stop_btn.set_enabled(True)
        self._draw_pbar(0, total)

        threading.Thread(
            target=self._worker,
            args=(list(self._files), langs, engine, gc_cred, dl_key, fmt, out_dir, src_code),
            daemon=True).start()

    def _stop(self):
        self._running = False
        self._log_write("⏹  Остановка...", "warn")

    def _worker(self, files, langs, engine, gc_creds, dl_key, fmt, out_dir, src):
        import time as _t
        self._q.put(("log", "⚙  Инициализация движка...", "info"))
        try:
            tr = BatchTranslator(engine=engine, gc_credentials=gc_creds, deepl_key=dl_key)
            tr.init()
            self._q.put(("log", "✓  Движок готов", "ok"))
        except Exception as e:
            self._q.put(("log", f"✗  Ошибка инициализации: {e}", "err"))
            self._q.put(("done",))
            return

        done = errors = 0
        total = len(files) * len(langs)
        t0 = _t.time()

        for fp in files:
            if not self._running: break
            for lc in langs:
                if not self._running: break
                name = Path(fp).name
                try:
                    tr.translate_file(fp, lc, fmt, out_dir, src)
                    done += 1
                    elapsed = _t.time() - t0
                    per_item = elapsed / done
                    eta_s = int(per_item * (total - done))
                    eta = f"{eta_s//60}м {eta_s%60}с" if eta_s > 60 else f"{eta_s}с"
                    self._q.put(("progress", done, total, eta,
                                 f"✓  {name}  →  {lc}", "ok"))
                except Exception as e:
                    errors += 1
                    done += 1
                    self._q.put(("progress", done, total, "",
                                 f"✗  {name} [{lc}] — {e}", "err"))

        tag = "ok" if errors == 0 else "warn"
        self._q.put(("log",
                     f"{'✅' if not errors else '⚠'}  Готово: {done-errors} успешно, {errors} ошибок",
                     tag))
        self._q.put(("done",))

    # ── Queue polling ────────────────────────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                msg = self._q.get_nowait()
                if msg[0] == "progress":
                    _, done, total, eta, text, tag = msg
                    pct = int(done / total * 100)
                    self._draw_pbar(done, total)
                    self._prog_lbl.config(text=f"{done} / {total}")
                    self._pct_lbl.config(text=f"{pct}%")
                    self._eta_lbl.config(text=f"~{eta}" if eta else "")
                    self._log_write(text, tag)
                elif msg[0] == "log":
                    self._log_write(msg[1], msg[2])
                elif msg[0] == "done":
                    self._running = False
                    self._start_btn.set_enabled(True)
                    self._stop_btn.set_enabled(False)
                    self._prog_lbl.config(text="Завершено")
                    self._eta_lbl.config(text="")
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _log_write(self, text: str, tag: str = "info"):
        self._log.config(state="normal")
        self._log.insert("end", text + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    # ── Helper builders ──────────────────────────────────────────────────
    def _radio(self, parent, text, var, value, cmd=None):
        fr = tk.Frame(parent, bg=CARD, cursor="hand2")
        fr.pack(anchor="w", pady=2)
        cv = tk.Canvas(fr, width=16, height=16, bg=CARD, highlightthickness=0)
        cv.pack(side="left", padx=(0, 8))
        lbl = tk.Label(fr, text=text, bg=CARD, fg=DIM, font=(FN, 9), cursor="hand2")
        lbl.pack(side="left")

        def draw():
            cv.delete("all")
            on = var.get() == value
            cv.create_oval(1, 1, 15, 15, fill=CARD2, outline=ACCENT if on else BORDER)
            if on:
                cv.create_oval(5, 5, 11, 11, fill=ACCENT, outline="")
            lbl.config(fg=TEXT if on else DIM)

        def toggle(_=None):
            var.set(value)
            if cmd: cmd()
            # Redraw all radios in parent
            for w in parent.winfo_children():
                if hasattr(w, "_radio_draw"):
                    w._radio_draw()

        draw()
        fr._radio_draw = draw
        for w in (fr, cv, lbl):
            w.bind("<Button-1>", toggle)
        var.trace_add("write", lambda *_: draw())

    def _entry(self, parent, var=None, show=None):
        e = tk.Entry(parent, bg=INPUT_BG, fg=TEXT, relief="flat",
                     font=(FN, 9), insertbackground=TEXT,
                     highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=ACCENT,
                     textvariable=var)
        if show:
            e.config(show=show)
        return e

    def _hsep(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", pady=14)


if __name__ == "__main__":
    App().mainloop()
