"""de-CH copy for everything Zorbeck sends or answers outside the templates.

Rules: "Sie", ss instead of ß, CHF 1'390 with an apostrophe as thousands
separator, plain words, no buzzwords, no comparisons with anyone else.
"""

from __future__ import annotations

PRODUCT_NAME = "Zorbeck Deal-Alarm"

# --- form / checkout --------------------------------------------------------

ERROR_EMAIL = "Bitte geben Sie eine gültige E-Mail-Adresse ein."
ERROR_CITY = "Bitte geben Sie die Stadt an, in der wir suchen sollen."
ERROR_BUDGET = "Bitte geben Sie das Budget als ganze Zahl in CHF an."
ERROR_BUDGET_ORDER = "Bitte prüfen Sie das Budget: «bis» muss grösser sein als «von»."
ERROR_PAYMENT_UNAVAILABLE = "Die Zahlung ist im Moment nicht möglich. Bitte versuchen Sie es in ein paar Minuten nochmals."
ERROR_PAYMENT_FAILED = "Die Zahlung konnte nicht gestartet werden. Bitte versuchen Sie es nochmals."
SIGNUP_OK = "Danke. Zorbeck meldet sich per E-Mail, sobald wir {city} abdecken."
ERROR_SERVER ="Da ist etwas schiefgelaufen. Wir wurden benachrichtigt. Bitte versuchen Sie es in ein paar Minuten nochmals."

# --- success page -----------------------------------------------------------

SUCCESS_TITLE = "Zahlung erhalten. Ihr Deal-Alarm ist eingerichtet."
SUCCESS_NEXT = "Was jetzt passiert"
# Both end with the buyer's e-mail address, rendered by the template.
SUCCESS_MAILED = "Diese Bestätigung mit den Schritten unten ist unterwegs an"
SUCCESS_MAIL_LATER = "Ihre Angaben sind gespeichert. Die Bestätigung per E-Mail folgt in wenigen Minuten an"
SUCCESS_PENDING = "Ihre Zahlung ist noch nicht bestätigt. Laden Sie diese Seite in einer Minute nochmals."
SUCCESS_UNKNOWN = "Wir konnten diese Zahlung nicht finden. Falls Sie bezahlt haben, schreiben Sie an info@startend.ch."

# --- confirmation e-mail ----------------------------------------------------

MAIL_SUBJECT = "Ihr Zorbeck Deal-Alarm für {city} ist eingerichtet"

MAIL_BODY = """Guten Tag

Vielen Dank. Ihre Zahlung von {amount} ist eingegangen und Ihr Deal-Alarm ist eingerichtet.

Ihre Angaben
- Stadt: {city}
- Budget: {budget}
- E-Mail: {email}

Was jetzt passiert
{timeline}

Stimmt etwas nicht? Antworten Sie einfach auf diese E-Mail.

Freundliche Grüsse
STARTEND GmbH, Cham
Bahnhofstrasse 7, 6330 Cham · info@startend.ch
Impressum, AGB und Datenschutz: {base_url}/impressum · {base_url}/agb · {base_url}/datenschutz
"""

BUDGET_UNLIMITED = "ohne Obergrenze"
BUDGET_FROM = "ab {min}"
BUDGET_TO = "bis {max}"
BUDGET_RANGE = "{min} bis {max}"

# The first value: what happens next, step by step, with no human in the
# loop. Shown on the success page and in the mail. {city} is filled in.
TIMELINE: tuple[tuple[str, str], ...] = (
    ("Sofort", "Diese Bestätigung mit Ihren Angaben, auf dieser Seite und per E-Mail."),
    ("Innerhalb von 24 Stunden", "Der erste Report: Inserate in {city}, die unter dem Durchschnitt liegen und in Ihr Budget passen."),
    ("30 Tage lang", "Eine E-Mail, sobald ein neues Inserat in {city} unter dem Durchschnitt erscheint."),
    ("Danach", "Der Alarm endet von selbst. Keine Verlängerung, nichts zu kündigen."),
)
