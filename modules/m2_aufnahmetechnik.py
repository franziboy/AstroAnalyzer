"""
AstroAnalyzer – Modul 2: Aufnahmetechnik
Bewertet Sub-Länge, Gain/Offset, Subs-Anzahl, Dithering, Tiefe, Temperatur, Bildskala
"""

import numpy as np


# QHY600M Gain-Tabelle (High Gain Mode 16-bit, empirisch)
QHY600_GAIN_TABLE = {
    0:   (1.00, 7.0, "LCG",          "Standard Low-Conversion-Gain"),
    26:  (0.50, 3.5, "HCG-Eingang",  "Erster HCG-Sprung, Rauschen halbiert"),
    56:  (0.26, 1.4, "HCG-optimal",  "Zweiter HCG-Sprung, ideal für Deep Sky"),
    100: (0.13, 1.2, "HCG-hoch",     "Maximale Empfindlichkeit, voller Well kleiner"),
}

# Generische Gain-Hinweise für andere Kameras
GENERIC_GAIN_HINWEIS = {
    (0,   50): "Niedrig-Gain – geringeres Rauschen, voller Dynamikbereich",
    (50, 150): "Mittel-Gain – Kompromiss Dynamik/Rauschen",
    (150, 999): "Hoch-Gain – maximale Empfindlichkeit, kleinerer Full-Well",
}


def run(meta: dict, img_stats: dict, n_subs_override: int = 0,
        dither_active: bool = True, dither_px: int = 0,
        progress_cb=None) -> dict:
    """
    meta          : Header-Dict aus xisf_reader
    img_stats     : Ergebnis-Dict aus Modul 1
    n_subs_override: falls NCOMBINE im Header fehlt, manuell übergeben
    """
    def pg(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    pg(10, "Belichtungsparameter auswerten …")

    N      = max(n_subs_override or meta.get("NCOMBINE", 1), 1)
    t_sub  = meta.get("EXPTIME", 0)
    gain   = meta.get("GAIN", 0)
    offset = meta.get("OFFSET", 0)
    temp   = meta.get("CCD-TEMP", -10)
    fl     = meta.get("FOCALLEN", 0)
    px_um  = meta.get("XPIXSZ", 3.76)
    instr  = meta.get("INSTRUME", "")
    noise  = img_stats.get("noise_mad", 1e-4)
    banding= img_stats.get("banding_amp", 0)

    results = {}

    # ── Gesamtbelichtung & SNR ─────────────────────────────────────────────
    pg(20, "Tiefe berechnen …")
    total_h   = N * t_sub / 3600 if t_sub > 0 else 0
    snr_gain  = np.sqrt(N)
    dmag_1h   = 2.5 * np.log10(snr_gain) if N > 0 else 0
    stack_noise_floor = noise / snr_gain if snr_gain > 0 else noise

    results["integration"] = {
        "n_subs":         N,
        "t_sub_s":        t_sub,
        "total_h":        round(total_h, 2),
        "snr_gain":       round(snr_gain, 1),
        "dmag_vs_1h":     round(dmag_1h, 2),
        "stack_noise_floor": stack_noise_floor,
        "status": (
            "✅" if total_h >= 3 else
            "⚠️" if total_h >= 1 else "❌"
        ),
        "hinweis": _integration_hinweis(total_h, N),
    }

    # ── Sub-Länge / Himmelslimitierung ─────────────────────────────────────
    pg(35, "Himmelslimitierung prüfen …")
    sub_noise_implied = noise * snr_gain
    results["sub_laenge"] = {
        "t_sub_s":      t_sub,
        "impliziertes_sub_rauschen": round(sub_noise_implied, 6),
        "status": "✅" if t_sub >= 180 else ("⚠️" if t_sub >= 60 else "❌"),
        "hinweis": (
            f"{t_sub:.0f}s — gut himmelslimitiert (bei f/7 und Gain≥56 typisch ab 180–360s)"
            if t_sub >= 180 else
            f"{t_sub:.0f}s — zu kurz für himmelslimitiertes Regime bei f/7, erwäge 180–360s"
        ),
    }

    # ── Gain/Offset-Regime ─────────────────────────────────────────────────
    pg(50, "Gain-Regime einordnen …")
    is_qhy600 = "QHY600" in (instr or "").upper()
    if is_qhy600:
        e_gain, rn, regime, regime_detail = _qhy600_regime(gain)
    else:
        e_gain, rn, regime, regime_detail = _generic_regime(gain)

    results["gain"] = {
        "gain":          gain,
        "offset":        offset,
        "e_gain":        e_gain,
        "read_noise_e":  rn,
        "regime":        regime,
        "regime_detail": regime_detail,
        "kamera":        instr or "unbekannt",
        "status": "✅" if "optimal" in regime.lower() or "hcg" in regime.lower() else "ℹ️",
        "hinweis": regime_detail,
    }

    # ── Dithering-Diagnose ─────────────────────────────────────────────────
    pg(65, "Dithering analysieren …")
    stack_floor  = stack_noise_floor
    dither_ratio = banding / stack_floor if stack_floor > 0 else 0

    if not dither_active:
        results["dithering"] = {
            "banding_amp":      round(banding, 6),
            "stack_floor":      round(stack_floor, 6),
            "ratio":            round(dither_ratio, 2),
            "status":           "❌ deaktiviert",
            "hinweis":          "Kein Dithering aktiv — Banding akkumuliert sich im Stack.",
            "empfehlung_px":    20,
            "manuell_gesetzt":  True,
            "dither_px":        0,
        }
    elif dither_px > 0:
        if dither_px >= 20:
            st   = "✅ ausreichend"
            hint = f"Dither-Amplitude {dither_px} px — gut gewählt."
        elif dither_px >= 10:
            st   = "⚠️ knapp"
            hint = f"Dither-Amplitude {dither_px} px — Banding-Periode prüfen, ggf. auf ≥ 20 px erhöhen."
        else:
            st   = "❌ zu klein"
            hint = f"Dither-Amplitude {dither_px} px — zu klein, Muster dekorreliert nicht zuverlässig."
        results["dithering"] = {
            "banding_amp":      round(banding, 6),
            "stack_floor":      round(stack_floor, 6),
            "ratio":            round(dither_ratio, 2),
            "status":           st,
            "hinweis":          hint,
            "empfehlung_px":    max(20, dither_px),
            "manuell_gesetzt":  True,
            "dither_px":        dither_px,
        }
    else:
        if dither_ratio > 2.0:
            dither_status  = "❌"
            dither_hinweis = (
                f"Pattern dominiert Stack-Rauschen um {dither_ratio:.1f}×. "
                f"Dither auf ≥ 30 px erhöhen."
            )
        elif dither_ratio > 0.5:
            dither_status  = "⚠️"
            dither_hinweis = f"Pattern {dither_ratio:.1f}× Stack-Rauschen — Amplitude erhöhen (≥ 15–20 px)."
        else:
            dither_status  = "✅"
            dither_hinweis = "Dithering wirksam."
        results["dithering"] = {
            "banding_amp":      round(banding, 6),
            "stack_floor":      round(stack_floor, 6),
            "ratio":            round(dither_ratio, 2),
            "status":           dither_status,
            "hinweis":          dither_hinweis,
            "empfehlung_px":    30 if dither_ratio > 2 else (20 if dither_ratio > 0.5 else 10),
            "manuell_gesetzt":  False,
            "dither_px":        0,
        }

    # ── Temperatur ─────────────────────────────────────────────────────────
    pg(80, "Thermische Bewertung …")
    results["temperatur"] = {
        "temp_c":  temp,
        "status":  "✅" if temp <= -10 else ("⚠️" if temp <= 0 else "❌"),
        "hinweis": (
            f"{temp:.1f}°C — optimal für QHY600M (Dunkelstrom minimal)" if temp <= -10 else
            f"{temp:.1f}°C — Dunkelstrom erhöht, Kühlung auf ≤ −10°C empfohlen"
        ),
    }

    # ── Bildskala ──────────────────────────────────────────────────────────
    pg(90, "Bildskala berechnen …")
    scale_arcsec = 0
    if fl > 0 and px_um > 0:
        scale_arcsec = round(206265 * px_um / 1000 / fl, 3)
    fwhm_arcsec = img_stats.get("fwhm_arcsec", 0)

    if scale_arcsec > 0:
        nyquist_ok = scale_arcsec <= fwhm_arcsec / 2.0
        results["bildskala"] = {
            "scale_arcsec_px": scale_arcsec,
            "focallen_mm":     fl,
            "pixel_um":        px_um,
            "nyquist_ok":      nyquist_ok,
            "status": "✅" if nyquist_ok else "ℹ️",
            "hinweis": (
                f"{scale_arcsec}\"/px — seeing-limitiert (FWHM {fwhm_arcsec}\")"
                if scale_arcsec <= 0.9 else
                f"{scale_arcsec}\"/px — grob gesampelt"
            ),
        }

    pg(100, "Aufnahmetechnik-Analyse abgeschlossen.")
    return results


def _qhy600_regime(gain: int):
    for threshold in sorted(QHY600_GAIN_TABLE.keys(), reverse=True):
        if gain >= threshold:
            return QHY600_GAIN_TABLE[threshold]
    return QHY600_GAIN_TABLE[0]


def _generic_regime(gain: int):
    for (lo, hi), hint in GENERIC_GAIN_HINWEIS.items():
        if lo <= gain < hi:
            return 0.5, 3.0, f"Gain {gain}", hint
    return 0.5, 3.0, f"Gain {gain}", "Gain-Wert im mittleren Bereich"


def _integration_hinweis(total_h: float, N: int) -> str:
    if total_h >= 10:
        return f"{total_h:.1f}h ({N} Subs) — sehr tiefe Integration, Grenzgröße ~22+ mag"
    elif total_h >= 5:
        return f"{total_h:.1f}h — gute Tiefe, Grenzgröße ~21–22 mag"
    elif total_h >= 2:
        return f"{total_h:.1f}h — moderate Tiefe, für helle Objekte ausreichend"
    elif total_h >= 0.5:
        return f"{total_h:.1f}h — geringe Tiefe, schwache Objekte kaum sichtbar"
    else:
        return f"{total_h:.1f}h — sehr kurz"


def empfehlungen(results: dict, img_stats: dict) -> list[str]:
    """Gibt priorisierte Textempfehlungen zurück."""
    recs = []
    d = results.get("dithering", {})
    if d.get("ratio", 0) > 0.5:
        recs.append(f"🔴 Dithering: Amplitude auf {d.get('empfehlung_px', 20)} px erhöhen "
                    f"(aktuell Pattern {d.get('ratio','?')}× über Stack-Rauschen)")
    g = results.get("gain", {})
    if g.get("regime") == "LCG":
        recs.append("🟡 Gain: Höheren Gain-Wert erwägen (QHY600M: Gain 56 = HCG-optimal)")
    t = results.get("temperatur", {})
    if t.get("temp_c", 0) > -10:
        recs.append(f"🟡 Temperatur: {t['temp_c']:.1f}°C — auf ≤ −10°C kühlen")
    i = results.get("integration", {})
    if i.get("total_h", 0) < 3:
        recs.append(f"🟡 Belichtungszeit: {i.get('total_h','?')}h — mehr Subs sammeln für Tiefe")
    s = results.get("sub_laenge", {})
    if s.get("t_sub_s", 0) < 180:
        recs.append(f"🟡 Sub-Länge: {s.get('t_sub_s','?')}s — zu kurz, 300–600s empfohlen")
    if not recs:
        recs.append("✅ Alle Aufnahme-Parameter in Ordnung")
    return recs
