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

## Deployment

`vercel.json` setzt `cleanUrls`, deaktiviert `trailingSlash` und cached statische
Assets (Bilder, Fonts, Media) mit `max-age=31536000, immutable`.

Lokal ansehen:

```bash
npx serve .
```
