"""Scheduling CRUD views, nested under their dog (PRD RF-004).

Every change to a schedule resynchronizes the dog's future ``previsto``
walks (see ``walks.services``); history is never destroyed.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, UpdateView

from dogs.models import Dog
from scheduling.forms import ScheduleForm
from scheduling.models import WalkSchedule
from walks.services import resync_dog_walks


def _get_dog(client_pk, dog_pk):
    return get_object_or_404(
        Dog.objects.select_related('client'), pk=dog_pk, client__pk=client_pk
    )


def _get_schedule(client_pk, dog_pk, pk):
    return get_object_or_404(
        WalkSchedule.objects.select_related('dog', 'dog__client'),
        pk=pk,
        dog__pk=dog_pk,
        dog__client__pk=client_pk,
    )


class ScheduleCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'scheduling.add_walkschedule'
    form_class = ScheduleForm
    template_name = 'scheduling/schedule_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.dog = _get_dog(self.kwargs['client_pk'], self.kwargs['dog_pk'])
        # Deactivated dogs/clients are not operational options (RF-002/003).
        if request.user.is_authenticated and (
            not self.dog.is_active or not self.dog.client.is_active
        ):
            messages.error(
                request,
                'Não é possível criar programações para um cachorro ou cliente desativado.',
            )
            return redirect('clients:detail', pk=self.dog.client.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Bind the dog before validation so Model.clean() can check overlaps
        # against the dog's other active schedules.
        kwargs['instance'] = WalkSchedule(dog=self.dog)
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        resync_dog_walks(self.dog)
        messages.success(
            request=self.request,
            message='Programação criada. Os passeios previstos foram gerados.',
        )
        return response

    def get_success_url(self):
        return reverse(
            'clients:detail', kwargs={'pk': self.kwargs['client_pk']}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dog'] = self.dog
        context['client'] = self.dog.client
        return context


class ScheduleUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'scheduling.change_walkschedule'
    form_class = ScheduleForm
    context_object_name = 'schedule'
    template_name = 'scheduling/schedule_form.html'

    def get_queryset(self):
        return WalkSchedule.objects.filter(
            dog__pk=self.kwargs['dog_pk'], dog__client__pk=self.kwargs['client_pk']
        ).select_related('dog', 'dog__client')

    def form_valid(self, form):
        response = super().form_valid(form)
        resync_dog_walks(self.object.dog)
        messages.success(
            request=self.request,
            message='Programação atualizada. Os passeios previstos foram regerados.',
        )
        return response

    def get_success_url(self):
        return reverse(
            'clients:detail', kwargs={'pk': self.kwargs['client_pk']}
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dog'] = self.object.dog
        context['client'] = self.object.dog.client
        return context


def _set_active(request, client_pk, dog_pk, pk, *, active, message):
    schedule = _get_schedule(client_pk, dog_pk, pk)
    with transaction.atomic():
        schedule.is_active = active
        schedule.deactivated_at = None if active else timezone.now()
        schedule.save(
            update_fields=('is_active', 'deactivated_at', 'updated_at')
        )
    resync_dog_walks(schedule.dog)
    messages.success(request, message)
    return redirect('clients:detail', pk=client_pk)


@require_POST
@login_required
@permission_required('scheduling.change_walkschedule', raise_exception=True)
def schedule_deactivate(request, client_pk, dog_pk, pk):
    return _set_active(
        request,
        client_pk,
        dog_pk,
        pk,
        active=False,
        message='Programação desativada. Os passeios previstos futuros desta programação foram removidos.',
    )


@require_POST
@login_required
@permission_required('scheduling.change_walkschedule', raise_exception=True)
def schedule_activate(request, client_pk, dog_pk, pk):
    return _set_active(
        request,
        client_pk,
        dog_pk,
        pk,
        active=True,
        message='Programação reativada. Os passeios previstos foram gerados.',
    )
