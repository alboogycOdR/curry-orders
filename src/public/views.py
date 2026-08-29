"""Placeholder views only — real templates/forms/API land with milestones
2-4+ (spec §22). These exist so `config/urls.py` has something to point
`public:home` / `public:order` / `public:checkout` at without crashing
`python manage.py check`, matching what src/templates/base.html already
has TODO'd `{% url %}` calls for. Deliberately plain HttpResponse stubs
(not TemplateView) so nothing here depends on a template file — templates/
is the other agent's territory.
"""
from django.http import HttpRequest, HttpResponse


def home(request: HttpRequest) -> HttpResponse:
    return HttpResponse("public:home placeholder — see spec §6.1, milestone 2")


def order(request: HttpRequest, public_token: str = "") -> HttpResponse:
    # Spec §6.1 route is /orders/:public_token; kept as a single stub name
    # ("order") to match what base.html's TODO already names.
    return HttpResponse("public:order placeholder — see spec §6.1, milestone 4")


def checkout(request: HttpRequest) -> HttpResponse:
    return HttpResponse("public:checkout placeholder — see spec §11.6, milestone 3")
