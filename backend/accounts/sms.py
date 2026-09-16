class SMSProvider:
    """Stub SMS provider — swap this out for a real vendor (e.g. Africa's Talking) later.

    Everything upstream calls SMSProvider.send(); no other code should know
    which vendor is behind it.
    """

    @staticmethod
    def send(phone, message):
        print(f'[SMS to {phone}] {message}')
