from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class AdministratorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.has_admin_access
