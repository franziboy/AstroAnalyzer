"""
AstroAnalyzer – Modul 7b: Finder Chart
DSS-Hintergrund via hips2fits, Sternatlas-Stil, FOV-Rechteck.
"""

import numpy as np
import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

from astropy.coordinates import SkyCoord
import astropy.units as u
import math

# ── Farben ─────────────────────────────────────────────────────────────────
SKY_BG   = "#06060e"
GRID_COL = "#151528"
STAR_COL = "#d0deff"
CON_LINE = "#2a3a5a"
CON_NAME = "#3a6a3a"
FOV_COL  = "#FF4040"
OBJ_COL  = "#FFD700"
TEXT_COL = "#e0e8ff"
LABEL_FG = "#8090b0"


CONSTELLATION_LINES = {
    "Com": [
        (185.34, 27.88, 183.86, 28.27),
        (183.86, 28.27, 194.01, 28.27),
        (183.86, 28.27, 181.92, 14.56),
    ],
    "CVn": [
        (194.01, 38.32, 196.55, 38.84),
    ],
    "Boo": [
        (213.92, 19.18, 218.01, 40.39),
        (218.01, 40.39, 216.90, 37.36),
        (216.90, 37.36, 220.48, 36.72),
        (216.90, 37.36, 211.59, 37.93),
        (211.59, 37.93, 213.92, 19.18),
        (218.01, 40.39, 219.17, 40.39),
    ],
    "Vir": [
        (190.42, -11.16, 193.90, -11.16),
        (193.90, -11.16, 201.30,  -4.40),
        (201.30,  -4.40, 202.76,   0.59),
        (202.76,   0.59, 198.81,  10.96),
        (198.81,  10.96, 188.60,   1.55),
    ],
    "Leo": [
        (152.09, 11.97, 154.17, 23.77),
        (154.17, 23.77, 158.43, 26.01),
        (158.43, 26.01, 163.33, 19.84),
        (163.33, 19.84, 168.53, 15.43),
        (168.53, 15.43, 177.26, 14.57),
        (177.26, 14.57, 174.17, 10.05),
        (174.17, 10.05, 168.53, 15.43),
        (168.53, 15.43, 152.09, 11.97),
    ],
    "UMa": [
        (165.46, 61.75, 178.46, 53.69),
        (178.46, 53.69, 183.86, 57.03),
        (183.86, 57.03, 193.51, 55.96),
        (193.51, 55.96, 200.98, 54.93),
        (200.98, 54.93, 206.89, 49.31),
        (206.89, 49.31, 210.96, 47.16),
        (200.98, 54.93, 205.14, 49.64),
    ],
}


def finder_chart(meta: dict, wcs, img_shape: tuple,
                 output_path: str,
                 fov_deg: float = 10.0,
                 progress_cb=None) -> bool:
    """
    Finder Chart: DSS-Hintergrund (hips2fits) + Sternatlas-Overlays.
    fov_deg : Gesamtfeld des Charts in Grad (Standard 10°)
    """
    def pg(pct, msg):
        if progress_cb: progress_cb(pct, msg)

    # ── Koordinaten ────────────────────────────────────────────────────────
    ra_c = dec_c = None
    if wcs is not None:
        try:
            H, W = img_shape
            sk = wcs.pixel_to_world(W / 2, H / 2)
            ra_c, dec_c = float(sk.ra.deg), float(sk.dec.deg)
        except Exception:
            pass
    if ra_c is None:
        ra_c  = float(meta.get("RA")  or 0)
        dec_c = float(meta.get("DEC") or 0)
    if not ra_c and not dec_c:
        return False

    target = meta.get("OBJECT") or "Unbekannt"
    filt   = meta.get("FILTER") or "?"

    try:
        from astropy.coordinates import get_constellation
        constellation = get_constellation(SkyCoord(ra_c * u.deg, dec_c * u.deg))
    except Exception:
        constellation = ""

    pg(5, "Finder Chart aufbauen …")

    # ── Figure ─────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 12), facecolor=SKY_BG)
    ax.set_facecolor(SKY_BG)

    # ── hips2fits: DSS-Hintergrundbild ─────────────────────────────────────
    pg(10, f"DSS {fov_deg:.0f}° herunterladen …")
    dss_wcs = None
    dss_loaded = False
    px_size = 1800
    try:
        import requests
        from astropy.io import fits as afits
        from astropy.wcs import WCS as AWCS
        from astropy.visualization import ZScaleInterval
        import io

        url = (
            "https://alasky.u-strasbg.fr/hips-image-services/hips2fits?"
            f"hips=CDS%2FP%2FDSS2%2Fred"
            f"&ra={ra_c}&dec={dec_c}"
            f"&fov={fov_deg}"
            f"&width={px_size}&height={px_size}"
            f"&projection=TAN&coordsys=icrs&rotation_angle=0"
            f"&format=fits"
        )
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        hdu  = afits.open(io.BytesIO(resp.content))[0]
        data = hdu.data.astype(float)
        dss_wcs = AWCS(hdu.header)

        interval = ZScaleInterval()
        vmin, vmax = interval.get_limits(data)
        ax.imshow(data, cmap="gray", origin="lower",
                  vmin=vmin, vmax=vmax,
                  extent=[0, px_size, 0, px_size])
        dss_loaded = True
        pg(40, "DSS geladen.")

    except Exception as e:
        pg(40, f"DSS nicht verfügbar ({e}) — dunkler Hintergrund.")
        ax.set_xlim(0, px_size)
        ax.set_ylim(0, px_size)

    # ── Koordinaten-Helper ─────────────────────────────────────────────────
    ra0  = math.radians(ra_c)
    dec0 = math.radians(dec_c)

    def sky_to_plot(ra_deg, dec_deg):
        """RA/Dec → tangentiale Ebene in Grad (Gnomonic, E links)."""
        ra  = math.radians(ra_deg)
        dec = math.radians(dec_deg)
        cos_c = (math.sin(dec0) * math.sin(dec) +
                 math.cos(dec0) * math.cos(dec) * math.cos(ra - ra0))
        if cos_c <= 0:
            return None, None
        x = -(math.cos(dec) * math.sin(ra - ra0)) / cos_c
        y = (math.cos(dec0) * math.sin(dec) -
             math.sin(dec0) * math.cos(dec) * math.cos(ra - ra0)) / cos_c
        return math.degrees(x), math.degrees(y)

    def to_px(ra_deg, dec_deg):
        """RA/Dec → DSS-Pixel (wenn DSS geladen) oder Gnomonic-Fallback."""
        if dss_wcs is not None:
            try:
                sc = SkyCoord(ra_deg * u.deg, dec_deg * u.deg)
                x, y = dss_wcs.world_to_pixel(sc)
                return float(x), float(y)
            except Exception:
                return None, None
        else:
            x, y = sky_to_plot(ra_deg, dec_deg)
            if x is not None:
                s = px_size / fov_deg
                return (x + fov_deg / 2) * s, (y + fov_deg / 2) * s
            return None, None

    # ── Koordinatengitter ──────────────────────────────────────────────────
    pg(42, "Koordinatengitter …")
    step = 5.0 if fov_deg > 20 else (2.0 if fov_deg > 5 else 1.0)
    ra_ticks  = np.arange(ra_c  - fov_deg * 1.5, ra_c  + fov_deg * 1.5, step)
    dec_ticks = np.arange(dec_c - fov_deg * 1.5, dec_c + fov_deg * 1.5, step)

    for dec_g in dec_ticks:
        xs, ys = [], []
        for ra_g in np.linspace(ra_c - fov_deg * 1.5, ra_c + fov_deg * 1.5, 120):
            x, y = to_px(ra_g, dec_g)
            if x is not None and -50 <= x <= px_size + 50 and -50 <= y <= px_size + 50:
                xs.append(x); ys.append(y)
        if xs:
            ax.plot(xs, ys, color=GRID_COL, lw=0.5, alpha=0.8)

    for ra_g in ra_ticks:
        xs, ys = [], []
        for dec_g in np.linspace(max(-85, dec_c - fov_deg * 1.5),
                                   min(85,  dec_c + fov_deg * 1.5), 120):
            x, y = to_px(ra_g, dec_g)
            if x is not None and -50 <= x <= px_size + 50 and -50 <= y <= px_size + 50:
                xs.append(x); ys.append(y)
        if xs:
            ax.plot(xs, ys, color=GRID_COL, lw=0.5, alpha=0.8)

    for dec_g in dec_ticks:
        x, y = to_px(ra_c - fov_deg * 0.48, dec_g)
        if x is not None and 0 <= y <= px_size:
            ax.text(x, y, f"{dec_g:+.0f}°",
                    color=LABEL_FG, fontsize=7, va="center", ha="right")

    for ra_g in ra_ticks:
        x, y = to_px(ra_g, dec_c - fov_deg * 0.46)
        if x is not None and 0 <= x <= px_size:
            h = ra_g / 15; hh = int(h); mm = int((h - hh) * 60)
            ax.text(x, y, f"{hh}h{mm:02d}m",
                    color=LABEL_FG, fontsize=7, ha="center", va="top")

    # ── Sternbildlinien ────────────────────────────────────────────────────
    pg(50, "Sternbildlinien …")
    for con_name, lines in CONSTELLATION_LINES.items():
        all_px = []
        for ra1, dec1, ra2, dec2 in lines:
            x1, y1 = to_px(ra1, dec1)
            x2, y2 = to_px(ra2, dec2)
            if None not in (x1, y1, x2, y2):
                if 0 < x1 < px_size and 0 < y1 < px_size:
                    ax.plot([x1, x2], [y1, y2], color=CON_LINE,
                            lw=1.5, alpha=0.8)
                    all_px += [(x1, y1), (x2, y2)]
        if all_px:
            cx = np.mean([p[0] for p in all_px])
            cy = np.mean([p[1] for p in all_px])
            if 50 < cx < px_size - 50 and 50 < cy < px_size - 50:
                ax.text(cx, cy, con_name, color=CON_NAME,
                        fontsize=11, fontweight="bold",
                        ha="center", va="center", alpha=0.9)

    # ── Sterne (Hipparcos) ─────────────────────────────────────────────────
    pg(55, "Sterne laden (Hipparcos) …")
    try:
        from astroquery.vizier import Vizier
        Vizier.ROW_LIMIT = 3000
        result = Vizier(columns=["RAICRS", "DEICRS", "Vmag"]).query_region(
            SkyCoord(ra_c * u.deg, dec_c * u.deg),
            radius=(fov_deg / 2 * 1.1) * u.deg,
            catalog="I/239/hip_main",
        )
        if result:
            t = result[0]
            ra_s  = np.array(t["RAICRS"])
            dec_s = np.array(t["DEICRS"])
            mag_s = np.array(t["Vmag"])
            valid = np.isfinite(mag_s) & (mag_s < 7.5)
            ra_s, dec_s, mag_s = ra_s[valid], dec_s[valid], mag_s[valid]

            xs_plot, ys_plot, mags_plot = [], [], []
            for ra_i, dec_i, mag_i in zip(ra_s, dec_s, mag_s):
                x, y = to_px(float(ra_i), float(dec_i))
                if x is not None and 0 <= x <= px_size and 0 <= y <= px_size:
                    xs_plot.append(x); ys_plot.append(y)
                    mags_plot.append(mag_i)

            if xs_plot:
                mags_a = np.array(mags_plot)
                sizes  = np.clip((7.5 - mags_a) * 3.5, 0.5, 25) ** 1.8
                alphas = np.clip((7.5 - mags_a) / 6.0, 0.3, 1.0)
                order  = np.argsort(mags_a)[::-1]
                for i in order:
                    ax.plot(xs_plot[i], ys_plot[i], "o",
                            color=STAR_COL, ms=sizes[i] ** 0.5,
                            alpha=float(alphas[i]), zorder=5)
                pg(70, f"{len(xs_plot)} Sterne gezeichnet.")

    except Exception as e:
        pg(70, f"Sterne nicht geladen ({e}).")
        bright_stars = [
            (213.92, 19.18, "Arcturus", 0.0),
            (177.26, 14.57, "Denebola", 2.1),
            (152.09, 11.97, "Regulus",  1.4),
            (206.89, 49.31, "Alkaid",   1.8),
            (200.98, 54.93, "Mizar",    2.3),
        ]
        for ra_b, dec_b, name, mag in bright_stars:
            x, y = to_px(ra_b, dec_b)
            if x is not None and 0 <= x <= px_size and 0 <= y <= px_size:
                sz = max(2, (4 - mag) * 1.5)
                ax.plot(x, y, "o", color=STAR_COL, ms=sz, alpha=0.9, zorder=5)
                ax.text(x + px_size * 0.005, y + px_size * 0.005, name,
                        color=LABEL_FG, fontsize=7, alpha=0.8)

    # ── FOV-Rechteck (Bildecken via WCS) ───────────────────────────────────
    pg(80, "Bildfeld einzeichnen …")
    if wcs is not None:
        H_img, W_img = img_shape
        dss_xs, dss_ys = [], []
        for px, py in [(0, 0), (W_img, 0), (W_img, H_img), (0, H_img), (0, 0)]:
            sk = wcs.pixel_to_world(px, py)
            x, y = to_px(sk.ra.deg, sk.dec.deg)
            if x is not None:
                dss_xs.append(x); dss_ys.append(y)
        if len(dss_xs) == 5:
            ax.plot(dss_xs, dss_ys, color=FOV_COL, lw=2.5, zorder=8)
            ax.fill(dss_xs, dss_ys, color=FOV_COL, alpha=0.10, zorder=7)

    # ── Objekt-Marker ──────────────────────────────────────────────────────
    cx_obj, cy_obj = to_px(ra_c, dec_c)
    if cx_obj is not None:
        ax.plot(cx_obj, cy_obj, "+", color=OBJ_COL, ms=18, mew=2.5, zorder=10)

    # ── N/E-Pfeile ─────────────────────────────────────────────────────────
    if dss_wcs is not None:
        try:
            sc_cen = SkyCoord(ra_c * u.deg, dec_c * u.deg)
            sc_n   = SkyCoord(ra_c * u.deg, (dec_c + 2.0) * u.deg)
            cx, cy = dss_wcs.world_to_pixel(sc_cen)
            nx, ny = dss_wcs.world_to_pixel(sc_n)
            ax.annotate("", xy=(float(nx), float(ny)),
                        xytext=(float(cx), float(cy)),
                        arrowprops=dict(arrowstyle="->", color="#80FF80",
                                        lw=2.0, mutation_scale=16))
            ax.text(float(nx), float(ny) + 20, "N",
                    color="#80FF80", fontsize=12, fontweight="bold",
                    ha="center")
            sc_e = SkyCoord((ra_c - 2.0 / math.cos(math.radians(dec_c))) * u.deg,
                            dec_c * u.deg)
            ex, ey = dss_wcs.world_to_pixel(sc_e)
            ax.annotate("", xy=(float(ex), float(ey)),
                        xytext=(float(cx), float(cy)),
                        arrowprops=dict(arrowstyle="->", color="#FF9040",
                                        lw=2.0, mutation_scale=14))
            ax.text(float(ex) - 20, float(ey), "E",
                    color="#FF9040", fontsize=11, fontweight="bold",
                    ha="right")
        except Exception:
            pass

    # ── Achsen / Titel / Speichern ─────────────────────────────────────────
    ax.set_xlim(0, px_size)
    ax.set_ylim(0, px_size)
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for sp in ax.spines.values():
        sp.set_color(GRID_COL)

    bg_label = "DSS2 Red" if dss_loaded else "kein Hintergrund"
    ax.set_title(
        f"Finder Chart  ·  {target}  ·  {constellation}  ·  "
        f"{_ra_str(ra_c)}  {_dec_str(dec_c)}  ·  FOV {fov_deg:.0f}°  ·  {bg_label}",
        color=TEXT_COL, fontsize=11, fontweight="bold", pad=10,
    )

    pg(95, "Speichern …")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=SKY_BG)
    plt.close(fig)
    pg(100, "Finder Chart gespeichert.")
    return dss_loaded


def _ra_str(ra_deg: float) -> str:
    h = ra_deg / 15; hh = int(h); mm = int((h - hh) * 60); ss = ((h - hh) * 60 - mm) * 60
    return f"{hh:02d}h {mm:02d}m {ss:04.1f}s"


def _dec_str(dec_deg: float) -> str:
    s = "+" if dec_deg >= 0 else "-"
    d = abs(dec_deg)
    dg = int(d); dm = int((d - dg) * 60); ds = ((d - dg) * 60 - dm) * 60
    return f"{s}{dg:02d}° {dm:02d}′ {ds:04.1f}″"
