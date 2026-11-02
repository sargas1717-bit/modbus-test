from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import UserCreateForm, UserUpdateForm
from .mixins import AdministratorRequiredMixin
from .models import User


class UserListView(AdministratorRequiredMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    ordering = ("username",)


class UserCreateView(AdministratorRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = "generic_form.html"
    success_url = reverse_lazy("accounts:user_list")
    extra_context = {"page_title": "Crear usuario"}

    def form_valid(self, form):
        messages.success(self.request, "Usuario creado correctamente.")
        return super().form_valid(form)


class UserUpdateView(AdministratorRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = "generic_form.html"
    success_url = reverse_lazy("accounts:user_list")
    extra_context = {"page_title": "Editar usuario"}

    def form_valid(self, form):
        messages.success(self.request, "Usuario actualizado correctamente.")
        return super().form_valid(form)


class UserDeleteView(AdministratorRequiredMixin, DeleteView):
    model = User
    template_name = "generic_confirm_delete.html"
    success_url = reverse_lazy("accounts:user_list")
    extra_context = {"page_title": "Eliminar usuario"}

    def form_valid(self, form):
        messages.success(self.request, "Usuario eliminado correctamente.")
        return super().form_valid(form)
