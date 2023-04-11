# from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy

from .models import Chain, Altruist, AltruistServingLog
from django.contrib.auth.models import User
# from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

# from .serializers import AltruistSerializer
# from rest_framework import viewsets
from django import forms
from django.http import Http404
from django.core.paginator import Paginator, EmptyPage
from django.contrib.auth.mixins import UserPassesTestMixin

from django.db.models import Count, Sum, Value, Case, When,F, ExpressionWrapper, DurationField
from django.db.models.functions import Extract, ExtractSecond

from django.utils import timezone
from django.conf import settings

import datetime
import logging
logger = logging.getLogger(__name__)

@method_decorator(login_required, name='dispatch')
class MyProfileView(UpdateView):
    model = User
    fields = ['first_name', 'last_name', 'email']

    success_url = reverse_lazy('manager:altruist-list')

    def get_object(self):
        return self.request.user
#============== CRUD Chain ====================

@method_decorator(login_required, name='dispatch')
class ChainListView(ListView):
    model = Chain
    fields = ['chain_id', 'chain_name',]

    def get_template_names(self, *args, **kwargs):
        if self.request.user.is_superuser:
            return ["manager/chain_list_with_altruists.html"]
        else:
            return ["manager/chain_list.html"]

    def get_queryset(self):
        return Chain.objects.all()\
                .annotate(num_altruists=Count('altruist'))\
                .annotate(cc_altruist=Sum(Case(
                    When(altruist__url__icontains=settings.GLOBAL_SETTINGS["CC_DOMAIN"], then=Value(1)),
                    default=Value(0)), default=Value(0)))

@method_decorator(login_required, name='dispatch')
class ChainUpdate(UpdateView):
    model = Chain
    fields = ['chain_id', 'chain_name',]
    success_url = reverse_lazy('manager:chain-list')

    def get(self, request, *args, **kwargs):
        try:
            object = self.get_object()
            if self.request.user.is_superuser:
                return super().get(request, *args, **kwargs)

            logger.warning(f"Requested altruist owned by another user.")
        except Exception as e:
            logger.error(f"Exception: {e}")

        return redirect('manager:chain-list')

@method_decorator(login_required, name='dispatch')
class ChainCreate(CreateView):
    model = Chain
    fields = ['chain_id', 'chain_name',]

    def get(self, request, *args, **kwargs):
        try:
            if self.request.user.is_superuser:
                return super().get(request, *args, **kwargs)

            logger.warning(f"Not admin users cannot add new chains")
        except Exception as e:
            logger.error(f"Exception: {e}")

        return redirect('manager:home')

@method_decorator(login_required, name='dispatch')
class ChainDelete(DeleteView):
    model = Chain
    success_url = reverse_lazy('manager:chain-list')

#============== CRUD Altruist ====================
@method_decorator(login_required, name='dispatch')
class AltruistUpdate(UpdateView):
    model = Altruist
    success_url = reverse_lazy('manager:altruist-list')
    fields = ['url', 'chain_id', 'enabled', 'owner']

    def get_form(self, form_class=None):
        form = super().get_form(form_class=form_class)
        # Only superusers can edit owner
        if not self.request.user.is_superuser:
            form.fields['owner'].widget = forms.HiddenInput()
        return form

    def get(self, request, *args, **kwargs):
        try:
            object = self.get_object()
            if self.request.user == object.owner or (self.request.user.is_superuser and object.owner.is_superuser):
                return super().get(request, *args, **kwargs)

            logger.warning(f"Requested altruist owned by another user.")
        except Exception as e:
            logger.error(f"Exception: {e}")

        return redirect('manager:home')

@method_decorator(login_required, name='dispatch')
class AltruistCreate(CreateView):
    model = Altruist
    fields = ['url', 'chain_id']
    success_url = reverse_lazy('manager:altruist-list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super(AltruistCreate, self).form_valid(form)


@method_decorator(login_required, name='dispatch')
class AltruistDelete(DeleteView):
    model = Altruist
    success_url = reverse_lazy('manager:altruist-list')

@login_required
def AltruistDetail(request, pk, page=1):
    """

    """
    altruist = get_object_or_404(Altruist, id = pk)

    logs = AltruistServingLog.objects.filter(altruist = altruist).order_by('-start_time')
    total_logs = len(logs)
    paginator = Paginator(logs, 50)
    try:
        logs = paginator.page(page)
    except EmptyPage:
        # if we exceed the page limit we return the last page 
        logs = paginator.page(paginator.num_pages)

    return render(request, 'manager/altruist_detail.html', {'altruist': altruist, 'logs': logs, 'total_logs': total_logs})

@login_required
def AltruistRunTest(request, pk):
    """
    This Django view function retrieves a specific Altruist instance and
    sends an HTTP GET request to a BlackBoxExporter, passing the Altruist's chain ID and URL as parameters. 
    It then renders a template named "altruist_runtest.html" and passes the "altruist" instance and the HTTP response as context variables.
    """
    altruist = get_object_or_404(Altruist, id = pk)

    # Get metrics
    nodes_response = dict()
    import requests, os
    try:
        # Black Box Exporter address
        BB_EXPORTER_ADDRESS = os.environ.get('BB_EXPORTER_ADDRESS')
        q_url = requests.utils.quote(altruist.url)
        resp = requests.get(f"http://{BB_EXPORTER_ADDRESS}/probe?chainid={altruist.chain_id.chain_id}&target={q_url}",
                                headers = {"Content-Type": "text/plain"},
                                timeout=(5,35))

        nodes_response["content"] = resp.text
        nodes_response["status_code"] = resp.status_code

    except Exception as e:
        nodes_response["exception"] = str(e)
        logging.warning(f"Failed to request: {e}")

    return render(request, 'manager/altruist_runtest.html', {'altruist': altruist, 'nodes_response': nodes_response})


@method_decorator(login_required, name='dispatch')
class AltruistListView(ListView):
    model = Altruist
    fields = ['owner' ,'url', 'chain_id', 'enabled']

    def get_queryset(self):
        now_minus_1h = timezone.now() - datetime.timedelta(hours=1)

        if self.request.user.is_superuser:
            qs = Altruist.objects.all()
        else:
            qs = Altruist.objects.filter(owner = self.request.user)

        if self.kwargs.get('pk'):
            qs = qs.filter(chain_id = self.kwargs.get('pk'))

        return qs.select_related()\
                    .annotate(last_hour_sessions_number=Sum(Case(\
                        When(altruistservinglog__start_time__gte=now_minus_1h, then=Value(1))\
                        ,When(altruistservinglog__start_time__lt=now_minus_1h, then=Value(0)) ), default=Value(0)))\
                    .order_by('chain_id')

@method_decorator(login_required, name='dispatch')
class BillingReport(TemplateView):
    """
    Calculates the total duration for all Altruists and renders a template named "duration.html".
    It also calculates the relative percentage of each Altruist per chain ID and allows for sorting and filtering of the results using the jQuery library.
    """
    # template_name = 'manager/duration.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        if self.request.user.is_superuser:
            alts = Altruist.objects.all()
        else:
            alts = Altruist.objects.filter(owner = self.request.user)

        # Get the start and end date Use 01 of the current months if not given
        start_date = datetime.datetime.strptime(self.kwargs.get('start_date'), '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())\
                        if self.kwargs.get('start_date') \
                        else timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        finish_date = datetime.datetime.strptime(self.kwargs.get('finish_date'), '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())\
                        if self.kwargs.get('finish_date') \
                        else timezone.now()

        used_chains = []
        total_by_altruist = []
        for a in alts:
            qs = AltruistServingLog.objects.filter(altruist=a, start_time__range=(start_date, finish_date))\
                .annotate(
                    duration_time=ExpressionWrapper(F("finish_time") - F("start_time"), output_field=DurationField()),
                    duration_sec=Extract(F("duration_time"), "epoch")
                )\
                .aggregate(total_duration = Sum('duration_sec'))

            total_by_altruist.append({
                                "url": a.url,
                                "chain": a.chain_id,
                                "owner": a.owner,
                                "total_duration": qs["total_duration"] if qs["total_duration"] else 0
                            })

            used_chains.append(a.chain_id.chain_id)

        total_by_chain = dict()
        for a in used_chains:
            qs = AltruistServingLog.objects.filter(chain_id=a, start_time__range=(start_date, finish_date))\
                .annotate(
                    duration_time=ExpressionWrapper(F("finish_time") - F("start_time"), output_field=DurationField()),
                    duration_sec=Extract(F("duration_time"), "epoch")
                )\
                .aggregate(total_duration = Sum('duration_sec'))

            total_by_chain[a] = qs["total_duration"] if qs["total_duration"] else 0

        chains_with_counts = Chain.objects.filter(chain_id__in=used_chains)\
                .annotate(num_altruists=Count('altruist'))\
                .annotate(cc_altruist=Sum(Case(
                    When(altruist__url__icontains=settings.GLOBAL_SETTINGS["CC_DOMAIN"], then=Value(1)),
                    default=Value(0)), default=Value(0)))
                #     \
                # .annotate(cc_altruists=Sum('is_cc_altruist'))

        # print(chains_with_counts)

        for a in total_by_altruist:
            total_by_chain[ a["chain"].chain_id ]
            if total_by_chain[ a["chain"].chain_id ] != 0:
                a["total_ratio"] = 100 * a["total_duration"] / total_by_chain[ a["chain"].chain_id ]
            else:
                a["total_ratio"] = None

            a["total_altruists"] = chains_with_counts.get(chain_id=a["chain"].chain_id).num_altruists
            a["cc_altruist"] = chains_with_counts.get(chain_id=a["chain"].chain_id).cc_altruist

        context["total_by_altruist"] = total_by_altruist
        context["start_date"]        = start_date
        context["finish_date"]       = finish_date

        return context

# ================= API ======================

# class apiAltruistListViewEnabled(viewsets.ModelViewSet):
#     authentication_classes = [authentication.TokenAuthentication]
#     permission_classes = [permissions.IsAdminUser]

#     queryset = Altruist.objects.filter(enabled = True)
#     serializer_class = AltruistSerializer

#     def get(self, request, format=None):
#         """
#         Return a list of all altruists.
#         """
#         return Response(queryset)

