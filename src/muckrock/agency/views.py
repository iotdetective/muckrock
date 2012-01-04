"""
Views for the Agency application
"""

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.http import Http404
from django.shortcuts import render_to_response, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.template import RequestContext

from agency.forms import AgencyForm, FlagForm
from agency.models import Agency
from foia.models import FOIARequest
from jurisdiction.models import Jurisdiction
from jurisdiction.views import collect_stats

def detail(request, jurisdiction, slug, idx):
    """Details for an agency"""

    jmodel = get_object_or_404(Jurisdiction, slug=jurisdiction)
    agency = get_object_or_404(Agency, jurisdiction=jmodel, slug=slug, pk=idx)

    if not agency.approved:
        raise Http404()

    context = {'agency': agency}
    collect_stats(agency, context)

    return render_to_response('agency/agency_detail.html', context,
                              context_instance=RequestContext(request))

@login_required
def update(request, jurisdiction, slug, idx):
    """Allow the user to fill in some information about new agencies they create"""

    jmodel = get_object_or_404(Jurisdiction, slug=jurisdiction)
    agency = get_object_or_404(Agency, jurisdiction=jmodel, slug=slug, pk=idx)

    if agency.user != request.user or agency.approved:
        messages.error(request, 'You may only edit your own agencies which have '
                                'not been approved yet')
        return redirect('foia-mylist', view='all')

    if request.method == 'POST':
        form = AgencyForm(request.POST, instance=agency)
        if form.is_valid():
            form.save()
            messages.success(request, 'Agency information saved.')
            foia_pk = request.GET.get('foia')
            foia = FOIARequest.objects.filter(pk=foia_pk)
            if foia:
                return redirect(foia[0])
            else:
                return redirect('foia-mylist', view='all')
    else:
        form = AgencyForm(instance=agency)

    return render_to_response('agency/agency_form.html', {'form': form},
                              context_instance=RequestContext(request))

def flag(request, jurisdiction, slug, idx):
    """Flag a correction for an agency's information"""

    jmodel = get_object_or_404(Jurisdiction, slug=jurisdiction)
    agency = get_object_or_404(Agency, jurisdiction=jmodel, slug=slug, pk=idx)

    if request.method == 'POST':
        form = FlagForm(request.POST)
        if form.is_valid():
            send_mail('[FLAG] Agency: %s' % agency.name,
                      render_to_string('agency/flag.txt',
                                       {'agency': agency, 'user': request.user,
                                        'reason': form.cleaned_data.get('reason')}),
                      'info@muckrock.com', ['requests@muckrock.com'], fail_silently=False)
            messages.info(request, 'Agency correction succesfully submitted')
            return redirect(agency)
    else:
        form = FlagForm()
    return render_to_response('agency/agency_flag.html', {'form': form, 'agency': agency},
                              context_instance=RequestContext(request))
