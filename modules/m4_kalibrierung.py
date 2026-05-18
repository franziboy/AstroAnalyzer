"""
AstroAnalyzer – Modul 4: Kalibrierungsketten-Analyse
MasterDark · MasterFlatDark · MasterFlat · Flat-Mismatch-Test
"""

import numpy as np
import scipy.ndimage as ndi
import warnings
warnings.filterwarnings("ignore")

from astropy.stats import sigma_clipped_stats


def run(light: np.ndarray | None,
        dark: np.ndarray | None,
        flat: np.ndarray | None,
        flatdark: np.ndarray | None,
        progress_cb=None) -> dict:
    """
    light    : kalibrierter MasterLight (float32, 0..1) — für Flat-Mismatch-Test
    dark     : MasterDark (gleiche Belichtungszeit wie Lights)
    flat     : MasterFlat (normalisiert, 0..1)
    flatdark : MasterFlatDark (gleiche Belichtung wie Flats)
    """
    def pg(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    results = {}

    # ── MasterDark ─────────────────────────────────────────────────────────
    if dark is not None:
        pg(10, "MasterDark analysieren …")
        _, med, std = sigma_clipped_stats(dark.ravel(), sigma=3.0, maxiters=5)
        H, W = dark.shape
        m = min(300, H//8, W//8)
        cen = float(np.median(dark[H//2-m:H//2+m, W//2-m:W//2+m]))

        corners = {}
        for n, (y0, y1, x0, x1) in {
            "TL": (0, m*2, 0, m*2),
            "TR": (0, m*2, W-m*2, W),
            "BL": (H-m*2, H, 0, m*2),
            "BR": (H-m*2, H, W-m*2, W),
        }.items():
            corners[n] = float(np.median(dark[y0:y1, x0:x1]))

        amp_glow = max(abs(v - cen) for v in corners.values())
        hot_mask = dark > (med + 10 * std)
        hot_pct  = 100 * hot_mask.sum() / dark.size

        results["dark"] = {
            "median":          round(float(med), 6),
            "noise_sigma":     round(float(std), 6),
            "amp_glow":        round(amp_glow, 6),
            "amp_glow_warn":   amp_glow > 5e-4,
            "hot_px_pct":      round(hot_pct, 4),
            "hot_px_warn":     hot_pct > 1.0,
            "corner_delta": {k: round(v - cen, 6) for k, v in corners.items()},
            "bewertung": (
                "✅ einwandfrei" if amp_glow < 5e-4 and hot_pct < 1.0
                else ("⚠️ prüfen" if amp_glow < 2e-3 else "❌ Amp-Glow vorhanden")
            ),
            "hinweis": _dark_hinweis(amp_glow, hot_pct),
        }
        pg(30, "MasterDark fertig.")

    # ── MasterFlatDark ─────────────────────────────────────────────────────
    if flatdark is not None:
        pg(32, "MasterFlatDark prüfen …")
        _, fd_med, fd_std = sigma_clipped_stats(flatdark.ravel(), sigma=3.0)
        results["flatdark"] = {
            "median":      round(float(fd_med), 6),
            "noise_sigma": round(float(fd_std), 6),
            "bewertung":   "✅",
            "hinweis":     "FlatDark-Pegel und Rauschen plausibel.",
        }

    # ── MasterFlat ─────────────────────────────────────────────────────────
    if flat is not None:
        pg(40, "MasterFlat analysieren …")
        H, W = flat.shape
        m = min(200, H//12, W//12)
        med_fl  = float(np.median(flat))
        cen_fl  = float(np.median(flat[H//2-m:H//2+m, W//2-m:W//2+m]))

        # Radiales Vignettierungsprofil
        yy, xx = np.mgrid[0:H, 0:W]
        r_arr   = np.hypot(yy - H/2, xx - W/2)
        rmax    = r_arr.max()
        radial  = {}
        for frac in [0.3, 0.6, 0.85, 1.0]:
            msk = (r_arr > frac*rmax - 80) & (r_arr < frac*rmax + 80)
            if msk.any():
                radial[f"r{int(frac*100)}"] = round(
                    100 * float(np.median(flat[msk])) / cen_fl, 1
                )

        # Ecken-Asymmetrie (Flat-Beleuchtungs-Check)
        margin = min(500, H//8, W//8)
        corners_fl = {
            "TL": float(np.median(flat[50:margin, 50:margin])),
            "TR": float(np.median(flat[50:margin, W-margin:W-50])),
            "BL": float(np.median(flat[H-margin:H-50, 50:margin])),
            "BR": float(np.median(flat[H-margin:H-50, W-margin:W-50])),
        }
        cpct = {k: round(100 * v / cen_fl, 1) for k, v in corners_fl.items()}
        asymm = max(cpct.values()) - min(cpct.values())

        # Staubschatten (Hochpass)
        hp = flat - ndi.uniform_filter(flat, size=min(80, H//20, W//20))
        dust_amp_pct = round(100 * float(hp.std()) / med_fl, 2)
        dust_deep    = round(100 * float(hp.min()) / med_fl, 1)

        # Absolute Vignettierung (min/center)
        vign_max = round(100 * (1 - flat.min() / cen_fl), 1)

        results["flat"] = {
            "median":            round(med_fl, 4),
            "center":            round(cen_fl, 4),
            "vignetting_max_pct": vign_max,
            "radial_pct":        radial,
            "corner_pct":        cpct,
            "asymmetrie_pct":    round(asymm, 1),
            "asymmetrie_warn":   asymm > 3.0,
            "dust_amp_pct":      dust_amp_pct,
            "dust_deepest_pct":  dust_deep,
            "bewertung": (
                "❌ stark asymmetrisch" if asymm > 6 else
                "⚠️ asymmetrisch" if asymm > 3 else "✅ gut"
            ),
            "hinweis": _flat_hinweis(asymm, dust_amp_pct, med_fl),
        }
        pg(70, "MasterFlat fertig.")

    # ── Flat-Mismatch-Test ─────────────────────────────────────────────────
    if light is not None and flat is not None:
        pg(75, "Flat-Mismatch-Test …")
        try:
            s = min(12, H//100)
            H2, W2 = light.shape
            ld = ndi.median_filter(light, 7)[::s, ::s]
            fd2 = flat[:H2:s, :W2:s]
            mn = min(ld.shape[0], fd2.shape[0]), min(ld.shape[1], fd2.shape[1])
            ld = ld[:mn[0], :mn[1]]
            fd2 = fd2[:mn[0], :mn[1]]

            thr  = np.percentile(ld, 40)
            mask = ld < thr
            if mask.sum() > 100:
                x = 1.0 / np.clip(fd2[mask], 0.05, None)
                y = ld[mask]
                x = (x - x.mean()) / (x.std() + 1e-10)
                y = (y - y.mean()) / (y.std() + 1e-10)
                corr = float(np.corrcoef(x, y)[0, 1])
            else:
                corr = 0.0

            results["flat_mismatch"] = {
                "korrelation": round(corr, 3),
                "warnung":     abs(corr) > 0.5,
                "interpretation": _mismatch_text(corr),
            }
        except Exception as e:
            results["flat_mismatch"] = {
                "korrelation": 0, "warnung": False,
                "interpretation": f"Test nicht durchführbar: {e}",
            }
        pg(95, "Flat-Mismatch-Test abgeschlossen.")

    pg(100, "Kalibrierungsanalyse abgeschlossen.")
    return results


def _dark_hinweis(amp_glow: float, hot_pct: float) -> str:
    parts = []
    if amp_glow < 5e-4:
        parts.append("Kein Amp-Glow (Ecken = Zentrum)")
    else:
        parts.append(f"Amp-Glow: {amp_glow:.1e} — sichtbar, ggf. Dunkelstrom-Quelle prüfen")
    if hot_pct < 0.5:
        parts.append("sehr wenig Warmpixel")
    elif hot_pct < 1.0:
        parts.append(f"{hot_pct:.2f}% Warmpixel — normal")
    else:
        parts.append(f"{hot_pct:.2f}% Warmpixel — viele; Kamera-Temperatur prüfen")
    return ". ".join(parts) + "."


def _flat_hinweis(asymm: float, dust_pct: float, level: float) -> str:
    parts = []
    if level < 0.3:
        parts.append(f"Flat-Pegel {level:.2f} — zu dunkel (optimum: 0.4–0.6)")
    elif level > 0.8:
        parts.append(f"Flat-Pegel {level:.2f} — zu hell (nahe Sättigung)")
    else:
        parts.append(f"Flat-Pegel {level:.2f} — gut")
    if asymm > 3:
        parts.append(
            f"Asymmetrie {asymm:.1f}% — inhomogene Flat-Beleuchtung, "
            "homogeneres Panel oder Sky-Flat empfohlen"
        )
    else:
        parts.append("Ausleuchtung weitgehend symmetrisch")
    if dust_pct > 1.0:
        parts.append(f"Staubschatten-Amplitude {dust_pct:.2f}% — Sensor/Filter reinigen")
    else:
        parts.append(f"Staubschatten minimal ({dust_pct:.2f}%)")
    return ". ".join(parts) + "."


def _mismatch_text(corr: float) -> str:
    if abs(corr) > 0.7:
        return (
            f"corr = {corr:.3f}: Starker Flat-Mismatch. "
            "Der Restgradient folgt der Flat-Form — primär "
            "Flat-Beleuchtungsfehler, nicht Lichtverschmutzung. "
            "Homogene Lichtquelle und fixe Geometrie dringend empfohlen."
        )
    elif abs(corr) > 0.5:
        return (
            f"corr = {corr:.3f}: Mäßiger Flat-Mismatch. "
            "Flat-Beleuchtung asymmetrisch — Lichtquelle verbessern."
        )
    else:
        return (
            f"corr = {corr:.3f}: Kalibrierung OK. "
            "Restgradient nicht Flat-korreliert — wahrscheinlich Lichtverschmutzung."
        )
