"""
AstroAnalyzer – Modul 1: Technische Bildanalyse
Rauschen · Hintergrund · Gradient · PSF (FWHM/Exzentrizität) · Artefakte
"""

import numpy as np
import warnings
warnings.filterwarnings("ignore")

from astropy.stats import sigma_clipped_stats
from photutils.background import Background2D, MedianBackground
from photutils.detection import DAOStarFinder


def run(img: np.ndarray, pixel_scale: float, progress_cb=None) -> dict:
    """
    Vollständige technische Qualitätsbewertung.

    img          : 2D float32 ndarray, normalisiert 0..1
    pixel_scale  : Bogensekunden/Pixel
    progress_cb  : optionale Callback-Funktion(pct, msg)
    """
    def pg(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    H, W = img.shape
    pg(5, "Hintergrundstatistik …")

    # ── Hintergrund & Rauschen ─────────────────────────────────────────────
    mean, med, std = sigma_clipped_stats(img, sigma=3.0, maxiters=5)
    bg_mask = img < (med + 3 * std)
    mad = float(np.median(np.abs(img[bg_mask] - med)) * 1.4826)

    pg(20, "Gradientenmodell …")

    # ── Gradient ──────────────────────────────────────────────────────────
    bkg = Background2D(img, (384, 384), filter_size=(7, 7),
                       bkg_estimator=MedianBackground())
    b = bkg.background
    grad_amp = float(np.max(b) - np.min(b))
    grad_pct = 100 * grad_amp / med if med > 0 else 0

    # ── Corner-Asymmetrie ─────────────────────────────────────────────────
    def cm(y0, y1, x0, x1):
        return float(np.median(img[max(0,y0):min(H,y1), max(0,x0):min(W,x1)]))

    margin = min(400, H//10, W//10)
    cen = cm(H//2-200, H//2+200, W//2-200, W//2+200)
    corner_delta = {
        "TL": 100*(cm(50,margin+50,50,margin+50) - cen)/cen if cen else 0,
        "TR": 100*(cm(50,margin+50,W-margin-50,W-50) - cen)/cen if cen else 0,
        "BL": 100*(cm(H-margin-50,H-50,50,margin+50) - cen)/cen if cen else 0,
        "BR": 100*(cm(H-margin-50,H-50,W-margin-50,W-50) - cen)/cen if cen else 0,
        "midL": 100*(cm(H//2-150,H//2+150,50,margin+50) - cen)/cen if cen else 0,
        "midR": 100*(cm(H//2-150,H//2+150,W-margin-50,W-50) - cen)/cen if cen else 0,
    }

    pg(40, "Sternabbildung messen …")

    # ── PSF-Analyse (FWHM / Exzentrizität) ────────────────────────────────
    fwhms, eccs, xs_list, ys_list = [], [], [], []

    try:
        sub = img - med
        threshold = max(20 * std, 5 * mad)
        finder = DAOStarFinder(
            fwhm=5, threshold=threshold,
            roundlo=-0.6, roundhi=0.6, exclude_border=True
        )
        stars = finder(sub)
        if stars is not None and len(stars) > 0:
            peak_min = max(10 * std, 3 * mad)
            stars = stars[(np.array(stars["peak"]) > peak_min) &
                          (np.array(stars["peak"]) < 0.85)]
            order = np.argsort(-np.array(stars["flux"]))

            for idx in order[:700]:
                s = stars[idx]
                cx = int(round(float(s["xcentroid"])))
                cy = int(round(float(s["ycentroid"])))
                if cx < 12 or cy < 12 or cx > W-12 or cy > H-12:
                    continue
                patch = np.clip(img[cy-9:cy+10, cx-9:cx+10] - med, 0, None)
                if patch.max() <= 0:
                    continue
                tot = patch.sum()
                if tot <= 0:
                    continue
                yy, xx = np.mgrid[0:patch.shape[0], 0:patch.shape[1]]
                mx_ = (xx * patch).sum() / tot
                my_ = (yy * patch).sum() / tot
                sxx = ((xx-mx_)**2 * patch).sum() / tot
                syy = ((yy-my_)**2 * patch).sum() / tot
                sxy = ((xx-mx_)*(yy-my_) * patch).sum() / tot
                if sxx <= 0 or syy <= 0:
                    continue
                disc = max(0, (sxx-syy)**2 + 4*sxy**2)
                l1 = 0.5*(sxx+syy + np.sqrt(disc))
                l2 = 0.5*(sxx+syy - np.sqrt(disc))
                if l2 <= 0:
                    continue
                fw  = 2.3548 * np.sqrt(0.5*(sxx+syy))
                ecc = np.sqrt(max(0, 1 - l2/l1))
                if 1.0 < fw < 14.0:
                    fwhms.append(fw)
                    eccs.append(ecc)
                    xs_list.append(cx)
                    ys_list.append(cy)
    except Exception as e:
        pass

    if fwhms:
        fwhms = np.array(fwhms)
        eccs  = np.array(eccs)
        xs_a  = np.array(xs_list)
        ys_a  = np.array(ys_list)
        r     = np.hypot(xs_a - W/2, ys_a - H/2)
        mask_cen  = r < min(1500, W*0.25)
        mask_edge = r > min(3200, W*0.45)
        fwhm_med  = float(np.median(fwhms))
        fwhm_cen  = float(np.median(fwhms[mask_cen]))  if mask_cen.any()  else fwhm_med
        fwhm_edge = float(np.median(fwhms[mask_edge])) if mask_edge.any() else fwhm_med
        ecc_med   = float(np.median(eccs))
        ecc_p90   = float(np.percentile(eccs, 90))
        n_stars   = len(fwhms)
    else:
        fwhm_med = fwhm_cen = fwhm_edge = 5.0
        ecc_med = ecc_p90 = 0.2
        n_stars = 0

    pg(70, "Banding-Analyse …")

    # ── Banding / Pattern ─────────────────────────────────────────────────
    py0 = max(0, H//4)
    py1 = min(H, 3*H//4)
    px0 = max(0, W//8)
    px1 = min(W, 7*W//8)
    bg_patch = img[py0:py1, px0:px1] - np.median(img[py0:py1, px0:px1])
    col_prof = bg_patch.mean(axis=0)
    col_prof -= col_prof.mean()
    row_prof = bg_patch.mean(axis=1)
    row_prof -= row_prof.mean()
    banding_col = float(col_prof.std())
    banding_row = float(row_prof.std())
    banding_amp = float(np.sqrt(banding_col**2 + banding_row**2))

    fft_c = np.abs(np.fft.rfft(col_prof))
    freqs_c = np.fft.rfftfreq(len(col_prof))
    top_idx = np.argsort(-fft_c[2:])[:4] + 2
    banding_periods = [
        round(1/freqs_c[i], 1) for i in top_idx if freqs_c[i] > 0
    ]

    pg(90, "Sättigungs-Check …")

    # ── Sättigung ─────────────────────────────────────────────────────────
    sat = int((img >= 0.999).sum())
    clipped_zero = int((img <= 0.0001).sum())

    pg(100, "Bildanalyse abgeschlossen.")

    return {
        # Hintergrund
        "sky_median":        float(med),
        "sky_mean":          float(mean),
        "noise_mad":         mad,
        "noise_std":         float(std),
        # Gradient
        "gradient_pct":      round(grad_pct, 2),
        "gradient_sigma":    round(grad_amp / mad, 1) if mad > 0 else 0,
        "corner_delta":      {k: round(v, 2) for k, v in corner_delta.items()},
        # PSF
        "fwhm_median_px":    round(fwhm_med, 2),
        "fwhm_arcsec":       round(fwhm_med * pixel_scale, 2),
        "fwhm_center_px":    round(fwhm_cen, 2),
        "fwhm_edge_px":      round(fwhm_edge, 2),
        "fwhm_field_delta":  round(abs(fwhm_edge - fwhm_cen), 2),
        "ecc_median":        round(ecc_med, 3),
        "ecc_p90":           round(ecc_p90, 3),
        "n_stars_measured":  n_stars,
        # Pattern
        "banding_amp":       round(banding_amp, 6),
        "banding_col":       round(banding_col, 6),
        "banding_row":       round(banding_row, 6),
        "banding_periods":   banding_periods,
        # Sonstige
        "sat_pixels":        sat,
        "zero_pixels":       clipped_zero,
        "pixel_scale":       round(pixel_scale, 4),
        "image_width":       W,
        "image_height":      H,
    }


def bewertung(r: dict) -> list[dict]:
    """Gibt eine Liste von Bewertungs-Einträgen zurück."""
    entries = []
    def add(thema, wert, status, hinweis=""):
        entries.append({"thema": thema, "wert": wert,
                        "status": status, "hinweis": hinweis})

    fwhm = r["fwhm_arcsec"]
    if fwhm < 2.0:
        add("FWHM", f"{r['fwhm_arcsec']}\"", "✅",
            "Exzellentes Seeing oder gutes Dithering")
    elif fwhm < 3.5:
        add("FWHM", f"{r['fwhm_arcsec']}\"", "✅",
            "Gutes Seeing, seeing-limitiert")
    elif fwhm < 5.0:
        add("FWHM", f"{r['fwhm_arcsec']}\"", "⚠️",
            "Mäßiges Seeing oder Tracking-Problem")
    else:
        add("FWHM", f"{r['fwhm_arcsec']}\"", "❌",
            "Schlechtes Seeing, möglicher Fokus- oder Tracking-Fehler")

    delta = r["fwhm_field_delta"]
    if delta < 0.3:
        add("Feldkurvatur/Tilt", f"Δ {delta:.2f} px", "✅",
            "Homogene Abbildung über das gesamte Feld")
    elif delta < 0.7:
        add("Feldkurvatur/Tilt", f"Δ {delta:.2f} px", "⚠️",
            "Leichte Feldvariation, ggf. Tilt-Justage prüfen")
    else:
        add("Feldkurvatur/Tilt", f"Δ {delta:.2f} px", "❌",
            "Signifikante Feldvariation — Tilt oder Bildfeldwölbung")

    if r["ecc_median"] < 0.25:
        add("Exzentrizität", f"{r['ecc_median']:.3f}", "✅", "Runde Sterne, gutes Guiding")
    elif r["ecc_median"] < 0.4:
        add("Exzentrizität", f"{r['ecc_median']:.3f}", "⚠️", "Leichte Verformung")
    else:
        add("Exzentrizität", f"{r['ecc_median']:.3f}", "❌", "Deutliche Verformung — Guiding prüfen")

    if r["gradient_pct"] < 2.0:
        add("Gradient", f"{r['gradient_pct']:.1f}%", "✅", "Schwacher Gradient, unkritisch")
    elif r["gradient_pct"] < 5.0:
        add("Gradient", f"{r['gradient_pct']:.1f}%", "⚠️", "Mäßiger Gradient — DBE/GraXpert empfohlen")
    else:
        add("Gradient", f"{r['gradient_pct']:.1f}%", "❌", "Starker Gradient — Ursache klären (Flat? LP?)")

    banding_ratio = r["banding_amp"] / r["noise_mad"] if r["noise_mad"] > 0 else 0
    if banding_ratio < 0.3:
        add("Banding", f"{banding_ratio:.2f}× Rauschen", "✅", "Kein signifikantes Banding")
    elif banding_ratio < 0.6:
        add("Banding", f"{banding_ratio:.2f}× Rauschen", "⚠️", "Schwaches Banding — größeres Dithering")
    else:
        add("Banding", f"{banding_ratio:.2f}× Rauschen", "❌",
            "Starkes Banding — LinearPatternSubtraction + größeres Dithering")

    if r["sat_pixels"] < 100:
        add("Sättigung", f"{r['sat_pixels']} px", "✅", "Keine kritische Sättigung")
    elif r["sat_pixels"] < 5000:
        add("Sättigung", f"{r['sat_pixels']} px", "⚠️", "Einige Sternkerne gesättigt")
    else:
        add("Sättigung", f"{r['sat_pixels']} px", "❌", "Starke Sättigung — kürzere Subs erwägen")

    return entries
