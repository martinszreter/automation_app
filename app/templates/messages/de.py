# German guest-facing message templates.
# All guest-facing text lives here — never hard-code messages inline.

BOOKING_CONFIRMED = (
    "Hallo {guest_name}, Ihre Reservierung bei {restaurant} "
    "am {date} um {time} Uhr für {party_size} Personen ist bestätigt. "
    "Wir freuen uns auf Sie!"
)

BOOKING_REMINDER = (
    "Erinnerung: Ihre Reservierung bei {restaurant} ist morgen "
    "am {date} um {time} Uhr für {party_size} Personen. "
    "Bitte antworten Sie mit JA zum Bestätigen oder NEIN zum Stornieren."
)

BOOKING_CANCELLED = (
    "Ihre Reservierung bei {restaurant} am {date} um {time} Uhr "
    "wurde storniert. Vielen Dank für Ihre Nachricht."
)

PARTY_SIZE_CHANGED = (
    "Die Personenanzahl für Ihre Reservierung bei {restaurant} "
    "am {date} um {time} Uhr wurde auf {party_size} geändert."
)

ALREADY_CONFIRMED = (
    "Ihre Reservierung bei {restaurant} am {date} um {time} Uhr "
    "ist bereits bestätigt."
)

ALREADY_CANCELLED = (
    "Ihre Reservierung bei {restaurant} am {date} um {time} Uhr "
    "wurde bereits storniert."
)

UNKNOWN_MESSAGE = (
    "Entschuldigung, ich habe Ihre Nachricht nicht verstanden. "
    "Bitte antworten Sie mit JA zum Bestätigen, NEIN zum Stornieren, "
    "oder einer Zahl um die Personenanzahl zu ändern."
)

NO_ACTIVE_BOOKING = (
    "Es wurde keine aktive Reservierung für Ihre Nummer gefunden."
)
