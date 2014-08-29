from __future__ import print_function

from django.shortcuts import render_to_response
from django.http import HttpResponse
from django.template import RequestContext
import json


def render(object, template, locals, request):
    if 'application/json' in request.META['HTTP_ACCEPT']:
        return HttpResponse(json.dumps(object), content_type='application/json')
    else:
        return render_to_response(template, locals, context_instance=RequestContext(request))
