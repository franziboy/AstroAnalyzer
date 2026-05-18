"""
AstroAnalyzer – Modul 3: PixInsight-Optimierungsvorschläge
Regelbasiertes System: Bedingung → Werkzeug + Einstellung + Begründung
"""


REGELN = [
    {
        "id": "R00", "phase": "linear", "prio": 0,
        "bedingung": lambda r: True,
        "werkzeug":  "DynamicCrop",
        "einstellung": "Stack-Ränder (Dither-Versatz) eng abschneiden",
        "begruendung": (
            "Die durch den Dither-Versatz ausgefransten Ränder enthalten weniger "
            "beitragende Frames und damit höheres Rauschen sowie partielle Treppenkanten. "
            "Alle nachfolgenden Werkzeuge (Hintergrundmodell, Rauschschätzung, STF) "
            "würden durch diese Randpixel verzerrt. DynamicCrop muss daher als "
            "absolut erster Schritt stehen."
        ),
    },
    {
        "id": "R01", "phase": "linear", "prio": 1,
        "bedingung": lambda r: r.get("banding_amp", 0) > 0.3 * r.get("noise_mad", 1),
        "werkzeug":  "LinearPatternSubtraction (Skript)",
        "einstellung": (
            "Achse=vertikal, an galaxie-/sternfreier Hintergrundregion kalibrieren. "
            "Stärke moderat beginnen. VOR Hintergrundkorrektur ausführen."
        ),
        "begruendung": (
            "Banding ist ein zeilen-/spaltenkohärentes Ausleseartefakt des Sensors — "
            "kein zufälliges Rauschen, sondern ein gerichtetes Muster. "
            "NoiseXTerminator entfernt es NICHT; er verschmiert es nur. "
            "Die Subtraktion MUSS vor der Hintergrundmodellierung erfolgen, "
            "weil DBE/GraXpert das Streifenmuster sonst teilweise als Himmelshintergrund "
            "interpretiert und dauerhaft einmodelliert."
        ),
    },
    {
        "id": "R02", "phase": "linear", "prio": 2,
        "bedingung": lambda r: abs(r.get("flat_corr", 0)) > 0.5,
        "werkzeug":  "Flat-Technik verbessern (außerhalb PixInsight)",
        "einstellung": (
            "Homogen diffuse Lichtquelle (Elektrolumineszenz-Panel mit Diffusor), "
            "Fokuslage und Filterrad-Position zwischen Flat und Light konstant halten. "
            "In PixInsight: DBE/GraXpert nur als Notlösung."
        ),
        "begruendung": (
            f"Korrelation(Resthintergrund, 1/Flat) > 0,5: Der Restgradient folgt der "
            "Flat-Struktur — das ist primär ein Flat-Beleuchtungsfehler, keine "
            "Lichtverschmutzung. DBE behandelt nur das Symptom. Die Ursache ist eine "
            "asymmetrische Flat-Lichtquelle (heller Schwerpunkt nicht im Sensorzentrum). "
            "Subtraktiv statt dividierend korrigieren, da es ein additiver Lichtoffset ist."
        ),
    },
    {
        "id": "R03", "phase": "linear", "prio": 3,
        "bedingung": lambda r: r.get("gradient_pct", 0) > 2.0,
        "werkzeug":  "GradientCorrection / DBE / GraXpert",
        "einstellung": (
            "Subtraktiv (NICHT dividierend). DBE: wenige manuelle Samples (10–20) "
            "ausschließlich in quellen- und halofreien Hintergrundbereichen, Grad 1 oder 2. "
            "GraXpert: AI-Modus, subtraktive Korrektur übernehmen."
        ),
        "begruendung": (
            "Gradient > 2%: Sichtbar, aber noch schwach. Ein niedriggradiges Modell genügt. "
            "Aggressives DBE (viele Samples, hoher Grad) würde in galaxienreichen Feldern "
            "ausgedehnte Halos und schwache LSB-Strukturen als 'Hintergrund' abtragen. "
            "Subtraktiv, weil ein additiver Lichtoffset (kein multiplikativer "
            "Empfindlichkeitsfehler — das wäre Flatfield-Sache)."
        ),
    },
    {
        "id": "R04", "phase": "linear", "prio": 4,
        "bedingung": lambda r: r.get("fwhm_arcsec", 0) > 2.0,
        "werkzeug":  "BlurXTerminator",
        "einstellung": (
            "Modus 'Correct Only' zuerst zur PSF-Korrektur. "
            "Sharpen Stars niedrig (0.1–0.2), Sharpen Nonstellar moderat (0.3–0.5). "
            "Ausschließlich auf lineares Bild anwenden."
        ),
        "begruendung": (
            "Seeing-limitiertes Bild (FWHM > 2\"): Die Optik liefert mehr Auflösung als "
            "das Seeing durchließ — hier liegt das größte ungenutzte Detailpotenzial. "
            "Staubband und Spiralstruktur profitieren besonders. "
            "Dekonvolution MUSS linear und vor jeder Rauschreduktion erfolgen: "
            "Sie invertiert ein lineares Vorwärtsmodell der Bildentstehung. "
            "Nach einem nichtlinearen Stretch oder Denoising ist dieses Modell "
            "ungültig und erzeugt Ringstrukturen (Ringing-Artefakte)."
        ),
    },
    {
        "id": "R05", "phase": "linear", "prio": 5,
        "bedingung": lambda r: True,
        "werkzeug":  "NoiseXTerminator",
        "einstellung": (
            "Denoise 0.6–0.8, Detail leicht anheben. "
            "Nach BlurXTerminator, noch im linearen Zustand."
        ),
        "begruendung": (
            "Reihenfolge ist entscheidend: Dekonvolution (BlurXTerminator) hebt "
            "zwangsläufig das Rauschen an — Denoising folgt danach, nicht davor. "
            "Würde Denoising vor der Dekonvolution stehen, entfernt es genau das "
            "Signal, das die Dekonvolution zur Invertierung des Unschärfemodells braucht. "
            "Bei tiefer Integration (> 5h) nur moderat dosieren: zu starkes Denoising "
            "kostet schwache Hintergrundgalaxien mehr als es dem Gesamtbild bringt."
        ),
    },
    {
        "id": "R06", "phase": "nichtlinear", "prio": 6,
        "bedingung": lambda r: True,
        "werkzeug":  "StarXTerminator",
        "einstellung": (
            "Sterne vollständig abtrennen. "
            "Galaxienebene und Sternebene separat speichern und weiterverarbeiten."
        ),
        "begruendung": (
            "In dichten Feldern mit vielen hellen Sternen dominieren die Sternhüllen "
            "den Stretch und drücken schwache ausgedehnte Galaxien optisch weg. "
            "Getrennte Ebenen erlauben einen aggressiveren, galaxienoptimierten Stretch "
            "auf der Galaxienebene (für PGC-Objekte und Halos), ohne dabei "
            "Sternkerne aufzublähen oder Sternhaloartefakte zu erzeugen."
        ),
    },
    {
        "id": "R07", "phase": "nichtlinear", "prio": 7,
        "bedingung": lambda r: True,
        "werkzeug":  "GeneralizedHyperbolicStretch (GHS)",
        "einstellung": (
            "Sternlose Galaxienebene strecken. "
            "Hintergrund knapp über dem Schwarzpunkt halten. "
            "Sternebene separat und dezent strecken."
        ),
        "begruendung": (
            "GHS bietet feinere Kontrolle über den Hintergrund→Mittelton-Übergang "
            "als ein klassischer STF-basierter AutoStretch. "
            "Wichtig, um flächige, schwache PGC-Galaxien sichtbar zu machen, "
            "ohne den Himmelshintergrund abzusaufen oder grau zu heben. "
            "Erst hier verlässt das Bild den linearen Zustand — "
            "alle vorherigen Schritte (R00–R05) erfordern zwingend lineare Eingangsdaten."
        ),
    },
    {
        "id": "R08", "phase": "nichtlinear", "prio": 8,
        "bedingung": lambda r: True,
        "werkzeug":  "PixelMath (Screen-Kombination)",
        "einstellung": "screen(galaxienebene, sternebene) — beide gestreckt.",
        "begruendung": (
            "Screen-Modus statt additiver Überlagerung: verhindert, dass helle Sternkerne "
            "die Galaxienebene überstrahlen und dort Halos oder Sättigungs-Artefakte erzeugen. "
            "Die Galaxienebene bleibt in ihrer Dynamik vollständig erhalten."
        ),
    },
    {
        "id": "R09", "phase": "annotation", "prio": 9,
        "bedingung": lambda r: r.get("wcs_available", False),
        "werkzeug":  "Script › Render › AnnotateImage",
        "einstellung": (
            "Kataloge aktivieren: NGC/IC, PGC (HyperLEDA), optional Gaia DR3. "
            "Auf gelöstes (lineares oder bereits gestrecktes) Bild anwenden."
        ),
        "begruendung": (
            "Die vorhandene WCS-Lösung (PCL:AstrometricSolution) wird von PixInsight "
            "direkt genutzt. Der PGC/HyperLEDA-Katalog benennt alle Hintergrundgalaxien, "
            "die über den lokalen NGC/IC-Katalog hinausgehen. "
            "Gegenprobe mit nova.astrometry.net empfohlen."
        ),
    },
    {
        "id": "R10", "phase": "aufnahme", "prio": 10,
        "bedingung": lambda r: r.get("dithering_ratio", 0) > 0.5,
        "werkzeug":  "N.I.N.A. Dithering-Einstellung",
        "einstellung": "Pseudo-random, Amplitude ≥ 15–30 px, nach jedem Sub.",
        "begruendung": (
            "Dies ist der größte Qualitätshebel für die nächste Session. "
            "Banding und Walking Noise dekorrelieren nur dann im Stack, wenn der "
            "Dither-Versatz größer als die Banding-Periode ist und pseudo-random verteilt. "
            "Kein nachträgliches PixInsight-Skript kann das so sauber lösen wie "
            "korrektes Dithering an der Quelle — ohne Signalverlust."
        ),
    },
]


def run(img_stats: dict, acq_results: dict, calib_results: dict,
        wcs_available: bool, progress_cb=None) -> list[dict]:
    """
    Kombiniert Ergebnisse aller Module → geordnete Empfehlungsliste.

    Rückgabe: Liste von Dicts mit id, phase, werkzeug, einstellung, begruendung
    """
    def pg(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    pg(10, "Regeln auswerten …")

    # Kontext für Bedingungen zusammenstellen
    dith = acq_results.get("dithering", {})
    ctx = {
        **img_stats,
        "flat_corr":        calib_results.get("flat_mismatch", {}).get("korrelation", 0),
        "wcs_available":    wcs_available,
        "dithering_ratio":  dith.get("ratio", 0),
    }

    pg(60, "Aktive Regeln filtern …")
    aktiv = [r for r in REGELN if r["bedingung"](ctx)]
    aktiv.sort(key=lambda r: r["prio"])

    pg(100, "PixInsight-Empfehlungen generiert.")
    return [
        {
            "nr":           i + 1,
            "id":           r["id"],
            "phase":        r["phase"],
            "werkzeug":     r["werkzeug"],
            "einstellung":  r["einstellung"],
            "begruendung":  r["begruendung"],
        }
        for i, r in enumerate(aktiv)
    ]
