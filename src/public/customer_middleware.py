from django.utils import timezone

from .customer_sessions import get_authenticated_customer


class CustomerSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.customer_user = get_authenticated_customer(request, timezone.now())
        return self.get_response(request)
