"""
AstroAnalyzer – Modul 5: Hauptobjekte / Galaxienanalyse
Detektion · NGC/IC-Abgleich · PGC-Kandidaten · Annotation · Beschreibungen
"""

import numpy as np
import warnings
warnings.filterwarnings("ignore")

from astropy.stats import sigma_clipped_stats
from astropy.coordinates import SkyCoord
from photutils.background import Background2D, MedianBackground
from photutils.segmentation import detect_sources, SourceCatalog, deblend_sources
import astropy.units as u


# ── Objekt-Beschreibungsdatenbank ──────────────────────────────────────────────

BESONDERE_OBJEKTE = {
    "NGC4565": {
        "name_lang": "NGC 4565 – Die Nadelgalaxie (Caldwell 38)",
        "beschreibung": (
            "NGC 4565 ist der Prototyp einer Edge-on-Spiralgalaxie im Sternbild Coma Berenices "
            "(Haar der Berenike) und eines der beeindruckendsten Objekte am Himmel. "
            "Die Galaxie ist annähernd exakt von der Kante zu sehen (Inklination ~87°), "
            "wodurch das charakteristische, zentrale Staubband direkt sichtbar wird. "
            "Es handelt sich um eine Sb-Spirale mit einem markanten, elongierten Bulge "
            "und einer ausgeprägten Scheibe von etwa 100.000 Lichtjahren Durchmesser, "
            "womit sie unserer Milchstraße sehr ähnlich ist. "
            "Die Entfernung beträgt schätzungsweise 30–40 Millionen Lichtjahre. "
            "NGC 4565 ist das hellste Mitglied der NGC-4565-Gruppe und hat mehrere Begleitgalaxien, "
            "darunter NGC 4562 im Südwesten. "
            "Historisch wurde NGC 4565 von William Herschel am 6. April 1785 entdeckt."
        ),
    },
    "NGC4555": {
        "name_lang": "NGC 4555 – Isolierte Elliptische mit Röntgen-Gashalo",
        "beschreibung": (
            "NGC 4555 ist eine elliptische Galaxie (Typ E) und physisch KEIN Mitglied der "
            "Coma-I-Gruppe, sondern ein Hintergrundobjekt bei z ≈ 0.022 (ca. 300 Mio. Lj.). "
            "Sie ist bekannt für einen ausgedehnten heißen Röntgen-Gashalo von ~100 kpc Radius, "
            "ungewöhnlich groß für eine isolierte Elliptische. "
            "Dies deutet auf eine extrem massive Dunkle-Materie-Hülle hin. "
            "Im optischen Bild erscheint sie als diffuses, rundes Gebilde ohne erkennbare Struktur — "
            "die hellste Hintergrundgalaxie im Feld nach NGC 4565."
        ),
    },
    "NGC4562": {
        "name_lang": "NGC 4562 – Physischer Begleiter von NGC 4565",
        "beschreibung": (
            "NGC 4562 (auch als NGC 4565A katalogisiert) ist eine Balkenspiralgalaxie (SBcd), "
            "die ebenfalls nahezu edge-on zu sehen ist. "
            "Sie ist ein physischer Begleiter von NGC 4565 im gleichen Gravitationssystem "
            "und liegt im Südwesten der Nadelgalaxie. "
            "Die Galaxie ist kleiner und weniger regelmäßig als NGC 4565, "
            "zeigt aber dasselbe charakteristische Edge-on-Profil."
        ),
    },
    "NGC4556": {
        "name_lang": "NGC 4556 – Elliptische am Bildrand",
        "beschreibung": (
            "NGC 4556 ist eine elliptische Galaxie am östlichen Rand des Bildfeldes. "
            "Sie ist ein weiteres Mitglied des Coma-Hintergrunds und erscheint als "
            "kompaktes, diffuses Objekt ohne erkennbare interne Struktur."
        ),
    },
}

HUBBLE_BESCHREIBUNG = {
    "Sa":  "Spiralgalaxie (Typ Sa): sehr enger Spiralarm-Pitch, großer Bulge",
    "Sb":  "Spiralgalaxie (Typ Sb): ausgeprägter Bulge, moderater Spiralarm-Pitch",
    "Sc":  "Spiralgalaxie (Typ Sc): kleiner Bulge, offene, weitgeschwungene Spiralarme",
    "Sd":  "Spiralgalaxie (Typ Sd): sehr kleiner Bulge, sehr offene Spiralarme",
    "SBa": "Balkenspiralgalaxie (Typ SBa): starker Balken, enger Spiralarm-Pitch",
    "SBb": "Balkenspiralgalaxie (Typ SBb): ausgeprägter Balken, moderater Pitch",
    "SBc": "Balkenspiralgalaxie (Typ SBc): Balken, offene Spiralarme",
    "SBcd":"Balkenspiralgalaxie (Typ SBcd): schwacher Balken, sehr offene flockige Spiralarme",
    "SBd": "Balkenspiralgalaxie (Typ SBd): minimaler Balken, sehr offene Arme",
    "E":   "Elliptische Galaxie: keine Spiralstruktur, reine Sternsphäroide",
    "E0":  "Elliptische Galaxie (E0): nahezu kugelförmig",
    "S0":  "Linsengalaxie (S0): Scheibe ohne Spiralarme",
    "S0-a":"Linsengalaxie (S0-a): Übergangstyp zwischen Linsen- und Spiralgalaxie",
    "I":   "Irreguläre Galaxie: keine klar erkennbare morphologische Struktur",
    "Im":  "Magellansche irreguläre Galaxie: flockige, asymmetrische Struktur",
    "SBm": "Magellansch-balken-irreguläre: zwischen Balkenspiral und irregulär",
    "Sab": "Spiralgalaxie (Sab): Übergang Sa→Sb",
    "Sbc": "Spiralgalaxie (Sbc): Übergang Sb→Sc",
    "Scd": "Spiralgalaxie (Scd): Übergang Sc→Sd",
}


def beschreibe_objekt(name: str, data: dict) -> str:
    """Gibt ausführliche Textbeschreibung zurück."""
    if name in BESONDERE_OBJEKTE:
        o = BESONDERE_OBJEKTE[name]
        return f"**{o['name_lang']}**\n\n{o['beschreibung']}"
    hubble = data.get("hubble", "")
    typ_text = HUBBLE_BESCHREIBUNG.get(hubble, f"Galaxie (Hubble-Typ: {hubble or 'unbekannt'})")
    B = data.get("B"); maj = data.get("maj")
    lines = [f"**{name}** — {typ_text}"]
    if B:   lines.append(f"Scheinbare Helligkeit: B = {B:.1f} mag")
    if maj: lines.append(f"Scheinbare Ausdehnung: {maj:.2f}′ (Hauptachse)")
    return "\n".join(lines)


# ── Haupt-Analyse ──────────────────────────────────────────────────────────────

def run(img: np.ndarray, wcs, pixel_scale: float, progress_cb=None) -> dict:
    """
    img          : 2D float32, normalisiert 0..1
    wcs          : astropy.wcs.WCS oder None
    pixel_scale  : Bogensekunden/Pixel
    """
    def pg(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    H, W = img.shape

    # ── Hintergrundsubtraktion ─────────────────────────────────────────────
    pg(5, "Hintergrundmodell berechnen …")
    bkg = Background2D(img, (128, 128), filter_size=(5, 5),
                       bkg_estimator=MedianBackground())
    sub = img - bkg.background
    _, med, std = sigma_clipped_stats(sub, sigma=3.0)

    # ── Quell-Detektion ────────────────────────────────────────────────────
    pg(15, "Quellen detektieren …")
    seg = detect_sources(sub, 1.5 * std, npixels=20)
    if seg is None:
        return _leer_result()
    pg(30, "Quellen deblenden …")
    seg = deblend_sources(sub, seg, npixels=20, nlevels=32, contrast=0.005)
    cat = SourceCatalog(sub, seg)
    t   = cat.to_table()

    smaj  = np.array(t["semimajor_axis"])
    area  = np.array(t["area"])
    ecc   = np.array(t["eccentricity"])
    xc    = np.array(t["x_centroid"])
    yc    = np.array(t["y_centroid"])
    flux  = np.array(t["segment_flux"])
    mx    = np.array(t["max_value"])
    smin  = np.array(t["semiminor_axis"])

    # Stellare Referenz-PSF
    star_ref = float(np.median(smaj[(smaj > 1.0) & (smaj < 3.5)])) if (
        (smaj > 1.0) & (smaj < 3.5)).any() else 2.0

    # Morphologie-Filter (galaxienartig)
    gal_mask = (smaj > star_ref * 1.8) & (area >= 30) & (ecc < 0.9) & (mx < 0.85)
    cand = np.column_stack([xc, yc, area, smaj, smin, ecc, flux, mx])[gal_mask]

    pg(50, f"{len(cand)} Galaxienkandidaten gefunden …")

    # ── NGC/IC-Katalogabgleich ─────────────────────────────────────────────
    cat_hits = []
    if wcs is not None:
        pg(55, "NGC/IC-Katalog laden …")
        try:
            from pyongc import ongc
            ngc_objs = ongc.listObjects(type=["G", "GPair", "GGroup", "GTrpl", "GClus"])
            pg(62, f"Koordinaten prüfen ({len(ngc_objs)} Objekte) …")
            for o in ngc_objs:
                try:
                    (rh, rm, rs), (dh, dm, ds) = o.coords
                    ra  = (rh + rm/60 + rs/3600) / 24 * 360
                    dec = (abs(dh) + dm/60 + ds/3600) * (-1 if str(o.dec).startswith("-") else 1)
                    px_, py_ = wcs.world_to_pixel(SkyCoord(ra * u.deg, dec * u.deg))
                    if 0 <= float(px_) <= W and 0 <= float(py_) <= H:
                        mags = o.magnitudes
                        dim  = o.dimensions
                        cat_hits.append({
                            "name":   o.name,
                            "type":   o.type,
                            "hubble": str(o.hubble) if o.hubble else "",
                            "ra":     round(ra, 6),
                            "dec":    round(dec, 6),
                            "x":      round(float(px_), 1),
                            "y":      round(float(py_), 1),
                            "B":      float(mags[0]) if mags and mags[0] else None,
                            "V":      float(mags[1]) if mags and len(mags)>1 and mags[1] else None,
                            "maj":    float(dim[0])  if dim  and dim[0]  else None,
                            "min_ax": float(dim[1])  if dim  and len(dim)>1 and dim[1] else None,
                        })
                except Exception:
                    continue
        except ImportError:
            pass

    pg(72, "Halo-Fragmente ausschließen …")

    # Halo-Fragment-Ausschluss
    def near_bright(x, y):
        for h in [c for c in cat_hits if c.get("B") and c["B"] < 15.5]:
            rad = max(120, (h.get("maj") or 0.3) * 60 / pixel_scale * 0.9)
            if np.hypot(x - h["x"], y - h["y"]) < rad:
                return True
        return False

    # Matching
    pg(78, "Katalog-Matching …")
    matched = set()
    if wcs is not None:
        for h in cat_hits:
            d = np.hypot(cand[:, 0] - h["x"], cand[:, 1] - h["y"])
            j = int(np.argmin(d))
            tol = max(15, (h.get("maj") or 0.3) * 60 / pixel_scale * 0.5)
            if d[j] < tol:
                matched.add(j)

    # PGC-Kandidaten
    pg(85, "PGC-Kandidaten klassifizieren …")
    pgc_cands = []
    for i in range(len(cand)):
        if i in matched or near_bright(cand[i, 0], cand[i, 1]):
            continue
        ra_c = dec_c = None
        if wcs is not None:
            try:
                sk = wcs.pixel_to_world(cand[i, 0], cand[i, 1])
                ra_c  = round(float(sk.ra.deg), 6)
                dec_c = round(float(sk.dec.deg), 6)
            except Exception:
                pass

        if   cand[i,3]>star_ref*2.5 and cand[i,2]>=60 and cand[i,5]<0.85 and cand[i,6]>0.15:
            conf = "HIGH"
        elif cand[i,3]>star_ref*2.0 and cand[i,2]>=35 and cand[i,5]<0.90 and cand[i,6]>0.05:
            conf = "MITTEL"
        else:
            conf = "NIEDRIG"

        pgc_cands.append({
            "ra": ra_c, "dec": dec_c,
            "x": round(float(cand[i,0]), 1),
            "y": round(float(cand[i,1]), 1),
            "area": int(cand[i,2]),
            "smaj": round(float(cand[i,3]), 1),
            "ecc":  round(float(cand[i,5]), 3),
            "konfidenz": conf,
        })

    pg(95, "Objektbeschreibungen generieren …")

    # Beschreibungen für Hauptobjekte
    beschreibungen = {}
    for h in sorted(cat_hits, key=lambda x: x.get("B") or 99)[:8]:
        beschreibungen[h["name"]] = beschreibe_objekt(h["name"], h)

    pg(100, f"Galaxienanalyse abgeschlossen: {len(cat_hits)} NGC/IC, "
             f"{sum(1 for p in pgc_cands if p['konfidenz']=='HIGH')} PGC-HIGH")

    return {
        "ngc_ic":       cat_hits,
        "pgc_kand":     pgc_cands,
        "star_ref_px":  round(star_ref, 2),
        "n_ngc_ic":     len(cat_hits),
        "n_high":       sum(1 for p in pgc_cands if p["konfidenz"] == "HIGH"),
        "n_mittel":     sum(1 for p in pgc_cands if p["konfidenz"] == "MITTEL"),
        "n_niedrig":    sum(1 for p in pgc_cands if p["konfidenz"] == "NIEDRIG"),
        "beschreibungen": beschreibungen,
        "wcs_used":     wcs is not None,
    }


def erstelle_tiefenkarte(img: np.ndarray, results: dict, pixel_scale: float,
                          output_path: str, title: str = "") -> None:
    """Erstellt annotierte PNG-Tiefenkarte."""
    from PIL import Image, ImageDraw, ImageFont
    import os

    H, W = img.shape
    lo, hi = np.percentile(img, [30, 99.8])
    a = np.arcsinh(np.clip((img - lo) / max(hi - lo, 1e-9), 0, 1) * 28) / np.arcsinh(28)
    pim = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("RGB")
    draw = ImageDraw.Draw(pim)

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    def get_font(size):
        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    f_big = get_font(28)
    f_sm  = get_font(18)

    # NGC/IC — Gelb
    for g in results.get("ngc_ic", []):
        r = max(14, (g.get("maj") or 0.4) * 60 / pixel_scale / 2)
        r = min(r, 200)
        px, py = g["x"], g["y"]
        col = (255, 205, 30) if g["name"] == "NGC4565" else (90, 200, 255)
        w  = 4 if g["name"] == "NGC4565" else 2
        draw.ellipse([px-r, py-r, px+r, py+r], outline=col, width=w)
        lab = g["name"].replace("NGC", "NGC ").replace("IC", "IC ")
        fnt = f_big if g["name"] == "NGC4565" else f_sm
        tx, ty = px + r*0.7 + 4, py - r*0.7 - 24
        for dx, dy in ((-1,-1),(1,-1),(-1,1),(1,1)):
            draw.text((tx+dx, ty+dy), lab, font=fnt, fill=(0, 0, 0))
        draw.text((tx, ty), lab, font=fnt, fill=col)

    # PGC HIGH — Magenta
    for p in results.get("pgc_kand", []):
        if p["konfidenz"] == "HIGH":
            draw.ellipse([p["x"]-9, p["y"]-9, p["x"]+9, p["y"]+9],
                         outline=(255, 80, 200), width=2)

    # Header
    n_ngc = results.get("n_ngc_ic", 0)
    n_high = results.get("n_high", 0)
    if title:
        draw.rectangle([0, 0, W, 62], fill=(0, 0, 0))
        draw.text((14, 8), title, font=f_big, fill=(255, 255, 255))
        draw.text((14, 40),
                  f"Gelb/Cyan: {n_ngc} NGC/IC · Magenta: {n_high} PGC-Kandidaten (HIGH)",
                  font=f_sm, fill=(180, 180, 180))

    pim.save(output_path, quality=94)


def _leer_result() -> dict:
    return {
        "ngc_ic": [], "pgc_kand": [], "star_ref_px": 2.0,
        "n_ngc_ic": 0, "n_high": 0, "n_mittel": 0, "n_niedrig": 0,
        "beschreibungen": {}, "wcs_used": False,
    }
