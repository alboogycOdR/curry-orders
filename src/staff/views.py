"""Placeholder views only — see public/views.py's module docstring for the
same rationale. Real staff dashboard views land with milestones 5-9.
"""
from django.http import HttpRequest, HttpResponse


def kitchen(request: HttpRequest) -> HttpResponse:
    return HttpResponse("manage:kitchen placeholder — see spec §12.4, milestone 6")
