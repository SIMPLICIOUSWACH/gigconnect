"""
Spotting contact or payment details in a message, so the sender can be reminded to keep payments on GigConnect. The
message is always sent: this only decides whether to show the tip.
"""

import re

SAFETY_TIP = "Keep payments on GigConnect so you're protected."

EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
# A Kenyan mobile in any common form, or any long run of digits with spaces or dashes, like a phone or till number.
PHONE = re.compile(r'(?:\+?254|\b0)?[\s-]?[17]\d{2}[\s-]?\d{3}[\s-]?\d{3}\b|\+?\d[\d\s-]{8,}\d')
PAYMENT_WORDS = re.compile(r'm[\s-]?pesa|paybill|pay\s?bill|till\s?(?:no|number)?', re.IGNORECASE)
NUMBER = re.compile(r'\d{4,}')


def mentions_contact_or_payment(text):
    if EMAIL.search(text) or PHONE.search(text):
        return True
    return bool(PAYMENT_WORDS.search(text) and NUMBER.search(text))
