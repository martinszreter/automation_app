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
