from django.contrib import admin
from django.urls import path
from django.contrib.auth import views
from django.conf.urls import include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', views.LoginView.as_view(template_name="registration/login.html"), name='login', kwargs={'next_page': 'altruist/'}),
    path('logout/', views.LogoutView.as_view(template_name="registration/logout.html"), name='logout', kwargs={'next_page': '/'}),

    # path('accounts/', include('django.contrib.auth.urls'), kwargs={'next_page': '/altruists/'}),
    # path('user/', MyProfileView.as_view(), name='user-profile'),

    # path('accounts/update/<int:pk>/', views.UpdateProfile.as_view(), name='update_user'),
    # path(
    #     'change-password/',
    #     auth_views.PasswordChangeView.as_view(
    #         template_name='commons/change-password.html',
    #         success_url = '/'
    #     ),
    #     name='change_password'
    # ),

    path('', include('manager.urls', namespace='manager')),
]
