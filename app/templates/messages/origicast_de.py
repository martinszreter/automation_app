# German (de-CH) customer-facing text for /origicast — the 21+ door.
# All customer-facing text lives here — never hard-code messages inline.
# de-CH: ss instead of ß, CHF 1'390 style thousands, "Sie".

BRAND = "ORIGICAST"
TAGLINE = "Für Erwachsene. Ab 21."

# --- gate ---------------------------------------------------------------------
GATE_TITLE = "ORIGICAST — Zugang ab 21"
GATE_HEADLINE = "Sind Sie 21 Jahre oder älter?"
GATE_LEAD = (
    "ORIGICAST richtet sich ausschliesslich an Erwachsene ab 21 Jahren. "
    "Bitte bestätigen Sie Ihr Alter, um die Tür zu öffnen."
)
GATE_YES = "Ja, ich bin 21 oder älter"
GATE_NO = "Nein"
GATE_NOTE = "Ihre Antwort wird nur in einem Sitzungs-Cookie gespeichert — 14 Tage, kein Tracking."

LEAVE_TITLE = "ORIGICAST — Kein Zugang"
LEAVE_HEADLINE = "Kein Zugang unter 21."
LEAVE_LEAD = "Danke für Ihre Ehrlichkeit. Diese Seite ist Erwachsenen ab 21 Jahren vorbehalten."
LEAVE_BACK = "Zurück zu startend.ch"

# --- door -----------------------------------------------------------------------
DOOR_TITLE = "ORIGICAST — Die Tür"
DOOR_KICKER = "Die Tür ist offen"
DOOR_HEADLINE = "Ein Abend, der bleibt."
DOOR_LEAD = (
    "ORIGICAST kuratiert seltene Momente für Erwachsene: ausgewählt, begrenzt, persönlich. "
    "Bevor die erste Saison öffnet, zeigen wir mit einem Test, dass Zahlung, Bestätigung "
    "und Rückerstattung funktionieren."
)
TEST_KICKER = "Der Test"
TEST_HEADLINE = "CHF 1 — einmal bezahlen, sofort zurück."
TEST_LEAD = (
    "Sie zahlen CHF 1.00 über Stripe, erhalten die Bestätigung und wir erstatten den "
    "Betrag innerhalb eines Werktages. So prüfen wir den Weg vom Klick bis zur Rückerstattung."
)
TEST_PRICE = "CHF 1.00"
TEST_PRICE_NOTE = "einmalig · Rückerstattung innerhalb eines Werktages"
TEST_BUTTON = "CHF 1 Test bezahlen"
TEST_PRODUCT_NAME = "ORIGICAST — CHF 1 Test"
TEST_UNAVAILABLE = "Der Test ist gerade nicht verfügbar. Bitte versuchen Sie es später nochmals."

OFFERS_KICKER = "Drei Wege hinein"
OFFER_SEASON = "Season"
OFFER_SEASON_LEAD = "Die ganze Saison, alle Abende."
OFFER_HOUR = "Hour"
OFFER_HOUR_LEAD = "Eine Stunde, ein Abend, ein Platz."
OFFER_KEEP = "Keep"
OFFER_KEEP_LEAD = "Etwas, das Sie mitnehmen."
OFFER_SOON = "Öffnet mit der ersten Saison."

# --- success --------------------------------------------------------------------
SUCCESS_TITLE = "ORIGICAST — Zahlung erhalten"
SUCCESS_KICKER = "Zahlung erhalten"
SUCCESS_HEADLINE = "Danke. Der Test ist bezahlt."
SUCCESS_LEAD = (
    "Stripe hat Ihre Zahlung von CHF 1.00 bestätigt. Wir erstatten den Betrag innerhalb "
    "eines Werktages auf dasselbe Zahlungsmittel. Sie erhalten die Bestätigung per E-Mail von Stripe."
)
SUCCESS_REFERENCE = "Referenz"
SUCCESS_BACK = "Zurück zur Tür"

# --- footer / legal (every page) -------------------------------------------------
LEGAL_COMPANY = "STARTEND GmbH · CHE-223.488.613 · Bahnhofstrasse 7 · 6330 Cham"
LEGAL_IMPRINT = "Impressum"
LEGAL_TERMS = "AGB"
LEGAL_PRIVACY = "Datenschutz"
LEGAL_CONTACT = "info@startend.ch"

# --- HQ notification (internal, English is fine but kept German for one voice)
HQ_MAIL_SUBJECT = "ORIGICAST: CHF 1 Test bezahlt"
HQ_MAIL_BODY = (
    "ORIGICAST CHF 1 Test bezahlt.\n"
    "Session: {session_id}\n"
    "E-Mail: {email}\n"
    "Betrag: {amount} {currency}\n"
    "Nächster Schritt: in Stripe zurückerstatten (Payments → Refund)."
)
