"""
AstroAnalyzer – XISF/FITS Reader
Liest XISF (PixInsight) und FITS (N.I.N.A. etc.) Dateien
"""

import struct, re, base64, warnings
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
from astropy.io import fits as astrofits
from astropy.wcs import WCS

warnings.filterwarnings("ignore")


# ─── XISF ─────────────────────────────────────────────────────────────────────

def _xisf_xml(path: str) -> tuple[str, int]:
    """Liest XISF-Header und gibt (XML-String, Header-Länge) zurück."""
    with open(path, "rb") as f:
        sig = f.read(8)
        if sig != b"XISF0100":
            raise ValueError(f"Kein gültiges XISF-Format: {sig}")
        hlen = struct.unpack("<I", f.read(4))[0]
        f.read(4)  # reserved
        xml = f.read(hlen).decode("utf-8", errors="replace")
    return xml, hlen


def _xisf_root(xml: str):
    return ET.fromstring(re.sub(r'xmlns="[^"]*"', "", xml, count=1))


def _prop(root, pid: str):
    for p in root.iter("Property"):
        if p.get("id") == pid:
            v = p.get("value")
            t = p.text.strip() if p.text else None
            return v if v is not None else t
    return None


def _fitsval(xml: str, key: str):
    m = re.search(r'FITSKeyword name="' + key + r'" value="([^"]*)"', xml)
    return m.group(1).strip().strip("'") if m else None


def _attachment_offset(xml: str, expected_bytes: int = 0) -> int:
    matches = re.findall(r'location="attachment:(\d+):(\d+)"', xml)
    if not matches:
        return 16 + 135000
    if expected_bytes > 0:
        for off, size in matches:
            if int(size) == expected_bytes:
                return int(off)
    return max(int(off) for off, size in matches)


def load_xisf(path: str) -> dict:
    """
    Lädt XISF-Datei vollständig.
    Rückgabe: dict mit img (float32 ndarray), meta (dict), wcs (WCS|None)
    """
    xml, hlen = _xisf_xml(path)
    root = _xisf_root(xml)

    # Geometrie & Format
    geo_m = re.search(r'geometry="(\d+):(\d+):(\d+)"', xml)
    if not geo_m:
        raise ValueError("XISF: Keine Bildgeometrie gefunden")
    W, H, C = int(geo_m.group(1)), int(geo_m.group(2)), int(geo_m.group(3))

    sf = re.search(r'sampleFormat="([^"]*)"', xml)
    sample_fmt = sf.group(1) if sf else "Float32"
    dtype = {"UInt16": "<u2", "UInt8": "u1", "Float32": "<f4", "Float64": "<f8"}.get(
        sample_fmt, "<f4"
    )
    bytes_per = {"<u2": 2, "u1": 1, "<f4": 4, "<f8": 8}.get(dtype, 4)

    expected = W * H * C * bytes_per
    off = _attachment_offset(xml, expected_bytes=expected)
    with open(path, "rb") as f:
        f.seek(off)
        buf = f.read(expected)

    raw = np.frombuffer(buf, dtype=dtype)

    if C == 1:
        img = raw.reshape(H, W).astype(np.float32)
    else:
        img = raw.reshape(C, H, W).astype(np.float32)

    # Normalisierung auf 0..1
    if dtype in ("<u2", "u1"):
        img /= 65535.0 if dtype == "<u2" else 255.0

    # Metadaten
    def fv(k):
        return _fitsval(xml, k)

    meta = {
        "INSTRUME":  fv("INSTRUME"),
        "TELESCOP":  fv("TELESCOP"),
        "FOCALLEN":  float(fv("FOCALLEN") or 0),
        "XPIXSZ":    float(fv("XPIXSZ") or 3.76),
        "GAIN":      int(float(fv("GAIN") or fv("EGAIN") or 0)),
        "OFFSET":    int(float(fv("OFFSET") or fv("PEDESTAL") or 0)),
        "CCD-TEMP":  float(fv("CCD-TEMP") or -10),
        "EXPTIME":   float(fv("EXPTIME") or fv("EXPOSURE") or 0),
        "FILTER":    fv("FILTER"),
        "OBJECT":    fv("OBJECT"),
        "DATE-OBS":  fv("DATE-OBS"),
        "IMAGETYP":  fv("IMAGETYP"),
        "NCOMBINE":  int(float(fv("NCOMBINE") or 1)),
        "AIRMASS":   float(fv("AIRMASS") or 0),
        "SITELAT":   float(fv("SITELAT") or fv("OBSGEO-B") or 0),
        "SITELONG":  float(fv("SITELONG") or fv("OBSGEO-L") or 0),
        "WIDTH":     W, "HEIGHT": H, "CHANNELS": C,
        "SAMPLE_FORMAT": sample_fmt,
        "source_file": str(Path(path).name),
    }

    if meta["GAIN"] == 0:
        gain_prop = _prop(root, "Instrument:Camera:Gain")
        if gain_prop:
            meta["GAIN"] = int(float(gain_prop))

    wcs = _xisf_wcs(root)
    return {"img": img, "meta": meta, "wcs": wcs, "xml": xml, "root": root}


def _xisf_wcs(root) -> WCS | None:
    """Dekodiert PCL:AstrometricSolution → astropy WCS."""
    def gtext(pid):
        for p in root.iter("Property"):
            if p.get("id") == pid and p.text:
                return p.text.strip()
        return None

    def d64(b64, n):
        raw = base64.b64decode(b64)
        return struct.unpack(f"<{n}d", raw[: 8 * n])

    try:
        ri  = d64(gtext("PCL:AstrometricSolution:ReferenceImageCoordinates"), 2)
        rc  = d64(gtext("PCL:AstrometricSolution:ReferenceCelestialCoordinates"), 2)
        ltm = d64(gtext("PCL:AstrometricSolution:LinearTransformationMatrix"), 4)
    except Exception:
        return None

    import math
    scale = math.hypot(ltm[0], ltm[2]) * 3600

    w = WCS(naxis=2)
    w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    w.wcs.crpix = [ri[0], ri[1]]
    w.wcs.crval = [rc[0], rc[1]]
    w.wcs.cd    = [[ltm[0], ltm[1]], [ltm[2], ltm[3]]]
    return w


# ─── FITS ──────────────────────────────────────────────────────────────────────

def load_fits(path: str) -> dict:
    """Lädt FITS-Datei (N.I.N.A., SharpCap, …)."""
    with astrofits.open(path) as hdul:
        hdr  = hdul[0].header
        data = hdul[0].data.astype(np.float32)

    # Normalisierung
    bzero  = float(hdr.get("BZERO",  0))
    bscale = float(hdr.get("BSCALE", 1))
    bitpix = int(hdr.get("BITPIX", 16))
    maxval = 2 ** abs(bitpix) - 1 if bitpix > 0 else 1.0

    if bitpix > 0:
        data = (data * bscale + bzero) / 65535.0
    data = np.clip(data, 0, 1)

    if data.ndim == 3:
        if data.shape[0] in (1, 3):
            img = data
        else:
            img = data[np.newaxis]
    else:
        img = data

    def hv(k, default=None):
        v = hdr.get(k, default)
        return str(v).strip().strip("'") if v is not None else default

    H, W = (img.shape[-2], img.shape[-1])
    meta = {
        "INSTRUME":  hv("INSTRUME"),
        "TELESCOP":  hv("TELESCOP"),
        "FOCALLEN":  float(hv("FOCALLEN", 0)),
        "XPIXSZ":    float(hv("XPIXSZ", 3.76)),
        "GAIN":      int(float(hv("GAIN") or hv("EGAIN") or 0)),
        "OFFSET":    int(float(hv("OFFSET") or hv("PEDESTAL") or 0)),
        "CCD-TEMP":  float(hv("CCD-TEMP", -10)),
        "EXPTIME":   float(hv("EXPTIME", hv("EXPOSURE", 0))),
        "FILTER":    hv("FILTER"),
        "OBJECT":    hv("OBJECT"),
        "DATE-OBS":  hv("DATE-OBS"),
        "IMAGETYP":  hv("IMAGETYP"),
        "NCOMBINE":  int(float(hv("NCOMBINE", 1))),
        "AIRMASS":   float(hv("AIRMASS", 0)),
        "SITELAT":   float(hv("SITELAT", 0)),
        "SITELONG":  float(hv("SITELONG", 0)),
        "WIDTH": W, "HEIGHT": H, "CHANNELS": img.shape[0] if img.ndim == 3 else 1,
        "SAMPLE_FORMAT": f"Int{abs(bitpix)}",
        "source_file": str(Path(path).name),
    }

    # WCS aus Standard-FITS-Keywords
    try:
        wcs = WCS(hdr, naxis=2)
        if not wcs.has_celestial:
            wcs = None
    except Exception:
        wcs = None

    return {"img": img, "meta": meta, "wcs": wcs}


def load_master_header(path: str) -> dict:
    """Reads only FITS keywords from XISF/FITS — no pixel data loaded."""
    p = Path(path)
    if p.suffix.lower() == ".xisf":
        xml, _ = _xisf_xml(path)
        root = _xisf_root(xml)
        ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
        def fv(k):
            for kw in root.iter("FITSKeyword"):
                if kw.get("name","").upper() == k.upper():
                    return kw.get("value","").strip().strip("'") or None
            return None
        return {k: fv(k) for k in ("IMAGETYP","EXPTIME","FILTER","OBJECT","NCOMBINE","GAIN")}
    else:
        from astropy.io import fits as astrofits
        with astrofits.open(path, memmap=True) as hdul:
            hdr = hdul[0].header
        def hv(k):
            v = hdr.get(k)
            return str(v).strip().strip("'") if v is not None else None
        return {k: hv(k) for k in ("IMAGETYP","EXPTIME","FILTER","OBJECT","NCOMBINE","GAIN")}


def load_image(path: str) -> dict:
    """Automatische Format-Erkennung."""
    p = Path(path)
    if p.suffix.lower() == ".xisf":
        return load_xisf(path)
    elif p.suffix.lower() in (".fits", ".fit", ".fts"):
        return load_fits(path)
    else:
        raise ValueError(f"Unbekanntes Format: {p.suffix}")


def pixel_scale(meta: dict, wcs: WCS | None) -> float:
    """Gibt Bogensekunden/Pixel zurück."""
    if wcs is not None:
        try:
            import math
            cd = wcs.wcs.cd
            return math.hypot(cd[0][0], cd[1][0]) * 3600
        except Exception:
            pass
    fl  = meta.get("FOCALLEN", 0)
    px  = meta.get("XPIXSZ",   3.76)
    if fl > 0:
        return 206265 * px / 1000 / fl
    return 0.698  # Fallback AP155+QHY600
