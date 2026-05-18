"""
AstroAnalyzer – Pipeline
Orchestriert alle 5 Module + Report-Ausgabe
"""

import os
from pathlib import Path
from datetime import datetime


def run_pipeline(
    light_path: str,
    dark_path: str | None,
    flat_path: str | None,
    flatdark_path: str | None,
    n_subs_override: int = 0,
    output_dir: str = ".",
    output_formats: list = None,    # ["markdown", "docx", "csv", "png"]
    modules_enabled: list = None,   # [1,2,3,4,5]
    progress_cb=None,
    obsidian_path: str | None = None,
    dither_active: bool = True,
    dither_px: int = 0,
) -> dict:
    """
    Zentrale Pipeline. Gibt dict mit allen Ergebnissen zurück.
    progress_cb(pct: float, msg: str) — optional
    """
    if output_formats is None:
        output_formats = ["markdown", "docx", "csv", "png"]
    if modules_enabled is None:
        modules_enabled = [1, 2, 3, 4, 5]

    def pg(pct, msg):
        if progress_cb:
            progress_cb(float(pct), str(msg))

    results = {}

    # ── Dateien laden ──────────────────────────────────────────────────────
    pg(2, f"Lade {Path(light_path).name} …")
    from utils.xisf_reader import load_image, pixel_scale

    light_data = load_image(light_path)
    img  = light_data["img"]
    meta = light_data["meta"]
    wcs  = light_data["wcs"]

    # Graustufenbild sicherstellen
    if img.ndim == 3:
        img = img[0] if img.shape[0] in (1, 3) else img.mean(axis=0)

    pscale = pixel_scale(meta, wcs)
    n_subs = n_subs_override or meta.get("NCOMBINE", 1)
    target = meta.get("OBJECT", "target").replace(" ", "_")
    results["meta"]   = meta
    results["n_subs"] = n_subs
    results["wcs"]    = wcs

    # Kalibrier-Master laden
    dark_img = flatdark_img = flat_img = None
    if dark_path:
        pg(4, f"Lade Dark …")
        dk = load_image(dark_path)
        di = dk["img"]
        dark_img = di[0] if di.ndim == 3 else di

    if flatdark_path:
        pg(5, f"Lade FlatDark …")
        fd = load_image(flatdark_path)
        fi = fd["img"]
        flatdark_img = fi[0] if fi.ndim == 3 else fi

    if flat_path:
        pg(6, f"Lade Flat …")
        fl = load_image(flat_path)
        fli = fl["img"]
        flat_img = fli[0] if fli.ndim == 3 else fli

    # ── Modul 1: Bildanalyse ───────────────────────────────────────────────
    if 1 in modules_enabled:
        pg(8, "Modul 1: Bildanalyse …")
        from modules.m1_bildanalyse import run as m1_run, bewertung
        r1 = m1_run(img, pscale,
                    progress_cb=lambda p, m: pg(8 + p*0.20, m))
        results["m1"] = r1
        results["m1_bewertung"] = bewertung(r1)

    # ── Modul 2: Aufnahmetechnik ───────────────────────────────────────────
    if 2 in modules_enabled:
        pg(30, "Modul 2: Aufnahmetechnik …")
        from modules.m2_aufnahmetechnik import run as m2_run, empfehlungen
        r1_for_m2 = results.get("m1", {})
        r2 = m2_run(meta, r1_for_m2, n_subs_override=n_subs,
                    dither_active=dither_active, dither_px=dither_px,
                    progress_cb=lambda p, m: pg(30 + p*0.10, m))
        results["m2"] = r2
        results["m2_empfehlungen"] = empfehlungen(r2, r1_for_m2)

    # ── Modul 4: Kalibrierung (vor Modul 3, da M3 calib_results braucht) ──
    if 4 in modules_enabled:
        pg(42, "Modul 4: Kalibrierung …")
        from modules.m4_kalibrierung import run as m4_run
        r4 = m4_run(img, dark_img, flat_img, flatdark_img,
                    progress_cb=lambda p, m: pg(42 + p*0.13, m))
        results["m4"] = r4
    else:
        results["m4"] = {}

    # ── Modul 3: PixInsight ────────────────────────────────────────────────
    if 3 in modules_enabled:
        pg(56, "Modul 3: PixInsight-Empfehlungen …")
        from modules.m3_pixinsight import run as m3_run
        r3 = m3_run(
            img_stats=results.get("m1", {}),
            acq_results=results.get("m2", {}),
            calib_results=results.get("m4", {}),
            wcs_available=wcs is not None,
            progress_cb=lambda p, m: pg(56 + p*0.06, m),
        )
        results["m3"] = r3

    # ── Modul 5: Galaxienanalyse ───────────────────────────────────────────
    if 5 in modules_enabled:
        pg(63, "Modul 5: Galaxienanalyse …")
        from modules.m5_hauptobjekte import run as m5_run, erstelle_tiefenkarte
        r5 = m5_run(img, wcs, pscale,
                    progress_cb=lambda p, m: pg(63 + p*0.22, m))
        results["m5"] = r5
    else:
        results["m5"] = {"ngc_ic": [], "pgc_kand": [], "n_ngc_ic": 0,
                         "n_high": 0, "n_mittel": 0, "n_niedrig": 0,
                         "beschreibungen": {}, "wcs_used": False}

    # ── Report-Ausgabe ─────────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    base = f"{date_str}_{target}"
    written = []

    from utils.report_writer import write_markdown, write_docx, write_csv

    if "markdown" in output_formats:
        pg(87, "Markdown-Report schreiben …")
        md_path = os.path.join(output_dir, f"{base}_Bericht.md")
        write_markdown(results, md_path, meta)
        written.append(md_path)
        results["md_path"] = md_path

        # In Obsidian schreiben
        if obsidian_path:
            obs_dir = os.path.join(obsidian_path, "Ergebnisse")
            os.makedirs(obs_dir, exist_ok=True)
            obs_out = os.path.join(obs_dir, f"{base}_Bericht.md")
            import shutil
            shutil.copy2(md_path, obs_out)
            written.append(f"Obsidian: {obs_out}")

    if "docx" in output_formats:
        pg(90, "Word-Dokument schreiben …")
        docx_path = os.path.join(output_dir, f"{base}_Bericht.docx")
        write_docx(results, docx_path, meta)
        written.append(docx_path)
        results["docx_path"] = docx_path

    if "csv" in output_formats and 5 in modules_enabled:
        pg(93, "CSV schreiben …")
        csv_path = os.path.join(output_dir, f"{base}_Galaxien.csv")
        write_csv(results.get("m5", {}), csv_path)
        written.append(csv_path)
        results["csv_path"] = csv_path

    if "png" in output_formats and 5 in modules_enabled:
        pg(95, "Tiefenkarte erstellen …")
        from modules.m5_hauptobjekte import erstelle_tiefenkarte
        png_path = os.path.join(output_dir, f"{base}_Tiefenkarte.png")
        tele = meta.get("TELESCOP", "?")
        instr = meta.get("INSTRUME", "?")
        filt  = meta.get("FILTER", "?")
        erstelle_tiefenkarte(
            img, results.get("m5", {}), pscale, png_path,
            title=f"{target} · {tele}+{instr} · {filt} · {n_subs}×{meta.get('EXPTIME','?')}s"
        )
        written.append(png_path)
        results["png_path"] = png_path

    if "pixinsight" in output_formats and 1 in modules_enabled:
        pg(97, "PixInsight-Script generieren …")
        from modules.m6_pi_script import run as m6_run
        js_path = os.path.join(output_dir, f"{base}_Workflow.js")
        m6_run(m1=results.get("m1",{}), m2=results.get("m2",{}),
               m3=results.get("m3",[]), m4=results.get("m4",{}),
               meta=meta, output_path=js_path)
        written.append(js_path); results["js_path"] = js_path

    if "skymap" in output_formats:
        pg(98, "Himmelskarte …")
        from modules.m7_skymap import run as m7_run
        sky_path = os.path.join(output_dir, f"{base}_Skymap.png")
        m7_run(meta, wcs,
               (meta.get("HEIGHT", 6388), meta.get("WIDTH", 9576)),
               sky_path, progress_cb=lambda p, m: pg(98 + p*0.02, m))
        written.append(sky_path)
        results["sky_path"] = sky_path

    results["written_files"] = written
    pg(100, f"Fertig. {len(written)} Dateien geschrieben.")
    return results
