"""
AstroAnalyzer – Modul 3: PixInsight-Optimierungsvorschläge (intensiv)
Regelbasiertes System: Bedingung → Werkzeug + konkrete Einstellung + ausführliche Begründung
Parameter werden direkt aus den Messwerten der Module 1, 2 und 4 abgeleitet.
"""


REGELN = [

    # ════════════════════════════════════════════════════
    # LINEARE PHASE — Reihenfolge ist zwingend
    # ════════════════════════════════════════════════════

    {
        "id": "R00", "phase": "linear", "prio": 0,
        "bedingung": lambda r: True,
        "werkzeug": "DynamicCrop",
        "einstellung": (
            "Alle vier Seiten um Dither-Versatz + ~20 px Puffer kürzen. "
            "Keine Rotation sofern nicht nötig."
        ),
        "begruendung": (
            "Die ausgefransten Stack-Ränder entstehen durch den Dither-Versatz — "
            "dort tragen nicht alle Frames bei, das Rauschen ist lokal höher "
            "und die Kanten verlaufen treppenartig. "
            "Wird nicht gecroppt, verzerren diese Bereiche alle nachfolgenden "
            "Hintergrundmodelle (DBE, GraXpert), weil sie lokale Helligkeitssprünge "
            "erzeugen die das Modell auf die gesamte Bildfläche extrapoliert. "
            "Auch sigma-clipping-basierte Statistiken (STF, Rauschschätzung) "
            "werden durch die Randpixel verfälscht. "
            "DynamicCrop steht deshalb absolut als erstes."
        ),
    },

    {
        "id": "R01", "phase": "linear", "prio": 1,
        "bedingung": lambda r: r.get("banding_amp", 0) > 0.3 * r.get("noise_mad", 1),
        "werkzeug": "LinearPatternSubtraction (Skript)",
        "einstellung": (
            "Achse = vertikal (QHY600M-Spaltenrauschen). "
            "Kalibrierungsregion: galaxie- und sternfreier Hintergrundbereich, "
            "mindestens 500 × 500 px, möglichst weit vom Bildzentrum. "
            "LayersToRemove = 6. RejectionLimit = 3.0 σ. "
            "Ausführen VOR jeder Hintergrundkorrektur."
        ),
        "begruendung": (
            "Gemessene Banding-Amplitude: {banding_ratio:.1f}× Hintergrundrauschen. "
            "Ab 0.3× ist das Muster im Stack sichtbar und bleibt beim weiteren Stacking "
            "erhalten, weil es eine spaltenkorrelierte Struktur ist — kein zufälliges Rauschen. "
            "NoiseXTerminator, MLT und EZ-Denoise entfernen es NICHT — "
            "sie behandeln unkorrelierten Pixelrausch und verschmieren "
            "das kohärente Spaltenrauschen nur in benachbarte Pixel. "
            "Kritisch: dieser Schritt MUSS vor DBE/GraXpert stehen. "
            "Hintergrundmodelle mitteln über Zeilen und Spalten — "
            "ein verbleibendes Streifenmuster wird in das Hintergrundmodell "
            "einbezogen und danach dauerhaft als 'Himmel' behandelt."
        ),
    },

    {
        "id": "R02", "phase": "linear", "prio": 2,
        "bedingung": lambda r: abs(r.get("flat_corr", 0)) > 0.5,
        "werkzeug": "Flat-Technik verbessern (außerhalb PixInsight)",
        "einstellung": (
            "Primär: Flat-Lichtquelle homogenisieren — Elektrolumineszenz-Panel "
            "mit Milchglas-Diffusor, Panel exakt senkrecht und zentriert vor der Öffnung. "
            "Fokuslage, Filterrad-Position und Backfokus zwischen Flat und Light identisch. "
            "Flats zeitnah zur Lichtsession aufnehmen. "
            "DBE/GraXpert in PixInsight danach nur noch als Feinkorrektur."
        ),
        "begruendung": (
            "Korrelation(Master-Hintergrund, 1/Flat) = {flat_corr:.3f}: "
            "Der Restgradient im Stack folgt der Flat-Form — "
            "das ist ein Flat-Beleuchtungsfehler, keine Lichtverschmutzung. "
            "Der Unterschied ist entscheidend: Lichtverschmutzung erzeugt einen glatten "
            "richtungsgebundenen Gradienten; ein Flat-Fehler erzeugt die exakte "
            "Invers-Struktur des Flats im kalibrierten Bild. "
            "DBE kann die Symptome dämpfen, aber jedes Sample das DBE auf dem "
            "fehlerhaften Hintergrund setzt, trägt den Flat-Fehler in das "
            "Korrekturmodell ein — das Modell wird kontaminiert. "
            "Die einzige vollständige Lösung ist eine homogene Flat-Quelle."
        ),
    },

    {
        "id": "R03", "phase": "linear", "prio": 3,
        "bedingung": lambda r: r.get("gradient_pct", 0) > 1.5,
        "werkzeug": "GradientCorrection / DBE / GraXpert",
        "einstellung": (
            "Methode: subtraktiv (NIEMALS dividierend — Division ist für Flatfield-Fehler, "
            "nicht für additiven Lichthintergrund). "
            "DBE: Grad 1 bei Gradient < 4%, Grad 2 bei > 4%. "
            "Samples ausschließlich in quell- und halofreien Zonen — "
            "bei galaxienreichen Feldern lieber 10 gute als 30 schlechte Samples. "
            "Kein Sample näher als 200 px an Galaxien oder ausgedehnte Sterne. "
            "GraXpert: AI-Modus, Correction = Subtraction, Smoothing 0.2–0.4 (konservativ). "
            "Ergebnis mit STF prüfen: kein Halo um helle Galaxien."
        ),
        "begruendung": (
            "Gemessener Gradient: {gradient_pct:.1f}%, {gradient_sigma:.1f} σ über Rauschen. "
            "Sichtbar, mit niedriggradigen Modell vollständig korrigierbar. "
            "Aggressiveres Modell (hoher Grad, viele Samples) würde in diesem "
            "galaxienreichen Feld ausgedehnte Halos und LSB-Strukturen "
            "als 'Hintergrund' interpretieren und abtragen — "
            "genau die Signale für die die Integration aufgenommen wurde. "
            "Subtraktiv, weil Lichtverschmutzung ein additiver Offset ist: "
            "das Flat hat die Empfindlichkeitsvariationen bereits normiert, "
            "was bleibt ist ein Helligkeitsoffset. "
            "Division würde SNR in dunkleren Bildbereichen verschlechtern."
        ),
    },

    {
        "id": "R04", "phase": "linear", "prio": 4,
        "bedingung": lambda r: True,
        "werkzeug": "SpectrophotometricColorCalibration (SPCC) — nur RGB/LRGB",
        "einstellung": (
            "Nur auf Farb- oder RGB-Master anwenden, nicht auf L-Master. "
            "Katalog: Gaia DR3 (bevorzugt) oder APASS. "
            "Weißreferenz: Durchschnittlicher Spiralgalaxie-Typ oder G2V-Stern. "
            "BackgroundNeutralization vorher auf quellfreiem Hintergrund-Preview ausführen."
        ),
        "begruendung": (
            "SPCC ist die präziseste Farbkalibrierung in PixInsight — "
            "sie basiert auf echten Spektraldaten aus dem Gaia-Katalog, "
            "nicht auf angenommenen Sternenfarben wie ColorCalibration. "
            "Muss linear erfolgen: die photometrischen Referenzwerte gelten "
            "nur für lineare Pixelwerte. Nach einem Stretch sind Sternintensitäten "
            "nichtlinear skaliert und als Farbkalibrierungsreferenz unbrauchbar. "
            "BackgroundNeutralization davor ist zwingend: SPCC setzt voraus "
            "dass der Himmelshintergrund (R=G=B) bereits neutralisiert ist."
        ),
    },

    {
        "id": "R05", "phase": "linear", "prio": 5,
        "bedingung": lambda r: r.get("fwhm_arcsec", 0) > 2.0,
        "werkzeug": "BlurXTerminator",
        "einstellung": (
            "Schritt 1 — PSF-Korrektur: Auto-Mode, Correct Only = true, alle Sharpen = 0. "
            "Ergebnis prüfen: Sterne runder und kleiner — kein Ringing. "
            "Schritt 2 — Schärfung: Correct Only = false, "
            "Sharpen Stars = {sharpen_stars:.2f}, Sharpen Nonstellar = {sharpen_nonstellar:.2f}. "
            "Adjust Halos = true. "
            "Ausschließlich auf lineares Bild anwenden — vor NoiseXTerminator und Stretch."
        ),
        "begruendung": (
            "Gemessene FWHM: {fwhm_arcsec:.2f}\" bei {pixel_scale:.3f}\"/px Bildskala — "
            "klar seeing-limitiert, nicht sampling-limitiert. "
            "Die Optik liefert mehr Auflösung als das Seeing durchgelassen hat. "
            "BlurXTerminator modelliert die PSF und invertiert sie: "
            "ein mathematisch korrekter Dekonvolutionsansatz. "
            "Dekonvolution MUSS im linearen Zustand erfolgen, weil das PSF-Modell "
            "auf einem linearen Zusammenhang zwischen Photonen und Pixelwerten basiert. "
            "Nach einem nichtlinearen Stretch ist dieser Zusammenhang gebrochen — "
            "die Dekonvolution erzeugt Ringing-Artefakte (konzentrische Ringe). "
            "Vor NoiseXTerminator ausführen: Dekon hebt das Rauschen an, "
            "NXT arbeitet besser auf dem geschärften Bild."
        ),
    },

    {
        "id": "R06", "phase": "linear", "prio": 6,
        "bedingung": lambda r: True,
        "werkzeug": "NoiseXTerminator",
        "einstellung": (
            "Denoise: {denoise:.2f} (aus {total_h:.1f}h Integrationstiefe abgeleitet). "
            "Detail: {detail:.2f}. "
            "Nach BlurXTerminator, noch linear. "
            "Auf Preview-Region testen: Hintergrund gleichmäßig, "
            "schwache Galaxien nicht verwaschen. "
            "Falls Texturverlust: Denoise auf 0.55–0.65 reduzieren."
        ),
        "begruendung": (
            "Reihenfolge ist entscheidend: BlurXTerminator hebt das Rauschen an — "
            "Dekonvolution verstärkt alle Frequenzen inklusive Rauschfrequenzen. "
            "NoiseXTerminator danach senkt es wieder, ohne das Signal-Modell zu stören. "
            "Andernfalls würde NXT das Signal entfernen das BXT für die PSF-Schätzung braucht. "
            "Bei {total_h:.1f}h Integration ist der Hintergrund bereits sehr rauscharm "
            "(MAD {noise_mad:.3g}) — moderate Dosierung ({denoise:.2f}) ist korrekt: "
            "zu starkes Denoising (> 0.9) kostet Textur in schwachen Galaxien "
            "und macht sie zu undifferenzierten Klecksen. "
            "Lineare Rauschreduktion ist effizienter als nichtlineare, "
            "weil Rauschen im linearen Raum statistisch sauber modellierbar ist."
        ),
    },

    {
        "id": "R07", "phase": "linear", "prio": 7,
        "bedingung": lambda r: r.get("ecc_p90", 0) > 0.4,
        "werkzeug": "MorphologicalTransformation — optionale Sternkorrektur",
        "einstellung": (
            "Sehr leichte Erosion auf Sternebene (nach StarXTerminator): "
            "Structure = 3 px, Iterations = 1, Amount = 0.10–0.15. "
            "Nur auf Sternebene anwenden, nicht auf Galaxienebene."
        ),
        "begruendung": (
            "Gemessene Exzentrizität p90 = {ecc_p90:.3f}: "
            "die elongiertsten 10% der Sterne zeigen deutliche Verformung — "
            "Guiding-Restfehler oder atmosphärischer Astigmatismus. "
            "Leichte Erosion kann stark elongierte Sterne optisch runder machen "
            "ohne die Galaxienstruktur zu beeinflussen, "
            "weil sie ausschließlich auf die isolierte Sternebene wirkt."
        ),
    },

    # ════════════════════════════════════════════════════
    # NICHTLINEARE PHASE
    # ════════════════════════════════════════════════════

    {
        "id": "R08", "phase": "nichtlinear", "prio": 8,
        "bedingung": lambda r: True,
        "werkzeug": "StarXTerminator",
        "einstellung": (
            "Stars Only = false → Galaxienebene im aktiven Fenster, Sterne in neuem Fenster. "
            "Unscreen = false (Standard). "
            "Sternfenster als <view_id>_stars speichern. "
            "Beide Ebenen vollständig getrennt verarbeiten bis zur Screen-Rekombination."
        ),
        "begruendung": (
            "Sternhüllen konkurrieren mit schwachen ausgedehnten Galaxien "
            "um den Stretch-Dynamikbereich: ein Stretch der helle Sternkerne "
            "und schwache PGC-Hintergrundgalaxien gleichzeitig abdeckt "
            "muss einen Kompromiss eingehen — auf Kosten der schwachen Objekte. "
            "Getrennte Ebenen erlauben für die Galaxienebene einen aggressiven, "
            "tiefen Stretch (Hintergrundgalaxien, NGC-4565-Halo), "
            "für die Sternebene einen konservativen (Sternfarben erhalten, kein Blooming). "
            "Die Screen-Rekombination (~(~G * ~S)) am Ende fügt beide zusammen "
            "ohne Überstrahlungsartefakte."
        ),
    },

    {
        "id": "R09", "phase": "nichtlinear", "prio": 9,
        "bedingung": lambda r: True,
        "werkzeug": "GeneralizedHyperbolicStretch (GHS) — Galaxienebene",
        "einstellung": (
            "Stretch-Typ: STF-Mean (Hintergrundstatistik automatisch). "
            "StretchFactor D = 6–10 (höher = aggressiverer Mittelton-Gewinn). "
            "Local Intensity = 0 beim ersten Stretch. "
            "Highlight Protection = 0.95 (Galaxienkern vor Sättigung schützen). "
            "Ziel: Hintergrund bei ~0.08–0.12, Kern nicht gesättigt. "
            "Mehrere GHS-Iterationen möglich. "
            "Sternebene separat mit D = 3–4 (konservativer) strecken."
        ),
        "begruendung": (
            "GHS bietet gegenüber HistogramTransformation eine explizite Kontrolle "
            "des Symmetrie-Punkts (Hintergrundlevel) und des Stretch-Faktors. "
            "Das ist entscheidend für schwache Galaxienfelder: "
            "ein STF-AutoStretch setzt den Hintergrund zu hell, "
            "was schwache PGC-Galaxien im Himmelsnebel versinken lässt. "
            "GHS hält den Hintergrund aggressiv dunkel ohne "
            "die Mittelton-Struktur der Galaxien zu komprimieren. "
            "Erst hier verlässt das Bild den linearen Zustand — "
            "alle Schritte R00–R07 erfordern zwingend lineare Eingangsdaten."
        ),
    },

    {
        "id": "R10", "phase": "nichtlinear", "prio": 10,
        "bedingung": lambda r: True,
        "werkzeug": "HDRMultiscaleTransform (HDRMT)",
        "einstellung": (
            "Layers = 6, Median Transform = true. "
            "Lightness Mask aktivieren (schützt Hintergrund). "
            "Iterations = 1, Amount = 0.5–0.7. "
            "Nur auf Galaxienebene. "
            "Ziel: Dynamikkompression im Galaxienkern ohne Halo-Verlust."
        ),
        "begruendung": (
            "Edge-on-Galaxien wie NGC 4565 haben einen extrem hellen Zentralkern "
            "bei gleichzeitig sehr schwachen äußeren Halobereichen — "
            "ein Dynamikbereich der über den Stretch oft nicht vollständig erfasst wird. "
            "HDRMT komprimiert die Luminanz auf großen Skalen (Kern) "
            "ohne die feinen Detailstrukturen (Staubband, Spiralarm-Ansätze) zu glätten. "
            "Median Transform verhindert Haloartefakte um den Kern. "
            "Nur auf Galaxienebene — auf Sterne hätte es keinen sinnvollen Effekt "
            "und würde Sternhüllen deformieren."
        ),
    },

    {
        "id": "R11", "phase": "nichtlinear", "prio": 11,
        "bedingung": lambda r: True,
        "werkzeug": "LocalHistogramEqualization (LHE)",
        "einstellung": (
            "Kernel Radius = 64–128 px, Amount = 0.10–0.20, Limit = 1.5–2.0. "
            "Nur auf Galaxienebene, mit Range-Maske auf Mittelton-Bereich (0.15–0.65). "
            "Nicht auf Hintergrund (strukturiert Rauschen) oder Sternkerne (Halos)."
        ),
        "begruendung": (
            "LHE hebt lokalen Kontrast in Strukturen hervor die global ähnliche "
            "Helligkeiten haben — ideal für das Staubband und die Staubstruktur "
            "in NGC 4565's Scheibe, die durch globale Kontrast-Stretches "
            "kaum differenzierbar sind. "
            "Konservative Einstellung ist zwingend: aggressives LHE verstärkt "
            "auch Bildrauschen und erzeugt strukturiertes Rauschen "
            "das wie falsche Textur aussieht. "
            "Range-Maske schützt Hintergrund und Sternkerne."
        ),
    },

    {
        "id": "R12", "phase": "nichtlinear", "prio": 12,
        "bedingung": lambda r: True,
        "werkzeug": "CurvesTransformation — Finishbearbeitung",
        "einstellung": (
            "Schritt 1 — Kontrast: leichte S-Kurve in Luminanz, "
            "Symmetriepunkt bei ~0.35 (Hintergrund bleibt dunkel, Mitteltöne angehoben). "
            "Schritt 2 — Farbe (RGB/LRGB): Sättigung im HS-Modus +10–15%. "
            "Blau/Violett-Ton der Hintergrundgalaxien betonen. "
            "Schritt 3 — Schwarzpunkt feinjustieren falls nötig."
        ),
        "begruendung": (
            "CurvesTransformation ist das präziseste Kontrast-/Farbwerkzeug in PixInsight "
            "weil es jeden Tonwertbereich unabhängig kontrolliert. "
            "S-Kurve in Luminanz ist das effektivste Mittel um Hintergrundgalaxien "
            "gegen den Himmel abzuheben ohne den Hintergrund aufzuhellen. "
            "Farbsättigung erst ganz am Ende: zu früh erhöhte Sättigung wird "
            "durch alle nachfolgenden Luminanzoperationen (HDRMT, LHE) "
            "inkonsistent verändert und muss danach erneut korrigiert werden."
        ),
    },

    {
        "id": "R13", "phase": "nichtlinear", "prio": 13,
        "bedingung": lambda r: True,
        "werkzeug": "PixelMath — Screen-Rekombination",
        "einstellung": (
            "Formel: ~(~$T * ~stars_layer) "
            "Ziel: aktuelle sternlose Galaxienebene. "
            "UseSingleExpression = true, CreateNewImage = false. "
            "Beide Ebenen müssen vollständig fertig bearbeitet sein."
        ),
        "begruendung": (
            "Screen-Blend ist mathematisch: 1 − (1−A) × (1−B) = A + B − A×B. "
            "Dadurch können keine Werte > 1 entstehen (kein Clipping), "
            "Sternkerne überstrahlen die Galaxienebene nicht. "
            "Im Gegensatz zur additiven Kombination (A+B) bleibt die Galaxiendynamik "
            "vollständig erhalten, weil bei hellen Sternen (B→1) der Ausdruck → 1 geht "
            "statt die Galaxienebene zu überschreiben. "
            "Rekombination erst ganz am Schluss — alle Korrekturen "
            "(HDRMT, LHE, Curves) müssen davor abgeschlossen sein."
        ),
    },

    {
        "id": "R14", "phase": "annotation", "prio": 14,
        "bedingung": lambda r: r.get("wcs_available", False),
        "werkzeug": "Script › Render › AnnotateImage",
        "einstellung": (
            "Kataloge: NGC/IC, PGC/HyperLEDA, optional Gaia DR3. "
            "Font-Größe bei 9576 px Breite: ca. 18–22 pt. "
            "Label-Farben: NGC/IC = Gelb, PGC = Magenta, Sterne = Weiß."
        ),
        "begruendung": (
            "Die WCS-Lösung (PCL:AstrometricSolution) wird von PixInsight direkt genutzt — "
            "kein erneutes Plate-Solving nötig. "
            "PGC/HyperLEDA ist entscheidend für dieses Feld: "
            "55+ High-Confidence-PGC-Kandidaten detektiert, die im NGC/IC-Katalog fehlen. "
            "HyperLEDA benennt diese zuverlässig. "
            "Gegenprobe mit nova.astrometry.net empfohlen."
        ),
    },

    {
        "id": "R15", "phase": "aufnahme", "prio": 15,
        "bedingung": lambda r: r.get("dithering_ratio", 0) > 0.5,
        "werkzeug": "N.I.N.A. — Dithering-Konfiguration",
        "einstellung": (
            "Dither Every = 1 Sub. Scale = 2.0–3.0 (~20–30 px). "
            "Settle At = 0.5 px, Timeout = 60 s. "
            "RandomPattern aktivieren. "
            "Nur bei stabilem Guiding < 1.5 px RMS dithern."
        ),
        "begruendung": (
            "Gemessenes Verhältnis Pattern/Stack-Rauschen: {dithering_ratio:.1f}×. "
            "Nach {n_subs} Subs ist das Banding-Muster {dithering_ratio:.0f}-mal "
            "stärker als das thermische Stack-Rauschen — es integriert sich tiefer ein. "
            "Dithering bricht die Korrelation zwischen festem Sensor-Muster "
            "und Himmels-Koordinaten auf: nach N Subs mit pseudo-zufälligem Versatz "
            "mittelt das Muster gegen das zufällige Hintergrundrauschen aus. "
            "Bei korrektem Dithering (≥ Banding-Periode, pseudo-random) "
            "verschwindet das Muster proportional √N — wie echtes Rauschen. "
            "RandomPattern verhindert systematische Lücken im Versatz-Raum. "
            "Kein nachträgliches Skript kann das vollständig ersetzen."
        ),
    },

    {
        "id": "R16", "phase": "aufnahme", "prio": 16,
        "bedingung": lambda r: r.get("fwhm_arcsec", 0) > 3.5,
        "werkzeug": "Fokus-Optimierung (nächste Session)",
        "einstellung": (
            "Auto-Fokus in N.I.N.A.: HFD-Methode, Exposure 5–10s, "
            "Step-Size 10–20 Motorschritte. "
            "Temperatur-Kompensation aktivieren (AP155 hat messbaren Temperaturgang). "
            "Refokus-Trigger: Temperaturdelta > 0.5°C oder alle 90 min."
        ),
        "begruendung": (
            "Gemessene FWHM {fwhm_arcsec:.2f}\" — für die AP155 EDF sind "
            "unter 2.5\" bei guten Bedingungen realistisch. "
            "Ein Teil der gemessenen FWHM könnte auf Fokusdrift zurückgehen "
            "(Temperaturschwankungen > 2°C in der Session). "
            "Regelmäßiger Refokus hält die PSF-Qualität konstant "
            "und macht den BlurXTerminator-Schritt effektiver."
        ),
    },

]


def run(img_stats: dict, acq_results: dict, calib_results: dict,
        wcs_available: bool, progress_cb=None) -> list[dict]:
    """
    Kombiniert Ergebnisse aller Module → geordnete, parametrisierte Empfehlungsliste.
    Rückgabe: Liste von Dicts mit id, phase, werkzeug, einstellung, begruendung
    """
    def pg(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    pg(10, "Regeln auswerten …")

    dith  = acq_results.get("dithering",   {})
    intg  = acq_results.get("integration", {})

    fwhm      = img_stats.get("fwhm_arcsec",   3.5)
    pscale    = img_stats.get("pixel_scale",   0.698)
    total_h   = intg.get("total_h",  1.0)
    n_subs    = intg.get("n_subs",   1)
    noise_mad = img_stats.get("noise_mad", 1.88e-4)
    flat_corr = calib_results.get("flat_mismatch", {}).get("korrelation", 0)
    dith_ratio = dith.get("ratio", 0)
    banding_amp = img_stats.get("banding_amp", 0)
    banding_ratio = banding_amp / noise_mad if noise_mad > 0 else 0

    # Abgeleitete Parameter
    sharpen_ns = round(min(0.6,  max(0.15, (fwhm - 2.0) * 0.15)), 2) if fwhm > 2 else 0.15
    sharpen_st = round(min(0.25, sharpen_ns * 0.4), 2)
    denoise    = round(min(0.85, max(0.55, 0.85 - (total_h - 1) * 0.02)), 2)
    detail     = round(min(0.30, 0.10 + total_h * 0.015), 2)

    ctx = {
        **img_stats,
        "flat_corr":       flat_corr,
        "wcs_available":   wcs_available,
        "dithering_ratio": dith_ratio,
        "total_h":         total_h,
        "n_subs":          n_subs,
        "banding_ratio":   banding_ratio,
    }

    pg(40, "Parameter interpolieren …")
    fmt = {
        "fwhm_arcsec":        fwhm,
        "pixel_scale":        pscale,
        "gradient_pct":       round(img_stats.get("gradient_pct",   0), 1),
        "gradient_sigma":     round(img_stats.get("gradient_sigma", 0), 1),
        "banding_ratio":      round(banding_ratio, 1),
        "noise_mad":          noise_mad,
        "total_h":            total_h,
        "n_subs":             n_subs,
        "sharpen_nonstellar": sharpen_ns,
        "sharpen_stars":      sharpen_st,
        "denoise":            denoise,
        "detail":             detail,
        "dithering_ratio":    round(dith_ratio, 1),
        "ecc_p90":            round(img_stats.get("ecc_p90", 0.2), 3),
        "flat_corr":          round(flat_corr, 3),
    }

    pg(60, "Aktive Regeln filtern …")
    aktiv = [r for r in REGELN if r["bedingung"](ctx)]
    aktiv.sort(key=lambda r: r["prio"])

    pg(90, "Texte formatieren …")
    result = []
    for i, r in enumerate(aktiv):
        try:   einst = r["einstellung"].format(**fmt)
        except: einst = r["einstellung"]
        try:   begr = r["begruendung"].format(**fmt)
        except: begr = r["begruendung"]
        result.append({
            "nr":          i + 1,
            "id":          r["id"],
            "phase":       r["phase"],
            "werkzeug":    r["werkzeug"],
            "einstellung": einst,
            "begruendung": begr,
        })

    pg(100, f"PixInsight-Empfehlungen: {len(result)} Schritte generiert.")
    return result
