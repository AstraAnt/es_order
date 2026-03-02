from django.contrib.auth import logout
from django.contrib.auth.views import LoginView

from django.http import HttpResponseRedirect
from django.urls import reverse



class UserLoginView(LoginView):
    template_name = "users/login.html"


    def get_success_url(self):
        """
        Django ожидает строку (URL) — возвращаем URL, полученный от role_redirect_url.
        Не возвращаем HttpResponse.
        """
        from tsunff.utils.role_redirect import role_redirect_url
        return role_redirect_url(self.request.user)

def logout_user(request):
    logout(request)
    return HttpResponseRedirect(reverse('users:login'))


