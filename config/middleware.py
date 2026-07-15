import uuid


class CSPNonceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generamos un nonce único para esta petición
        request.csp_nonce = uuid.uuid4().hex
        response = self.get_response(request)
        # Lo guardamos en la respuesta para usarlo en la plantilla
        return response
