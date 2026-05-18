"""
AstroAnalyzer – Modul 6: PixInsight JavaScript Workflow Generator
Erzeugt ein PI-Script (.js) basierend auf den Analyseergebnissen.
"""

from __future__ import annotations
from datetime import datetime
from pathlib import Path


def run(m1: dict, m2: dict, m3: list, m4: dict,
        meta: dict, output_path: str) -> None:
    """Generate a PixInsight JavaScript workflow script."""

    obj     = meta.get("OBJECT", "Unbekannt")
    date    = meta.get("DATE-OBS", datetime.now().strftime("%Y-%m-%d"))[:10]
    gain    = meta.get("GAIN", 0)
    exptime = meta.get("EXPTIME", 0)
    filt    = meta.get("FILTER", "L")

    fwhm    = m1.get("fwhm_median_px", 0)
    noise   = m1.get("noise_mad", 0)
    grad    = m1.get("gradient_pct", 0)
    banding = m1.get("banding_amp", 0)
    ecc     = m1.get("ecc_median", 0)

    gain_info = m2.get("gain", {})
    read_noise = gain_info.get("read_noise_e", 1.0)
    full_well  = gain_info.get("full_well_e", 50000)

    dk = m4.get("dark", {})
    amp_glow   = dk.get("amp_glow", 0) or 0
    hot_px_pct = dk.get("hot_px_pct", 0) or 0

    # ABE empfehlen wenn Gradient > 5%
    abe_needed = grad > 5.0
    # DBE empfehlen wenn Gradient > 15%
    dbe_needed = grad > 15.0
    # MultiscaleLinearTransform wenn Banding sichtbar
    mlt_banding = banding > 1e-4
    # StarAlignment-Sigma aus FWHM ableiten
    star_sigma  = max(1.5, round(fwhm * 0.8, 1))
    # TGVDenoise empfehlen wenn Rauschen hoch
    tgv_needed  = noise > 5e-4
    # CosmeticCorrection wenn viele Hotpixel
    cc_needed   = hot_px_pct > 0.5

    suggestions = "\n".join(f"// - {r}" for r in m3) if m3 else "// (keine)"

    js = f"""// ============================================================
// AstroAnalyzer – PixInsight Workflow Script
// Objekt  : {obj}
// Datum   : {date}
// Filter  : {filt}
// Gain    : {gain}  |  Belichtung: {exptime}s
// Erzeugt : {datetime.now().strftime("%Y-%m-%d %H:%M")}
// ============================================================
//
// Analysewerte:
//   FWHM median     : {fwhm:.2f} px
//   Noise (MAD)     : {noise:.2e}
//   Gradient        : {grad:.1f}%
//   Banding-Amp     : {banding:.2e}
//   Exzentrizität   : {ecc:.3f}
//   Amp-Glow        : {amp_glow:.2e}
//   Hot-Pixel       : {hot_px_pct:.2f}%
//
// PixInsight-Empfehlungen:
{suggestions}
// ============================================================

#include <pjsr/StdButton.jsh>
#include <pjsr/StdIcon.jsh>

// ── Hilfsfunktion ─────────────────────────────────────────
function applyProcess(proc, view) {{
   proc.executeOn(view, false);
}}

// ── Hauptworkflow ──────────────────────────────────────────
function main() {{
   var target = ImageWindow.activeWindow.mainView;
   if (!target.isNull) {{
      Console.writeln("AstroAnalyzer Workflow – " + "{obj}");
   }}

{_cosmetic_block(cc_needed, hot_px_pct)}
{_abe_block(abe_needed, grad)}
{_dbe_block(dbe_needed, grad)}
{_banding_block(mlt_banding, banding)}
{_denoise_block(tgv_needed, noise)}
{_star_block(star_sigma, fwhm)}
{_stretch_block(noise)}
{chr(10).join("   " + l for l in _step_screen())}

   Console.writeln("Workflow abgeschlossen.");
}}

main();
"""

    Path(output_path).write_text(js, encoding="utf-8")


# ── Block-Generatoren ─────────────────────────────────────

def _cosmetic_block(needed: bool, hot_pct: float) -> str:
    if not needed:
        return "   // CosmeticCorrection: nicht erforderlich (Hot-Pixel < 0.5%)"
    return f"""   // CosmeticCorrection – Hot-Pixel: {hot_pct:.2f}%
   var cc = new CosmeticCorrection;
   cc.hotDarkCheck = true;
   cc.hotDarkLevel = 3.0;
   // applyProcess(cc, target);  // Pfade anpassen, dann aktivieren"""


def _abe_block(needed: bool, grad: float) -> str:
    if not needed:
        return f"   // ABE: nicht erforderlich (Gradient {grad:.1f}% < 5%)"
    return f"""   // AutomaticBackgroundExtraction – Gradient: {grad:.1f}%
   var abe = new AutomaticBackgroundExtraction;
   abe.degree = 1;
   abe.unclippedMode = false;
   // applyProcess(abe, target);"""


def _dbe_block(needed: bool, grad: float) -> str:
    if not needed:
        return f"   // DBE: optional (Gradient {grad:.1f}%)"
    return f"""   // DynamicBackgroundExtraction empfohlen – Gradient: {grad:.1f}%
   // Manuell in PI durchführen: Script > DynamicBackgroundExtraction"""


def _banding_block(needed: bool, amp: float) -> str:
    if not needed:
        return f"   // Banding-Korrektur: nicht erforderlich (Amp {amp:.2e})"
    return f"""   // MultiscaleLinearTransform – Banding sichtbar (Amp {amp:.2e})
   var mlt = new MultiscaleLinearTransform;
   mlt.layers = [[true, true, 0.000, false, 3.000, 0.50, true],
                 [true, true, 0.000, false, 2.000, 0.50, true],
                 [true, true, 0.000, false, 1.000, 0.50, true],
                 [false, true, 0.000, false, 1.000, 0.50, true]];
   // applyProcess(mlt, target);"""


def _denoise_block(needed: bool, noise: float) -> str:
    if not needed:
        return f"   // TGVDenoise: optional (Noise {noise:.2e})"
    strength = min(0.9, round(noise * 1500, 2))
    return f"""   // TGVDenoise – Rauschen: {noise:.2e}
   var tgv = new TGVDenoise;
   tgv.strengthL = {strength};
   tgv.strengthC = {round(strength * 0.5, 2)};
   tgv.iterations = 100;
   // applyProcess(tgv, target);"""


def _step_screen() -> list[str]:
    return [
        f'// ── Schritt 7: PixelMath — Screen-Rekombination ───────────────',
        f'// Sterne (stars_layer) mit Galaxienebene screen-kombinieren.',
        f'// Screen verhindert Überstrahlung der Sternkerne.',
        f'Console.writeln("── Schritt 7: Screen-Rekombination ──");',
        f'Console.writeln("  Manuell (falls StarXT genutzt wurde):");',
        f'Console.writeln("  PixelMath: ~(~$T*~stars_layer)");',
        f'Console.writeln("  Ziel-Bild: sternlose Galaxienebene (aktuelles Fenster)");',
        f'',
        f'// Automatisch — StarXT benennt Sternfenster als <original>_stars',
        f'var starsId = view.id + "_stars";',
        f'var starsWindow = ImageWindow.windowById(starsId);',
        f'if (starsWindow.isNull) {{',
        f'   // Fallback: alle Fenster nach "_stars" durchsuchen',
        f'   var allWindows = ImageWindow.windows;',
        f'   for (var i = 0; i < allWindows.length; i++) {{',
        f'      if (allWindows[i].mainView.id.indexOf("_stars") >= 0) {{',
        f'         starsWindow = allWindows[i]; break;',
        f'      }}',
        f'   }}',
        f'}}',
        f'if (!starsWindow.isNull) {{',
        f'   var pm = new PixelMath();',
        f'   pm.expression  = "~(~$T*~" + starsWindow.mainView.id + ")";',
        f'   pm.useSingleExpression = true;',
        f'   pm.createNewImage = false;',
        f'   pm.executeOn(view);',
        f'   Console.writeln("  Screen-Kombination ausgeführt: ~(~Galaxien * ~Sterne)");',
        f'}} else {{',
        f'   Console.writeln("  Kein Sternfenster gefunden — manuelle Rekombination nötig.");',
        f'   Console.writeln("  PixelMath: ~(~$T*~<sternfenster_id>)");',
        f'}}',
        f'',
    ]


def _star_block(sigma: float, fwhm: float) -> str:
    return f"""   // StarAlignment-Parameter (FWHM {fwhm:.1f} px)
   // Empfohlen: StarAlignment mit structureLayers=5, noiseLayers=0,
   //            hotPixelFilterRadius=1, sensitivity=-1.00,
   //            peakResponse=0.50, minStructureSize={int(fwhm*0.5)}"""


def _stretch_block(noise: float) -> str:
    bp = min(0.1, round(noise * 5, 4))
    return f"""   // HistogramTransformation – Empfohlener Black Point
   var ht = new HistogramTransformation;
   ht.H = [[0, 0.5, 1, 0, 1],
           [0, 0.5, 1, 0, 1],
           [0, 0.5, 1, 0, 1],
           [{bp}, 0.5, 1, 0, 1],
           [0, 0.5, 1, 0, 1]];
   // applyProcess(ht, target);"""
