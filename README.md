# vzillner

Statische Website (HTML) — bereit für Deployment auf Vercel.

## Struktur

| Datei | Seite |
| --- | --- |
| `index.html` | Startseite |
| `behandlung.html` | Behandlung (Übersicht) |
| `behandlung/*.html` | Behandlung (Unterseiten) |
| `villa.html` | Villa |
| `zur-person.html` | Zur Person |
| `kontakt.html` | Kontakt |
| `formular.html` | Formular |
| `datenschutzerklaerung.html` | Datenschutzerklärung |
| `datenschutzhinweis.html` | Datenschutzhinweis |
| `404.html` | Fehlerseite |
| `ru/**` | Russische Version (generiert, siehe unten) |
| `framer/` | Framer-Runtime, Seitentexte und CMS-Daten (selbst gehostet) |
| `tools/` | Skripte zum Ändern der Texte und Erzeugen von `ru/` |

## Texte ändern

Die Seiten werden beim Laden von der Framer-Runtime aus `framer/` neu gerendert —
Text direkt im HTML zu ändern reicht deshalb nicht. Die Texte liegen in:

- `tools/apply_ru_texts.py` — russische Seitentexte (Navigation, Footer, Seiten);
- `tools/apply_cms_texts.py` — Behandlungsseiten (CMS), russisch und deutsch;
- `tools/build_ru_pages.py` — erzeugt `ru/**` aus den deutschen Seiten und übernimmt
  CMS-Texte ins HTML; `tools/ru_ssr_dict.json` enthält die Textpaare Deutsch → Russisch
  für das serverseitige HTML.

Nach einer Änderung alle drei der Reihe nach ausführen:

```bash
python tools/apply_ru_texts.py && python tools/apply_cms_texts.py && python tools/build_ru_pages.py
```

Ein neuer Export aus Framer überschreibt diese Änderungen — Texte daher auch im
Framer-Projekt nachziehen.

## Deployment

`vercel.json` setzt `cleanUrls`, deaktiviert `trailingSlash` und cached statische
Assets (Bilder, Fonts, Media) mit `max-age=31536000, immutable`. Dateien unter
`framer/` werden bei jedem Aufruf revalidiert, weil sie beim Ändern der Texte ihren
Namen behalten.

Lokal ansehen:

```bash
npx serve .
```
