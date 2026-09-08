# German (de-CH: ss, never ß; "Sie") customer-facing text for the X Autopilot
# panel and the weekly digest. All customer-facing text lives here.

PANEL_TITLE = "Panel — X Autopilot"
PILL_ACTIVE = "Plan aktiv"
PILL_PAUSED = "Pausiert"
PILL_NONE = "Kein aktiver Plan"
SIGNED_IN_AS = "Angemeldet als"

FACT_PLAN = "Plan"
FACT_PRODUCT = "Produkt"
FACT_AMOUNT = "Betrag"
FACT_STRIPE_EMAIL = "Stripe-E-Mail"
FACT_NEXT_INVOICE = "Nächste Rechnung"
FACT_AGENT = "Konto"
STATUS_ACTIVE = "Aktiv"
STATUS_PAUSED = "Pausiert"
STATUS_NONE = "Keiner"
INVOICE_NONE = "keine (Einmalzahlung)"
INVOICE_UNKNOWN = "wird von Stripe geladen"

NO_PLAN = (
    "Auf diesem Google-Konto ist kein aktiver Plan. Bezahlen Sie auf der "
    "Preisseite und kommen Sie zurück — kein Kontakt nötig."
)
PRICING_LINK = "Preisseite"
REFUND_BUTTON = "CHF 1 Testzahlung erstatten"

CALENDAR_TITLE = "Geplante Posts — nächste 7 Tage"
CALENDAR_HINT = "Zeiten in Europe/Zurich. Die Slots kommen aus Ihrem Posting-Rhythmus."
CALENDAR_PAUSED = "Pausiert: geplante Posts werden nicht veröffentlicht, bis Sie fortsetzen."
SLOT_STATUS_SCHEDULED = "geplant"
SLOT_STATUS_PAUSED = "pausiert"
PAUSE_BUTTON = "Posts pausieren"
RESUME_BUTTON = "Posts fortsetzen"

POSTS_TITLE = "Veröffentlichte Posts"
NO_POSTS = "Noch keine veröffentlichten Posts."
COL_DATE = "Datum"
COL_POST = "Post"
COL_IMPRESSIONS = "Impressionen"
COL_LIKES = "Likes"
METRICS_PENDING = "—"
LANE_UNAVAILABLE = "Kennzahlen sind gerade nicht erreichbar. Der Plan läuft weiter."

SHEETS_TITLE = "Google Sheets"
SHEETS_READ_OK = "Lesen ok"
SHEETS_ROWS = "Zeilen"
SHEETS_NOT_CONNECTED = "Sheets ist nicht verbunden. Wir kümmern uns darum — Sie müssen nichts tun."

SIGN_OUT = "Abmelden"

DIGEST_SUBJECT = "X Autopilot — Ihre Woche: {count} Posts"
DIGEST_LINE = "{date} · {impressions} Impressionen · {likes} Likes\n{text}"
DIGEST_NO_METRICS = "noch keine"
DIGEST_BODY = (
    "Guten Tag\n\n"
    "Ihre Wochenübersicht für X Autopilot ({period}).\n\n"
    "Veröffentlicht: {count} Posts\n"
    "{lines}\n\n"
    "Geplant für die nächsten 7 Tage: {scheduled} Posts.\n"
    "{status_line}\n\n"
    "Panel: {panel_url}\n\n"
    "Freundliche Grüsse\n"
    "STARTEND GmbH, Cham · info@startend.ch"
)
DIGEST_STATUS_ACTIVE = "Status: aktiv."
DIGEST_STATUS_PAUSED = "Status: pausiert — im Panel können Sie jederzeit fortsetzen."
DIGEST_NO_POSTS = "Diese Woche wurde noch nichts veröffentlicht."
