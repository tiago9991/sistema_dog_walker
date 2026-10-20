"""Client CRUD views (PRD RF-002).

Every view enforces authentication and backend permissions (PRD sections
4.3 and RF-001) — the interface may hide actions, but never replaces
authorization here.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from clients.forms import ClientForm
from clients.models import Client


class ClientListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List + search (RF-002: ``listar clientes`` / ``pesquisar clientes``)."""

    permission_required = 'clients.view_client'
    context_object_name = 'clients'
    paginate_by = 20
    template_name = 'clients/client_list.html'

    def get_queryset(self):
        queryset = Client.objects.annotate(dog_count=Count('dogs')).order_by('name')

        query = self.request.GET.get('q', '').strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(phone__icontains=query) | Q(email__icontains=query)
            )

        status = self.request.GET.get('status', '')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'inactive':
            queryset = queryset.filter(is_active=False)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        context['querystring'] = params.urlencode()
        context['query'] = self.request.GET.get('q', '').strip()
        context['status'] = self.request.GET.get('status', '')
        return context


class ClientDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Client data + associated dogs (RF-002: ``acessar os cachorros associados``)."""

    permission_required = 'clients.view_client'
    context_object_name = 'client'
    template_name = 'clients/client_detail.html'

    def get_queryset(self):
        return Client.objects.prefetch_related('dogs')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dogs'] = self.object.dogs.all()
        return context


class ClientCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'clients.add_client'
    form_class = ClientForm
    template_name = 'clients/client_form.html'

    def get_success_url(self):
        return reverse('clients:detail', kwargs={'pk': self.object.pk})


class ClientUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'clients.change_client'
    form_class = ClientForm
    context_object_name = 'client'
    template_name = 'clients/client_form.html'

    def get_queryset(self):
        return Client.objects.all()

    def get_success_url(self):
        return reverse('clients:detail', kwargs={'pk': self.object.pk})


def _set_active(request, pk, *, active, message):
    """Toggle soft deactivation inside a transaction (PRD sections 10, RF-002)."""
    client = get_object_or_404(Client, pk=pk)
    with transaction.atomic():
        client.is_active = active
        client.deactivated_at = None if active else timezone.now()
        client.save(update_fields=('is_active', 'deactivated_at', 'updated_at'))
    messages.success(request, message)
    return redirect('clients:detail', pk=client.pk)


@require_POST
@login_required
@permission_required('clients.change_client', raise_exception=True)
def client_deactivate(request, pk):
    """Deactivate preserving history (RF-002: ``desativar cliente``)."""
    return _set_active(
        request, pk, active=False, message='Cliente desativado. Os dados históricos foram preservados.'
    )


@require_POST
@login_required
@permission_required('clients.change_client', raise_exception=True)
def client_activate(request, pk):
    """Inverse of deactivation (mistakes must be reversible)."""
    return _set_active(request, pk, active=True, message='Cliente reativado.')
