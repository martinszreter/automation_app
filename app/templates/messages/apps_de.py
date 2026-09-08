# German customer-facing text for /apps (setup form on the success page).
# All customer-facing text lives here — never hard-code messages inline.

SUCCESS_HEADLINE = "Zahlung erhalten. Noch drei Angaben."
SUCCESS_LEAD = (
    "Damit wir Ihre WhatsApp-Reservierung einrichten können, brauchen wir "
    "den Namen Ihres Restaurants, Ihre Schweizer Nummer und Ihre Öffnungszeiten."
)

FIELD_RESTAURANT = "Name des Restaurants"
FIELD_PHONE = "Schweizer Telefonnummer (WhatsApp)"
FIELD_PHONE_HINT = "Zum Beispiel 079 938 03 72 oder +41 79 938 03 72."
FIELD_OPENING_HOURS = "Öffnungszeiten"
FIELD_OPENING_HOURS_HINT = "Zum Beispiel: Di–Sa 11:30–14:00 und 18:00–23:00, So und Mo geschlossen."
SUBMIT = "Angaben senden"

ERROR_RESTAURANT_REQUIRED = "Bitte geben Sie den Namen Ihres Restaurants an."
ERROR_OPENING_HOURS_REQUIRED = "Bitte geben Sie Ihre Öffnungszeiten an."
ERROR_PHONE_INVALID = (
    "Diese Nummer erkennen wir nicht als Schweizer Nummer. "
    "Bitte im Format 079 938 03 72 oder +41 79 938 03 72 angeben."
)
ERROR_SAVE_FAILED = (
    "Wir konnten Ihre Angaben gerade nicht speichern. "
    "Bitte versuchen Sie es nochmals oder schreiben Sie an info@startend.ch."
)

DONE_HEADLINE = "Danke — wir haben alles."
DONE_LEAD = (
    "Wir richten Ihre WhatsApp-Reservierung ein und melden uns innerhalb "
    "eines Werktages bei Ihnen. Fragen? info@startend.ch"
)

# /apps/demo — a prospect books a live demo (date, guests, confirm).
DEMO_TITLE = "Demo buchen — WhatsApp-Reservierung"
DEMO_HEADLINE = "Demo buchen. 20 Minuten, live auf WhatsApp."
DEMO_LEAD = (
    "Sie wählen Datum und Personenanzahl wie ein Gast — wir zeigen Ihnen den "
    "ganzen Ablauf auf Ihrem Handy: Anfrage, Bestätigung, Erinnerung, Absage."
)
DEMO_FIELD_RESTAURANT = "Name des Restaurants"
DEMO_FIELD_CONTACT = "Ihre E-Mail-Adresse oder Telefonnummer"
DEMO_FIELD_CONTACT_HINT = "Darüber bestätigen wir den Termin."
DEMO_FIELD_DATE = "Wunschdatum"
DEMO_FIELD_TIME = "Uhrzeit (optional)"
DEMO_FIELD_GUESTS = "Personenanzahl"
DEMO_FIELD_NOTE = "Notiz (optional)"
DEMO_GUESTS_WORD = "Personen"
DEMO_SUBMIT = "Demo bestätigen"

DEMO_ERROR_CONTACT_REQUIRED = "Bitte geben Sie eine E-Mail-Adresse oder Telefonnummer an."
DEMO_ERROR_DATE_INVALID = "Bitte wählen Sie ein Datum ab heute."
DEMO_ERROR_GUESTS_INVALID = "Bitte geben Sie eine Personenanzahl zwischen 1 und 50 an."
DEMO_ERROR_SEND_FAILED = (
    "Wir konnten Ihre Demo-Buchung gerade nicht übermitteln. "
    "Bitte versuchen Sie es nochmals oder schreiben Sie an info@startend.ch."
)

DEMO_DONE_TITLE = "Demo gebucht — WhatsApp-Reservierung"
DEMO_DONE_HEADLINE = "Demo gebucht."
DEMO_DONE_LEAD = "Wir bestätigen den Termin über den Kontakt, den Sie angegeben haben."

# Internal confirmation to the HQ inbox (sent through HQ Mail).
DEMO_MAIL_SUBJECT = "Demo-Buchung /apps: {restaurant} — {date} {time}, {guests} Personen"
DEMO_MAIL_BODY = (
    "Neue Demo-Buchung über startend.ch/apps/demo\n\n"
    "Restaurant: {restaurant}\n"
    "Kontakt: {contact}\n"
    "Datum: {date}\n"
    "Uhrzeit: {time}\n"
    "Personen: {guests}\n"
    "Notiz: {note}\n\n"
    "Bitte den Termin über den angegebenen Kontakt bestätigen."
)
