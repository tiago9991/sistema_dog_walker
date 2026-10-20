"""Dog CRUD views, nested under their client (PRD RF-003).

Routes are always ``/clients/<client_pk>/dogs/...`` and every dog lookup is
scoped by ``client_pk``, so accessing a dog that belongs to another client
by changing IDs returns 404 (RF-003 acceptance criterion).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, UpdateView

from clients.models import Client
from dogs.forms import DogForm
from dogs.models import Dog


def _get_client(client_pk):
    return get_object_or_404(Client, pk=client_pk)


def _scoped_queryset(client_pk):
    """Dogs of this client only — cross-scope access becomes a 404."""
    return Dog.objects.select_related('client').filter(client__pk=client_pk)


class DogCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'dogs.add_dog'
    form_class = DogForm
    template_name = 'dogs/dog_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.client = _get_client(self.kwargs['client_pk'])
        # Deactivated clients must not appear as operational options
        # (PRD RF-002 acceptance criterion).
        if request.user.is_authenticated and not self.client.is_active:
            messages.error(
                request,
                'Não é possível adicionar cachorros a um cliente desativado.',
            )
            return redirect('clients:detail', pk=self.client.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.client = self.client
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            'dogs:detail',
            kwargs={'client_pk': self.client.pk, 'pk': self.object.pk},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = self.client
        return context


class DogDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = 'dogs.view_dog'
    context_object_name = 'dog'
    template_name = 'dogs/dog_detail.html'

    def get_queryset(self):
        return _scoped_queryset(self.kwargs['client_pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = self.object.client
        # Schedules (Sprint 6) and recent walk history (Sprint 8).
        context['schedules'] = self.object.schedules.all()
        context['dog_walks'] = (
            self.object.walks.select_related('dog', 'dog__client')
            .order_by('-date', '-dog__name')[:10]
        )
        return context


class DogUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'dogs.change_dog'
    form_class = DogForm
    context_object_name = 'dog'
    template_name = 'dogs/dog_form.html'

    def get_queryset(self):
        return _scoped_queryset(self.kwargs['client_pk'])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['client'] = self.object.client
        return context

    def get_success_url(self):
        return reverse(
            'dogs:detail',
            kwargs={'client_pk': self.object.client.pk, 'pk': self.object.pk},
        )


def _set_active(request, client_pk, pk, *, active, message):
    dog = get_object_or_404(_scoped_queryset(client_pk), pk=pk)
    with transaction.atomic():
        dog.is_active = active
        dog.deactivated_at = None if active else timezone.now()
        dog.save(update_fields=('is_active', 'deactivated_at', 'updated_at'))
    messages.success(request, message)
    return redirect('dogs:detail', client_pk=dog.client.pk, pk=dog.pk)


@require_POST
@login_required
@permission_required('dogs.change_dog', raise_exception=True)
def dog_deactivate(request, client_pk, pk):
    """Deactivate preserving history (RF-003: ``desativar cachorro``)."""
    return _set_active(
        request,
        client_pk,
        pk,
        active=False,
        message='Cachorro desativado. O histórico foi preservado.',
    )


@require_POST
@login_required
@permission_required('dogs.change_dog', raise_exception=True)
def dog_activate(request, client_pk, pk):
    """Inverse of deactivation (mistakes must be reversible)."""
    return _set_active(request, client_pk, pk, active=True, message='Cachorro reativado.')
