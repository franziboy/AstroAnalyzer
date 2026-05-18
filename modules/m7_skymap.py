"""
AstroAnalyzer – Modul 7: Himmelskarte und Orientierung
Drei Ausgaben als ein kombiniertes PNG:
  1. Vollhimmel-Übersicht (Mollweide) — wo liegt das Objekt?
  2. FOV-Orientierung — N/E-Pfeile, Feldrotation, Bildskala
  3. Sichtbarkeits-Chart — Altitude über die Beobachtungsnacht
"""

import numpy as np
import warnings
warnings.filterwarnings("ignore")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from matplotlib.gridspec import GridSpec

from astropy.coordinates import SkyCoord, get_constellation, AltAz, EarthLocation
from astropy.time import Time
import astropy.units as u


# ── Farben ─────────────────────────────────────────────────────────────────
SKY_BG    = "#08080f"
GRID_COL  = "#1a1a3a"
STAR_COL  = "#c8d8ff"
OBJ_COL   = "#FFD700"
FOV_COL   = "#FF6060"
TEXT_COL  = "#e0e8ff"
ACCENT    = "#7c9ad6"
ALT_COL   = "#6bcb6b"


def run(meta: dict, wcs, img_shape: tuple,
        output_path: str, progress_cb=None) -> bool:
    """
    meta       : Header-Dict aus xisf_reader
    wcs        : astropy.wcs.WCS (kann None sein)
    img_shape  : (H, W) des Bildes
    output_path: Ziel-PNG
    Rückgabe   : True wenn erfolgreich
    """
    def pg(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    # ── Koordinaten aus WCS oder Header ────────────────────────────────────
    ra_deg  = None
    dec_deg = None

    if wcs is not None:
        try:
            H, W = img_shape
            sk = wcs.pixel_to_world(W / 2, H / 2)
            ra_deg  = float(sk.ra.deg)
            dec_deg = float(sk.dec.deg)
        except Exception:
            pass

    if ra_deg is None:
        try:
            from astropy.coordinates import SkyCoord
            ra_deg  = float(meta.get("RA")  or meta.get("OBJCTRA")  or 0)
            dec_deg = float(meta.get("DEC") or meta.get("OBJCTDEC") or 0)
        except Exception:
            pass

    if not ra_deg and not dec_deg:
        pg(100, "Keine Koordinaten — Himmelskarte übersprungen.")
        return False

    # ── Metadaten ──────────────────────────────────────────────────────────
    target   = meta.get("OBJECT")  or "Unbekannt"
    filt     = meta.get("FILTER")  or "?"
    date_obs = meta.get("DATE-OBS") or ""
    site_lat = float(meta.get("SITELAT")  or 52.24)
    site_lon = float(meta.get("SITELONG") or 8.81)

    # Sternbild
    try:
        sk_obj = SkyCoord(ra_deg * u.deg, dec_deg * u.deg)
        constellation = get_constellation(sk_obj)
    except Exception:
        constellation = ""

    # FOV aus WCS
    fov_w_deg = fov_h_deg = rot_deg = None
    if wcs is not None:
        try:
            H, W = img_shape
            import math
            cd = wcs.wcs.cd
            fov_w_deg = abs(cd[0][0]) * W
            fov_h_deg = abs(cd[1][1]) * H
            rot_deg   = math.degrees(math.atan2(cd[0][1], cd[0][0]))
        except Exception:
            pass

    # ── Figure aufbauen ────────────────────────────────────────────────────
    pg(10, "Himmelskarte aufbauen …")
    fig = plt.figure(figsize=(18, 7), facecolor=SKY_BG)
    fig.patch.set_facecolor(SKY_BG)

    gs = GridSpec(1, 3, figure=fig, width_ratios=[2.2, 1.0, 1.8],
                  wspace=0.08, left=0.04, right=0.97,
                  top=0.88, bottom=0.08)

    # ── Panel 1: Vollhimmel-Übersicht ─────────────────────────────────────
    pg(20, "Vollhimmel-Projektion …")
    ax1 = fig.add_subplot(gs[0], projection="mollweide")
    ax1.set_facecolor(SKY_BG)
    ax1.tick_params(colors=TEXT_COL, labelsize=7)
    ax1.grid(True, color=GRID_COL, alpha=0.8, linewidth=0.5)

    # Galaktische Ebene
    l_gal = np.linspace(0, 360, 360)
    b_gal = np.zeros(360)
    import astropy.coordinates as _ac
    gal_sc = _ac.SkyCoord(l=l_gal * u.deg, b=b_gal * u.deg, frame="galactic")
    eq  = gal_sc.icrs
    ra_gal  = eq.ra.deg
    dec_gal = eq.dec.deg
    # Sortieren für saubere Linie
    sort_idx = np.argsort(ra_gal)
    ra_s  = ra_gal[sort_idx]
    dec_s = dec_gal[sort_idx]
    # Umwandlung für Mollweide (RA: 0..360 → -π..π, mit Zentrierung)
    ra_mol  = np.radians(-(ra_s - 180))
    dec_mol = np.radians(dec_s)
    # Sprünge vermeiden
    gaps = np.where(np.abs(np.diff(ra_mol)) > np.pi / 2)[0]
    prev = 0
    for g in gaps:
        ax1.plot(ra_mol[prev:g+1], dec_mol[prev:g+1],
                 color="#886644", alpha=0.4, linewidth=1.0)
        prev = g + 1
    ax1.plot(ra_mol[prev:], dec_mol[prev:],
             color="#886644", alpha=0.4, linewidth=1.0,
             label="Galaktische Ebene")

    # Ekliptik
    try:
        from astropy.coordinates import GeocentricMeanEcliptic
        lam_ecl = np.linspace(0, 360, 360)
        ecl = GeocentricMeanEcliptic(lon=lam_ecl * u.deg,
                                      lat=np.zeros(360) * u.deg,
                                      equinox="J2000")
        eq_ecl = ecl.icrs
        ra_e  = np.radians(-(eq_ecl.ra.deg - 180))
        dec_e = np.radians(eq_ecl.dec.deg)
        sort_e = np.argsort(ra_e)
        ax1.plot(ra_e[sort_e], dec_e[sort_e],
                 color="#446688", alpha=0.4, linewidth=1.0,
                 label="Ekliptik")
    except Exception:
        pass

    # Objekt-Position
    obj_ra_mol  = np.radians(-(ra_deg - 180))
    obj_dec_mol = np.radians(dec_deg)
    ax1.plot(obj_ra_mol, obj_dec_mol, "o",
             color=OBJ_COL, ms=14, zorder=10,
             markeredgecolor="white", markeredgewidth=1.5)

    # FOV-Rechteck (vereinfacht als Ellipse auf Mollweide)
    if fov_w_deg and fov_h_deg:
        ell = mpatches.Ellipse(
            (obj_ra_mol, obj_dec_mol),
            width=np.radians(fov_w_deg) * 1.5,
            height=np.radians(fov_h_deg) * 1.5,
            angle=rot_deg or 0,
            fill=False, edgecolor=FOV_COL,
            linewidth=1.5, zorder=9)
        ax1.add_patch(ell)

    # Beschriftung
    ax1.annotate(
        f"{target}\n{constellation}",
        (obj_ra_mol, obj_dec_mol),
        color=OBJ_COL, fontsize=9, fontweight="bold",
        xytext=(18, 18), textcoords="offset points",
        arrowprops=dict(arrowstyle="-", color=OBJ_COL, lw=0.8)
    )

    ax1.set_title("Himmelsposition", color=TEXT_COL,
                  fontsize=11, fontweight="bold", pad=8)

    # RA-Achsenbeschriftung anpassen
    xticks = ax1.get_xticks()
    ax1.set_xticklabels(
        [f"{int((180 - np.degrees(t)) % 360)}°" for t in xticks],
        color=TEXT_COL, fontsize=7)
    ax1.set_yticklabels(
        [f"{int(np.degrees(t))}°" for t in ax1.get_yticks()],
        color=TEXT_COL, fontsize=7)

    # ── Panel 2: FOV-Orientierung ─────────────────────────────────────────
    pg(50, "FOV-Orientierung …")
    ax2 = fig.add_subplot(gs[1])
    ax2.set_facecolor(SKY_BG)
    ax2.set_xlim(-1.3, 1.3); ax2.set_ylim(-1.3, 1.3)
    ax2.set_aspect("equal")
    ax2.axis("off")
    ax2.set_title("Orientierung", color=TEXT_COL,
                  fontsize=11, fontweight="bold", pad=8)

    import math

    # FOV-Rechteck zentriert
    if fov_w_deg and fov_h_deg:
        ratio = fov_h_deg / fov_w_deg if fov_w_deg > 0 else 1
        bw = 0.80
        bh = min(0.80, bw * ratio)
        if bh > 0.80:
            bh = 0.80; bw = bh / ratio
        rot_rad = math.radians(rot_deg or 0)
        corners_local = np.array([
            [-bw/2, -bh/2], [bw/2, -bh/2],
            [bw/2, bh/2], [-bw/2, bh/2], [-bw/2, -bh/2]
        ])
        R = np.array([[math.cos(rot_rad), -math.sin(rot_rad)],
                      [math.sin(rot_rad),  math.cos(rot_rad)]])
        corners_rot = corners_local @ R.T
        ax2.plot(corners_rot[:, 0], corners_rot[:, 1],
                 color=FOV_COL, linewidth=2)
        ax2.fill(corners_rot[:, 0], corners_rot[:, 1],
                 color=FOV_COL, alpha=0.06)
        ax2.plot(0, 0, "+", color=OBJ_COL, ms=12, mew=2)

    # N/E-Pfeile aus WCS-Rotation
    if rot_deg is not None:
        r = math.radians(rot_deg)
        # Nord
        n_dx = -math.sin(r) * 0.55
        n_dy =  math.cos(r) * 0.55
        ax2.annotate("", xy=(n_dx, n_dy), xytext=(0, 0),
                     arrowprops=dict(arrowstyle="->", color="#80FF80",
                                     lw=2.0, mutation_scale=16))
        ax2.text(n_dx * 1.25, n_dy * 1.25, "N",
                 color="#80FF80", fontsize=12, fontweight="bold",
                 ha="center", va="center")
        # Ost (90° gegen Uhrzeigersinn von N)
        e_dx = -math.cos(r) * 0.45
        e_dy = -math.sin(r) * 0.45
        ax2.annotate("", xy=(e_dx, e_dy), xytext=(0, 0),
                     arrowprops=dict(arrowstyle="->", color="#FF9040",
                                     lw=2.0, mutation_scale=14))
        ax2.text(e_dx * 1.3, e_dy * 1.3, "E",
                 color="#FF9040", fontsize=11, fontweight="bold",
                 ha="center", va="center")

    # Info-Text
    info_lines = [
        f"RA  {_ra_str(ra_deg)}",
        f"Dec {_dec_str(dec_deg)}",
        f"Sternbild: {constellation}",
    ]
    if fov_w_deg and fov_h_deg:
        info_lines += [
            f"FOV  {fov_w_deg:.2f}° × {fov_h_deg:.2f}°",
            f"Rotation {rot_deg:.1f}°" if rot_deg else "",
        ]
    ax2.text(0, -1.15, "\n".join(l for l in info_lines if l),
             color=TEXT_COL, fontsize=8,
             ha="center", va="bottom", linespacing=1.6,
             fontfamily="monospace")

    # ── Panel 3: Sichtbarkeits-Chart ──────────────────────────────────────
    pg(70, "Sichtbarkeits-Chart …")
    ax3 = fig.add_subplot(gs[2])
    ax3.set_facecolor(SKY_BG)
    ax3.tick_params(colors=TEXT_COL, labelsize=8)
    for spine in ax3.spines.values():
        spine.set_color(GRID_COL)
    ax3.set_title("Sichtbarkeit", color=TEXT_COL,
                  fontsize=11, fontweight="bold", pad=8)

    try:
        from astroplan import Observer, FixedTarget
        from astropy.coordinates import EarthLocation
        import astropy.coordinates as _ac2

        location = EarthLocation(lat=site_lat * u.deg,
                                  lon=site_lon * u.deg,
                                  height=60 * u.m)
        observer = Observer(location=location, name="Standort")
        target_coord = _ac2.SkyCoord(ra_deg * u.deg, dec_deg * u.deg)
        target_ap = FixedTarget(target_coord, name=target)

        # Beobachtungsdatum aus Header oder heute
        if date_obs:
            t0 = Time(date_obs[:10] + "T12:00:00", format="isot", scale="utc")
        else:
            t0 = Time.now()

        times = t0 + np.linspace(0, 24, 289) * u.hour
        altaz_frame = AltAz(obstime=times, location=location)
        altaz = target_coord.transform_to(altaz_frame)
        alt = altaz.alt.deg

        hours = np.linspace(0, 24, 289)
        local_hours = (hours + site_lon / 15) % 24

        # Nacht-Shading (grob: 20–4 Uhr Lokalzeit)
        night_mask = (local_hours >= 20) | (local_hours <= 5)
        ax3.fill_between(local_hours, 0, 90,
                         where=night_mask, color="#0a0a20", alpha=0.7)

        # Altitude-Kurve
        ax3.plot(local_hours, np.clip(alt, 0, 90),
                 color=ALT_COL, linewidth=2.0, label=target)
        ax3.fill_between(local_hours, 0, np.clip(alt, 0, 90),
                         color=ALT_COL, alpha=0.15)

        # Horizont + 30°-Linie
        ax3.axhline(0, color=GRID_COL, linewidth=1.0)
        ax3.axhline(30, color="#443344", linewidth=0.8, linestyle="--",
                    label="30° (empfohlen)")

        # Aufnahmezeitpunkt markieren
        if date_obs:
            try:
                t_obs = Time(date_obs, format="isot", scale="utc")
                from datetime import timezone
                dt_utc = t_obs.to_datetime(timezone=timezone.utc)
                h_obs = (dt_utc.hour + dt_utc.minute / 60 + site_lon / 15) % 24
                idx = int(h_obs / 24 * 288)
                alt_obs = float(np.clip(alt[idx], 0, 90))
                ax3.axvline(h_obs, color=OBJ_COL, linewidth=1.5,
                             linestyle="--", alpha=0.8)
                ax3.plot(h_obs, alt_obs, "o",
                         color=OBJ_COL, ms=9, zorder=10)
                ax3.text(h_obs + 0.3, alt_obs + 2,
                         f"Aufnahme\n{alt_obs:.0f}°",
                         color=OBJ_COL, fontsize=8)
            except Exception:
                pass

        ax3.set_xlim(0, 24)
        ax3.set_ylim(0, 92)
        ax3.set_xlabel("Lokalzeit (h)", color=TEXT_COL, fontsize=9)
        ax3.set_ylabel("Altitude (°)", color=TEXT_COL, fontsize=9)
        ax3.set_xticks(range(0, 25, 3))
        ax3.set_yticks(range(0, 91, 15))
        ax3.grid(True, color=GRID_COL, alpha=0.5, linewidth=0.5)
        ax3.legend(fontsize=8, facecolor="#111122",
                   labelcolor=TEXT_COL, edgecolor=GRID_COL)

        # Max-Altitude annotieren
        max_alt = float(np.max(alt))
        max_h   = float(local_hours[np.argmax(alt)])
        ax3.text(0.98, 0.95, f"Max {max_alt:.0f}° @ {max_h:.1f}h",
                 transform=ax3.transAxes, color=ALT_COL,
                 fontsize=8, ha="right", va="top")

    except ImportError:
        ax3.text(0.5, 0.5, "astroplan nicht installiert\npip install astroplan",
                 transform=ax3.transAxes, color=TEXT_COL,
                 ha="center", va="center", fontsize=10)
    except Exception as e:
        ax3.text(0.5, 0.5, f"Fehler:\n{e}",
                 transform=ax3.transAxes, color="#FF6060",
                 ha="center", va="center", fontsize=9)

    # ── Gesamt-Titel ──────────────────────────────────────────────────────
    pg(90, "Speichern …")
    title = (f"{target}  ·  {_ra_str(ra_deg)}  {_dec_str(dec_deg)}"
             f"  ·  Filter {filt}")
    if date_obs:
        title += f"  ·  {date_obs[:10]}"
    fig.suptitle(title, color=TEXT_COL, fontsize=12,
                 fontweight="bold", y=0.97)

    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=SKY_BG)
    plt.close(fig)
    pg(100, f"Himmelskarte gespeichert: {output_path}")
    return True


# ── Hilfsfunktionen ────────────────────────────────────────────────────────

def _ra_str(ra_deg: float) -> str:
    h = ra_deg / 15
    hh = int(h); mm = int((h - hh) * 60); ss = ((h - hh) * 60 - mm) * 60
    return f"{hh:02d}h {mm:02d}m {ss:04.1f}s"


def _dec_str(dec_deg: float) -> str:
    sign = "+" if dec_deg >= 0 else "-"
    d = abs(dec_deg)
    dg = int(d); dm = int((d - dg) * 60); ds = ((d - dg) * 60 - dm) * 60
    return f"{sign}{dg:02d}° {dm:02d}′ {ds:04.1f}″"
