"""
AstroAnalyzer – GUI
Tkinter-basierte Desktop-App zur Analyse von Astrofotografie-Masters
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading, os, sys, queue
from pathlib import Path

# Sicherstellen, dass das Projektverzeichnis im Pfad ist
sys.path.insert(0, str(Path(__file__).parent))


# ── Farben & Konstanten ────────────────────────────────────────────────────────

DARK_BG    = "#1e1e2e"
PANEL_BG   = "#2a2a3d"
ACCENT     = "#7c9ad6"
ACCENT2    = "#a6d6a6"
TEXT_FG    = "#e0e0f0"
LABEL_FG   = "#9090b0"
GREEN      = "#6bcb6b"
YELLOW     = "#f0c040"
RED        = "#e06060"
ENTRY_BG   = "#30304a"
BUTTON_BG  = "#3a4a7a"
BUTTON_FG  = "#e8e8ff"

FONT_TITLE = ("Helvetica", 28, "bold")
FONT_H2    = ("Helvetica", 20, "bold")
FONT_BODY  = ("Helvetica", 17)
FONT_MONO  = ("Courier", 15)
FONT_HINT  = ("Helvetica", 13)


class AstroAnalyzerApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("AstroAnalyzer")
        self.geometry("1100x820")
        self.configure(bg=DARK_BG)
        self.resizable(True, True)

        # State
        self.progress_queue = queue.Queue()
        self.analysis_running = False
        self.results = {}
        self.multi_lights: list[tuple[str, str]] = []  # [(filter_name, path), ...]

        # Datei-Variablen
        self.var_light    = tk.StringVar()
        self.var_dark     = tk.StringVar()
        self.var_flat     = tk.StringVar()
        self.var_flatdark = tk.StringVar()
        self.var_output   = tk.StringVar()
        self.var_obsidian = tk.StringVar()

        # Konfig
        self.var_n_subs    = tk.IntVar(value=0)
        self.var_fmt_md    = tk.BooleanVar(value=True)
        self.var_fmt_docx  = tk.BooleanVar(value=True)
        self.var_fmt_csv   = tk.BooleanVar(value=True)
        self.var_fmt_png   = tk.BooleanVar(value=True)
        self.var_fmt_js    = tk.BooleanVar(value=True)

        self.var_mod = {i: tk.BooleanVar(value=True) for i in range(1, 6)}

        self._build_styles()
        self._build_menu()
        self._build_ui()
        self._poll_queue()

    # ── Styles ─────────────────────────────────────────────────────────────

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TNotebook", background=DARK_BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=PANEL_BG, foreground=TEXT_FG,
                        padding=[16, 6], font=FONT_BODY)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT)],
                  foreground=[("selected", "#ffffff")])
        style.configure("TFrame", background=DARK_BG)
        style.configure("Panel.TFrame", background=PANEL_BG)
        style.configure("TLabel", background=DARK_BG, foreground=TEXT_FG,
                        font=FONT_BODY)
        style.configure("Panel.TLabel", background=PANEL_BG, foreground=TEXT_FG,
                        font=FONT_BODY)
        style.configure("TEntry", fieldbackground=ENTRY_BG, foreground=TEXT_FG,
                        insertcolor=TEXT_FG)
        style.configure("TCheckbutton", background=PANEL_BG, foreground=TEXT_FG,
                        font=FONT_BODY)
        style.configure("TProgressbar", troughcolor=PANEL_BG,
                        background=ACCENT, thickness=18)
        style.configure("Run.TButton",
                        background=ACCENT, foreground="#ffffff",
                        font=("Helvetica", 12, "bold"), padding=10)
        style.map("Run.TButton",
                  background=[("active", "#5a7ab6"), ("disabled", "#404060")])
        style.configure("TButton",
                        background=BUTTON_BG, foreground=BUTTON_FG,
                        font=FONT_BODY, padding=5)
        style.map("TButton", background=[("active", "#4a5a8a")])

    # ── Menü ───────────────────────────────────────────────────────────────

    def _build_menu(self):
        bar = tk.Menu(self, bg=PANEL_BG, fg=TEXT_FG, tearoff=0)
        self.config(menu=bar)
        file_m = tk.Menu(bar, tearoff=0, bg=PANEL_BG, fg=TEXT_FG)
        file_m.add_command(label="Light-Master öffnen …", command=self._browse_light)
        file_m.add_separator()
        file_m.add_command(label="Beenden", command=self.quit)
        bar.add_cascade(label="Datei", menu=file_m)
        help_m = tk.Menu(bar, tearoff=0, bg=PANEL_BG, fg=TEXT_FG)
        help_m.add_command(label="Über AstroAnalyzer", command=self._about)
        bar.add_cascade(label="Hilfe", menu=help_m)

    # ── Haupt-UI ───────────────────────────────────────────────────────────

    def _build_ui(self):
        # Titelzeile
        hdr = tk.Frame(self, bg=DARK_BG, pady=10)
        hdr.pack(fill="x", padx=20)
        tk.Label(hdr, text="🔭  AstroAnalyzer", font=FONT_TITLE,
                 bg=DARK_BG, fg=ACCENT).pack(side="left")
        tk.Label(hdr, text="XISF/FITS · Bildanalyse · Galaxien · PixInsight",
                 font=FONT_BODY, bg=DARK_BG, fg=LABEL_FG).pack(side="left", padx=18)

        # Notebook
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=12, pady=(0,8))

        self._tab_dateien()
        self._tab_konfiguration()
        self._tab_analyse()
        self._tab_ergebnisse()

    # ── Tab 1: Dateien ─────────────────────────────────────────────────────

    def _tab_dateien(self):
        frm = ttk.Frame(self.nb, style="TFrame", padding=20)
        self.nb.add(frm, text="  📂 Dateien  ")

        hdr_row = tk.Frame(frm, bg=DARK_BG)
        hdr_row.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0,16))
        tk.Label(hdr_row, text="Eingabedateien", font=FONT_H2,
                 bg=DARK_BG, fg=ACCENT).pack(side="left")
        ttk.Button(hdr_row, text="📁 Ordner auto-scan",
                   command=self._scan_folder).pack(side="left", padx=20)

        rows = [
            ("Light-Master *",     self.var_light,    self._browse_light,    "XISF/FITS — kalibrierter oder unkalibrierter Lum/RGB-Stack"),
            ("MasterDark",         self.var_dark,     self._browse_dark,     "360s MasterDark (optional)"),
            ("MasterFlat",         self.var_flat,     self._browse_flat,     "Lum-MasterFlat (optional, für Flat-Mismatch-Test)"),
            ("MasterFlatDark",     self.var_flatdark, self._browse_flatdark, "FlatDark mit gleicher Belichtungszeit wie Flat (optional)"),
        ]
        for i, (label, var, cmd, hint) in enumerate(rows, start=1):
            tk.Label(frm, text=label, bg=DARK_BG, fg=TEXT_FG,
                     font=FONT_BODY, anchor="e", width=16).grid(
                         row=i, column=0, sticky="e", padx=(0,8), pady=6)
            e = ttk.Entry(frm, textvariable=var, width=62)
            e.grid(row=i, column=1, sticky="ew", pady=6)
            ttk.Button(frm, text="…", command=cmd, width=3).grid(
                row=i, column=2, padx=(6,0), pady=6)
            tk.Label(frm, text=hint, bg=DARK_BG, fg=LABEL_FG,
                     font=FONT_HINT).grid(
                         row=i, column=1, sticky="w", padx=4, pady=(0,0))

        # Ausgabe
        tk.Label(frm, text="─"*80, bg=DARK_BG, fg=PANEL_BG).grid(
            row=6, column=0, columnspan=3, pady=12)
        tk.Label(frm, text="Ausgabeverzeichnis *", bg=DARK_BG, fg=TEXT_FG,
                 font=FONT_BODY, anchor="e", width=16).grid(
                     row=7, column=0, sticky="e", padx=(0,8))
        ttk.Entry(frm, textvariable=self.var_output, width=62).grid(
            row=7, column=1, sticky="ew", pady=6)
        ttk.Button(frm, text="…", command=self._browse_output, width=3).grid(
            row=7, column=2, padx=(6,0))

        tk.Label(frm, text="Obsidian Vault (opt.)", bg=DARK_BG, fg=TEXT_FG,
                 font=FONT_BODY, anchor="e", width=16).grid(
                     row=8, column=0, sticky="e", padx=(0,8))
        ttk.Entry(frm, textvariable=self.var_obsidian, width=62).grid(
            row=8, column=1, sticky="ew", pady=6)
        ttk.Button(frm, text="…", command=self._browse_obsidian, width=3).grid(
            row=8, column=2, padx=(6,0))
        tk.Label(frm, text="Reports werden als Markdown direkt in <Vault>/Ergebnisse/ geschrieben",
                 bg=DARK_BG, fg=LABEL_FG, font=FONT_HINT).grid(
                     row=8, column=1, sticky="w", padx=4)

        frm.columnconfigure(1, weight=1)

    # ── Tab 2: Konfiguration ───────────────────────────────────────────────

    def _tab_konfiguration(self):
        frm = ttk.Frame(self.nb, style="TFrame", padding=20)
        self.nb.add(frm, text="  ⚙️ Konfiguration  ")

        # Module
        mod_frm = tk.LabelFrame(frm, text=" Analysemodule ", bg=DARK_BG,
                                 fg=ACCENT, font=FONT_H2, padx=16, pady=12)
        mod_frm.pack(fill="x", pady=(0,16))

        mod_labels = {
            1: "Modul 1 – Technische Bildanalyse (FWHM, Rauschen, Gradient, Banding)",
            2: "Modul 2 – Aufnahmetechnik (Gain, Sub-Länge, Tiefe, Dithering)",
            3: "Modul 3 – PixInsight-Optimierungsvorschläge (mit Begründungen)",
            4: "Modul 4 – Kalibrierungskette (Dark/Flat/Flat-Mismatch-Test)",
            5: "Modul 5 – Hauptobjekte / Galaxienanalyse (NGC/IC + PGC-Kandidaten)",
        }
        for i, lbl in mod_labels.items():
            cb = ttk.Checkbutton(mod_frm, text=lbl, variable=self.var_mod[i],
                                 style="TCheckbutton")
            cb.pack(anchor="w", pady=3)

        # Ausgabeformate
        fmt_frm = tk.LabelFrame(frm, text=" Ausgabeformate ", bg=DARK_BG,
                                 fg=ACCENT, font=FONT_H2, padx=16, pady=12)
        fmt_frm.pack(fill="x", pady=(0,16))

        fmt_row = tk.Frame(fmt_frm, bg=DARK_BG)
        fmt_row.pack(fill="x")
        for var, lbl in [(self.var_fmt_md,   "📄 Markdown (.md)"),
                         (self.var_fmt_docx, "📝 Word (.docx)"),
                         (self.var_fmt_csv,  "📊 CSV Galaxienliste"),
                         (self.var_fmt_png,  "🗺️ Tiefenkarte (.png)"),
                         (self.var_fmt_js,   "📜 PixInsight-Script (.js)")]:
            ttk.Checkbutton(fmt_row, text=lbl, variable=var,
                            style="TCheckbutton").pack(side="left", padx=16)

        # Zusatz
        add_frm = tk.LabelFrame(frm, text=" Zusatzparameter ", bg=DARK_BG,
                                  fg=ACCENT, font=FONT_H2, padx=16, pady=12)
        add_frm.pack(fill="x")
        row = tk.Frame(add_frm, bg=DARK_BG)
        row.pack(fill="x")
        tk.Label(row, text="Anzahl Subs (0 = aus Header):",
                 bg=DARK_BG, fg=TEXT_FG, font=FONT_BODY).pack(side="left")
        ttk.Spinbox(row, from_=0, to=9999, textvariable=self.var_n_subs,
                    width=6, font=FONT_BODY).pack(side="left", padx=10)
        tk.Label(row, text="Tipp: Falls NCOMBINE nicht im Header steht",
                 bg=DARK_BG, fg=LABEL_FG, font=FONT_HINT).pack(
                     side="left", padx=10)

    # ── Tab 3: Analyse ─────────────────────────────────────────────────────

    def _tab_analyse(self):
        frm = ttk.Frame(self.nb, style="TFrame", padding=20)
        self.nb.add(frm, text="  🔬 Analyse  ")

        # Run-Button
        self.btn_run = ttk.Button(frm, text="▶  Analyse starten",
                                   style="Run.TButton", command=self._start_analysis)
        self.btn_run.pack(pady=(0, 16))

        # Progress
        prog_frm = tk.Frame(frm, bg=DARK_BG)
        prog_frm.pack(fill="x", pady=(0, 8))
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(prog_frm, variable=self.progress_var,
                                             maximum=100, length=900)
        self.progress_bar.pack(fill="x")
        self.lbl_status = tk.Label(prog_frm, text="Bereit",
                                    bg=DARK_BG, fg=LABEL_FG, font=FONT_BODY)
        self.lbl_status.pack(anchor="w", pady=4)

        # Log
        tk.Label(frm, text="Analyse-Log", bg=DARK_BG, fg=ACCENT,
                 font=FONT_H2).pack(anchor="w", pady=(8,4))
        self.log = scrolledtext.ScrolledText(
            frm, height=32, bg=PANEL_BG, fg=TEXT_FG,
            font=FONT_MONO, insertbackground=TEXT_FG,
            selectbackground=ACCENT, relief="flat", bd=2
        )
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("ok",   foreground=GREEN)
        self.log.tag_config("warn", foreground=YELLOW)
        self.log.tag_config("err",  foreground=RED)
        self.log.tag_config("head", foreground=ACCENT, font=("Courier",9,"bold"))

    # ── Tab 4: Ergebnisse ──────────────────────────────────────────────────

    def _tab_ergebnisse(self):
        frm = ttk.Frame(self.nb, style="TFrame", padding=10)
        self.nb.add(frm, text="  📊 Ergebnisse  ")

        # Toolbar
        tb = tk.Frame(frm, bg=DARK_BG)
        tb.pack(fill="x", pady=(0, 8))
        ttk.Button(tb, text="📂 Ausgabeordner öffnen",
                   command=self._open_output_dir).pack(side="left", padx=4)
        ttk.Button(tb, text="🔄 Aktualisieren",
                   command=self._refresh_results).pack(side="left", padx=4)

        # Ergebnis-Karten (Grid)
        self.results_frame = tk.Frame(frm, bg=DARK_BG)
        self.results_frame.pack(fill="both", expand=True)
        self._build_result_cards()

    def _build_result_cards(self):
        """Baut die Ergebnis-Übersichtskarten."""
        for w in self.results_frame.winfo_children():
            w.destroy()

        cards = [
            ("🌌 Bildqualität",     self._card_m1),
            ("📷 Aufnahmetechnik",  self._card_m2),
            ("🔧 PixInsight",       self._card_m3),
            ("🎞️ Kalibrierung",     self._card_m4),
            ("🔭 Galaxien",         self._card_m5),
        ]
        for col, (title, builder) in enumerate(cards):
            card = tk.Frame(self.results_frame, bg=PANEL_BG, bd=1,
                            relief="flat", padx=12, pady=12)
            card.grid(row=0, column=col, sticky="nsew", padx=5, pady=5)
            self.results_frame.columnconfigure(col, weight=1)
            self.results_frame.rowconfigure(0, weight=1)
            tk.Label(card, text=title, bg=PANEL_BG, fg=ACCENT,
                     font=FONT_H2).pack(anchor="w", pady=(0,8))
            builder(card)

    def _card_m1(self, parent):
        r = self.results.get("m1", {})
        if not r:
            tk.Label(parent, text="— noch keine Analyse —", bg=PANEL_BG,
                     fg=LABEL_FG).pack()
            return
        items = [
            ("FWHM", f"{r.get('fwhm_arcsec','?')}\""),
            ("Feldvariation", f"Δ {r.get('fwhm_field_delta','?')} px"),
            ("Exzentrizität", f"{r.get('ecc_median','?')}"),
            ("Rauschen MAD", f"{r.get('noise_mad','?'):.3g}"),
            ("Gradient", f"{r.get('gradient_pct','?'):.1f}%"),
            ("Banding", f"{r.get('banding_amp','?'):.3g}"),
        ]
        for k, v in items:
            row = tk.Frame(parent, bg=PANEL_BG)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=k+":", bg=PANEL_BG, fg=LABEL_FG,
                     font=FONT_BODY, width=14, anchor="w").pack(side="left")
            tk.Label(row, text=v, bg=PANEL_BG, fg=TEXT_FG,
                     font=FONT_BODY).pack(side="left")

    def _card_m2(self, parent):
        r = self.results.get("m2", {})
        if not r:
            tk.Label(parent, text="— noch keine Analyse —", bg=PANEL_BG,
                     fg=LABEL_FG).pack(); return
        intg = r.get("integration", {})
        dith = r.get("dithering", {})
        items = [
            ("Gesamt", f"{intg.get('total_h','?')} h"),
            ("SNR-Gewinn", f"{intg.get('snr_gain','?')}×"),
            ("+mag vs 1h", f"+{intg.get('dmag_vs_1h','?')} mag"),
            ("Gain",  f"{r.get('gain',{}).get('regime','?')}"),
            ("Dithering", f"{dith.get('status','?')} ({dith.get('ratio','?')}×)"),
            ("Temp.", f"{r.get('temperatur',{}).get('temp_c','?')} °C"),
        ]
        for k, v in items:
            row = tk.Frame(parent, bg=PANEL_BG); row.pack(fill="x", pady=2)
            tk.Label(row, text=k+":", bg=PANEL_BG, fg=LABEL_FG, font=FONT_BODY,
                     width=14, anchor="w").pack(side="left")
            tk.Label(row, text=v, bg=PANEL_BG, fg=TEXT_FG, font=FONT_BODY).pack(side="left")

    def _card_m3(self, parent):
        r3 = self.results.get("m3", [])
        if not r3:
            tk.Label(parent, text="— noch keine Analyse —", bg=PANEL_BG,
                     fg=LABEL_FG).pack(); return
        for step in r3[:6]:
            tk.Label(parent, text=f"{step['nr']}. {step['werkzeug'][:30]}",
                     bg=PANEL_BG, fg=TEXT_FG, font=("Helvetica",9), anchor="w",
                     wraplength=180).pack(fill="x", pady=1)
        if len(r3) > 6:
            tk.Label(parent, text=f"… +{len(r3)-6} weitere", bg=PANEL_BG,
                     fg=LABEL_FG, font=FONT_HINT).pack(anchor="w")

    def _card_m4(self, parent):
        r4 = self.results.get("m4", {})
        if not r4:
            tk.Label(parent, text="— noch keine Analyse —", bg=PANEL_BG,
                     fg=LABEL_FG).pack(); return
        dk = r4.get("dark", {}); fl = r4.get("flat", {}); fm = r4.get("flat_mismatch", {})
        items = [
            ("Dark Amp-Glow", dk.get("bewertung", "—")),
            ("Flat Asymm.", f"{fl.get('asymmetrie_pct','—')}%"),
            ("Flat-Mismatch", f"corr={fm.get('korrelation','—')}"),
            ("Warnung", "⚠️ Flat-Mismatch!" if fm.get("warnung") else "✅ OK"),
        ]
        for k, v in items:
            row = tk.Frame(parent, bg=PANEL_BG); row.pack(fill="x", pady=2)
            tk.Label(row, text=k+":", bg=PANEL_BG, fg=LABEL_FG, font=FONT_BODY,
                     width=14, anchor="w").pack(side="left")
            col = RED if "⚠️" in str(v) else (GREEN if "✅" in str(v) else TEXT_FG)
            tk.Label(row, text=v, bg=PANEL_BG, fg=col, font=FONT_BODY).pack(side="left")

    def _card_m5(self, parent):
        r5 = self.results.get("m5", {})
        if not r5.get("n_ngc_ic") and not r5.get("n_high"):
            tk.Label(parent, text="— noch keine Analyse —", bg=PANEL_BG,
                     fg=LABEL_FG).pack(); return
        items = [
            ("NGC/IC", str(r5.get("n_ngc_ic", 0))),
            ("PGC HIGH", str(r5.get("n_high", 0))),
            ("PGC MITTEL", str(r5.get("n_mittel", 0))),
            ("Gesamt", str(r5.get("n_ngc_ic",0) + r5.get("n_high",0))),
            ("WCS", "✅" if r5.get("wcs_used") else "❌ nicht vorhanden"),
        ]
        for k, v in items:
            row = tk.Frame(parent, bg=PANEL_BG); row.pack(fill="x", pady=2)
            tk.Label(row, text=k+":", bg=PANEL_BG, fg=LABEL_FG, font=FONT_BODY,
                     width=14, anchor="w").pack(side="left")
            tk.Label(row, text=v, bg=PANEL_BG, fg=TEXT_FG, font=FONT_BODY).pack(side="left")

    # ── Analyse-Thread ─────────────────────────────────────────────────────

    def _start_analysis(self):
        if self.analysis_running:
            return
        if not self.var_light.get():
            messagebox.showerror("Fehler", "Bitte einen Light-Master auswählen!")
            return
        if not self.var_output.get():
            messagebox.showerror("Fehler", "Bitte ein Ausgabeverzeichnis auswählen!")
            return

        self.analysis_running = True
        self.btn_run.configure(state="disabled")
        self.progress_var.set(0)
        self.log.delete("1.0", "end")
        self.nb.select(2)  # Analyse-Tab

        # Konfiguration lesen
        cfg = {
            "light_path":      self.var_light.get(),
            "dark_path":       self.var_dark.get() or None,
            "flat_path":       self.var_flat.get() or None,
            "flatdark_path":   self.var_flatdark.get() or None,
            "n_subs_override": self.var_n_subs.get(),
            "output_dir":      self.var_output.get(),
            "obsidian_path":   self.var_obsidian.get() or None,
            "output_formats": [
                k for k, v in [("markdown", self.var_fmt_md),
                                ("docx",     self.var_fmt_docx),
                                ("csv",      self.var_fmt_csv),
                                ("png",      self.var_fmt_png),
                                ("pixinsight", self.var_fmt_js)]
                if v.get()
            ],
            "modules_enabled": [i for i in range(1, 6) if self.var_mod[i].get()],
        }

        lights = self.multi_lights if self.multi_lights else [("", cfg["light_path"])]

        def worker():
            try:
                from pipeline import run_pipeline
                self._log("╔══ AstroAnalyzer gestartet ══╗", "head")

                def cb(pct, msg):
                    self.progress_queue.put(("progress", pct, msg))

                last_res = {}
                for idx, (filt, lpath) in enumerate(lights):
                    if len(lights) > 1:
                        self._log(f"── Filter {filt} ({idx+1}/{len(lights)}) ──", "head")
                    self._log(f"  Light: {Path(lpath).name}", "ok")
                    for k in ("dark_path","flat_path","flatdark_path"):
                        if cfg.get(k):
                            self._log(f"  {k.replace('_path','').capitalize()}: {Path(cfg[k]).name}", "ok")
                    self._log(f"  Module: {cfg['modules_enabled']}")
                    self._log(f"  Formate: {cfg['output_formats']}", "ok")
                    self._log("")

                    last_res = run_pipeline(
                        light_path      = lpath,
                        dark_path       = cfg["dark_path"],
                        flat_path       = cfg["flat_path"],
                        flatdark_path   = cfg["flatdark_path"],
                        n_subs_override = cfg["n_subs_override"],
                        output_dir      = cfg["output_dir"],
                        output_formats  = cfg["output_formats"],
                        modules_enabled = cfg["modules_enabled"],
                        progress_cb     = cb,
                        obsidian_path   = cfg["obsidian_path"],
                    )

                self.progress_queue.put(("done", last_res))

            except Exception as e:
                import traceback
                self.progress_queue.put(("error", str(e), traceback.format_exc()))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_queue(self):
        """Verarbeitet Queue-Nachrichten aus dem Analyse-Thread."""
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                if msg[0] == "progress":
                    _, pct, text = msg
                    self.progress_var.set(pct)
                    self.lbl_status.configure(text=text)
                    self._log(f"  [{pct:5.1f}%] {text}")

                elif msg[0] == "done":
                    res = msg[1]
                    self.results = res
                    self.progress_var.set(100)
                    self.lbl_status.configure(text="✅ Analyse abgeschlossen!")
                    self._log("\n╔══ ABGESCHLOSSEN ══╗", "head")
                    self._log_results(res)
                    self._build_result_cards()
                    self.btn_run.configure(state="normal")
                    self.analysis_running = False

                elif msg[0] == "error":
                    _, err, tb = msg
                    self.lbl_status.configure(text=f"❌ Fehler: {err}")
                    self._log(f"\n❌ FEHLER: {err}", "err")
                    self._log(tb, "err")
                    self.btn_run.configure(state="normal")
                    self.analysis_running = False
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _log(self, msg: str, tag: str = ""):
        self.log.insert("end", msg + "\n", tag)
        self.log.see("end")

    def _log_results(self, res: dict):
        r1 = res.get("m1", {}); r5 = res.get("m5", {})
        self._log(f"  FWHM: {r1.get('fwhm_arcsec','?')}\"  "
                  f"Gradient: {r1.get('gradient_pct','?'):.1f}%  "
                  f"Banding: {r1.get('banding_amp','?'):.3g}", "ok")
        self._log(f"  Galaxien: {r5.get('n_ngc_ic',0)} NGC/IC + "
                  f"{r5.get('n_high',0)} PGC-HIGH", "ok")
        for f in res.get("written_files", []):
            self._log(f"  📄 {f}", "ok")

    # ── Browse-Callbacks ───────────────────────────────────────────────────

    def _browse_xisf(self, var):
        p = filedialog.askopenfilename(
            title="XISF/FITS auswählen",
            filetypes=[("Astro-Dateien","*.xisf *.fits *.fit *.fts"),
                       ("Alle","*.*")])
        if p: var.set(p)

    def _browse_light(self):
        self._browse_xisf(self.var_light)
        if self.var_light.get() and not self.var_output.get():
            self.var_output.set(str(Path(self.var_light.get()).parent))
    def _browse_dark(self):     self._browse_xisf(self.var_dark)
    def _browse_flat(self):     self._browse_xisf(self.var_flat)
    def _browse_flatdark(self): self._browse_xisf(self.var_flatdark)

    def _browse_output(self):
        p = filedialog.askdirectory(title="Ausgabeverzeichnis")
        if p: self.var_output.set(p)

    def _browse_obsidian(self):
        p = filedialog.askdirectory(title="Obsidian Vault-Verzeichnis")
        if p: self.var_obsidian.set(p)

    # ── Sonstiges ──────────────────────────────────────────────────────────

    def _open_output_dir(self):
        d = self.var_output.get()
        if d and os.path.isdir(d):
            import subprocess, sys
            if sys.platform == "darwin":
                subprocess.Popen(["open", d])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", d])
            else:
                subprocess.Popen(["xdg-open", d])

    def _refresh_results(self):
        self._build_result_cards()

    def _scan_folder(self):
        folder = filedialog.askdirectory(title="Ordner mit Master-Dateien wählen")
        if not folder:
            return
        if not self.var_output.get():
            self.var_output.set(folder)

        EXTS = {".xisf", ".fits", ".fit", ".fts"}
        files = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in EXTS)
        if not files:
            messagebox.showwarning("Keine Dateien", "Keine XISF/FITS-Dateien im Ordner.")
            return

        TYPE_MAP = {
            "light": "light", "light frame": "light",
            "dark": "dark", "dark frame": "dark",
            "flat": "flat", "flat frame": "flat",
            "flatdark": "flatdark", "flat dark": "flatdark",
            "darkflat": "flatdark", "dark flat": "flatdark",
        }
        NAME_MAP = {
            "light": "light", "dark": "dark", "flat": "flat",
            "flatdark": "flatdark", "darkflat": "flatdark",
        }

        from utils.xisf_reader import load_master_header

        # {typ: {filter_name: [Path]}}
        found: dict[str, dict[str, list[Path]]] = {
            "light": {}, "dark": {}, "flat": {}, "flatdark": {}
        }
        unknown: list[tuple[Path, str]] = []

        for f in files:
            try:
                hdr = load_master_header(str(f))
                typ_raw = hdr.get("IMAGETYP") or ""
                filt    = (hdr.get("FILTER") or "?").strip()
            except Exception as e:
                unknown.append((f, f"[Lesefehler: {e}]"))
                continue

            typ = TYPE_MAP.get(typ_raw.lower().strip())
            if typ is None:
                for key, val in NAME_MAP.items():
                    if key in f.stem.lower():
                        typ = val
                        break
            if typ:
                found[typ].setdefault(filt, []).append(f)
            else:
                unknown.append((f, f"IMAGETYP={typ_raw!r}"))

        # EXPTIME aus erstem Light/Flat lesen für Dark-Matching
        light_exptime = None
        flat_exptime  = None
        if found["light"]:
            first_light = next(iter(next(iter(found["light"].values()))))
            try:
                hdr = load_master_header(str(first_light))
                t = hdr.get("EXPTIME")
                if t: light_exptime = float(t)
            except Exception:
                pass
        if found["flat"]:
            first_flat = next(iter(next(iter(found["flat"].values()))))
            try:
                hdr = load_master_header(str(first_flat))
                t = hdr.get("EXPTIME")
                if t: flat_exptime = float(t)
            except Exception:
                pass

        def best_dark(candidates: list, target_exp) -> "Path | None":
            if not candidates: return None
            if target_exp is None: return candidates[0]
            for p in candidates:
                try:
                    hdr = load_master_header(str(p))
                    t = float(hdr.get("EXPTIME") or 0)
                    if abs(t - target_exp) < 1.0:
                        return p
                except Exception:
                    pass
            return candidates[0]

        if not any(found.values()):
            detail = "\n".join(f"{p.name}: {info}" for p, info in unknown[:10])
            messagebox.showwarning(
                "Nichts erkannt",
                "IMAGETYP-Header fehlt oder unbekannt.\n\n" + detail)
            return

        # Filter-Auswahl für Lights
        chosen_light = None
        self.multi_lights = []
        light_by_filter = found["light"]
        if light_by_filter:
            filters = sorted(light_by_filter.keys())
            if len(filters) == 1:
                chosen_light = light_by_filter[filters[0]][0]
            else:
                picked = self._pick_filter(light_by_filter)
                if picked is None:
                    return
                if isinstance(picked, list):
                    self.multi_lights = [(f, str(p)) for f, p in picked]
                    chosen_light = picked[0][1]
                else:
                    chosen_light = picked

        # Filter-Auswahl für Flats
        chosen_flat = None
        flat_by_filter = found["flat"]
        if flat_by_filter:
            filters = sorted(flat_by_filter.keys())
            if len(filters) == 1:
                chosen_flat = flat_by_filter[filters[0]][0]
            else:
                picked = self._pick_filter(flat_by_filter, label="MasterFlat-Filter")
                if picked is None:
                    return
                chosen_flat = picked[0][1] if isinstance(picked, list) else picked

        all_darks     = [p for pl in found["dark"].values()     for p in pl]
        all_flatdarks = [p for pl in found["flatdark"].values() for p in pl]
        chosen_dark     = best_dark(all_darks,     light_exptime)
        chosen_flatdark = best_dark(all_flatdarks, flat_exptime)

        msg = []
        if self.multi_lights:
            msg.append(f"Light:     Alle Filter — {', '.join(f for f,_ in self.multi_lights)}")
        elif chosen_light:
            msg.append(f"Light:     {Path(str(chosen_light)).name}")
        if chosen_dark:
            exp_str = f" ({light_exptime:.0f}s)" if light_exptime else ""
            msg.append(f"Dark:      {chosen_dark.name}{exp_str}")
        if chosen_flat:     msg.append(f"Flat:      {Path(str(chosen_flat)).name}")
        if chosen_flatdark:
            exp_str = f" ({flat_exptime:.2f}s)" if flat_exptime else ""
            msg.append(f"FlatDark:  {chosen_flatdark.name}{exp_str}")
        if unknown:         msg.append(f"Unbekannt: {len(unknown)} Datei(en)")

        if not messagebox.askokcancel("Zuordnung bestätigen",
                                      "\n".join(msg) + "\n\nFelder überschreiben?"):
            return

        if chosen_light:    self.var_light.set(str(chosen_light))
        if chosen_dark:     self.var_dark.set(str(chosen_dark))
        if chosen_flat:     self.var_flat.set(str(chosen_flat))
        if chosen_flatdark: self.var_flatdark.set(str(chosen_flatdark))

    def _pick_filter(self, by_filter: dict[str, list[Path]],
                     label: str = "Light-Filter wählen") -> "Path | list[tuple[str,Path]] | None":
        """Zeigt Filter-Auswahl. Gibt Path (Einzel), [(filt,Path),...] (alle) oder None zurück."""
        win = tk.Toplevel(self)
        win.title(label)
        win.configure(bg=DARK_BG)
        win.resizable(False, False)
        win.grab_set()

        tk.Label(win, text=label, font=FONT_H2, bg=DARK_BG, fg=ACCENT,
                 pady=12).pack(padx=20)

        result: list = [None]

        for filt, paths in sorted(by_filter.items()):
            row = tk.Frame(win, bg=DARK_BG)
            row.pack(fill="x", padx=20, pady=4)
            files_str = ", ".join(p.name for p in paths[:2])
            if len(paths) > 2:
                files_str += f" (+{len(paths)-2})"
            btn = ttk.Button(
                row, text=f"  {filt}  —  {files_str}",
                command=lambda p=paths[0], w=win, r=result: (r.__setitem__(0, p), w.destroy()))
            btn.pack(fill="x")

        ttk.Separator(win, orient="horizontal").pack(fill="x", padx=20, pady=8)
        all_entries = [(f, paths[0]) for f, paths in sorted(by_filter.items())]
        ttk.Button(win, text=f"★ Alle Filter ({', '.join(f for f,_ in all_entries)})",
                   command=lambda w=win, r=result, a=all_entries: (r.__setitem__(0, a), w.destroy())
                   ).pack(fill="x", padx=20, pady=(0, 4))
        ttk.Button(win, text="Abbrechen",
                   command=win.destroy).pack(pady=8)
        win.wait_window()
        return result[0]

    def _about(self):
        messagebox.showinfo(
            "Über AstroAnalyzer",
            "AstroAnalyzer v0.1\n\n"
            "Technische Analyse von Astrofotografie-Masters\n"
            "(XISF/FITS · LRGB · Galaxien · PixInsight)\n\n"
            "Entwickelt für AP155 EDF + QHY600M\n"
            "Pilotanalyse: NGC 4565, April 2026"
        )


# ── Entry Point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = AstroAnalyzerApp()
    app.mainloop()
