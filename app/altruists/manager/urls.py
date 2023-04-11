from django.contrib import admin
from django.urls import path
from . import views
from manager.views import ChainListView, ChainCreate, ChainUpdate, ChainDelete,\
                          AltruistListView, AltruistCreate, AltruistUpdate,\
                          AltruistDelete, AltruistRunTest, BillingReport, MyProfileView
from django.views.generic.base import RedirectView
from django.conf.urls import include
from django.contrib.auth import views as auth_views
from datetime import date

app_name = 'manager'

urlpatterns = [
    path('user/', MyProfileView.as_view(), name='user-profile'),
    path('user/passwd', auth_views.PasswordChangeView.as_view(
                                    template_name="registration/passwd_change.html",
                                    success_url = '/'), name='user-passwd'),

#### Chain
    path('chain/', ChainListView.as_view(), name='chain-list'),
    path('chain/<int:pk>/', ChainUpdate.as_view(), name='chain-update'),
    path('chain/add/', ChainCreate.as_view(), name='chain-add'),
    path('chain/<int:pk>/delete/', ChainDelete.as_view(), name='chain-delete'),
#### Altruist
    path('altruist/', AltruistListView.as_view(template_name="manager/altruist_list.html"), name='altruist-list'),
    path('altruist/chain/<int:pk>/', AltruistListView.as_view(template_name="manager/altruist_list.html"), name='altruist-by-chain'),
    path('altruist/<int:pk>/', AltruistUpdate.as_view(), name='altruist-update'),
    path('altruist/add/', AltruistCreate.as_view(), name='altruist-add'),
    path('altruist/view/<int:pk>/<int:page>/', views.AltruistDetail, name='altruist-detail'),
    path('altruist/<int:pk>/delete/', AltruistDelete.as_view(), name='altruist-delete'),
    path('altruist/test/<int:pk>/', views.AltruistRunTest, name='altruist-runtest'),
    path('altruist/billing/<str:start_date>/<str:finish_date>', BillingReport.as_view(template_name="manager/billing.html"), name='altruist-billing'),
#### Home
    path('', RedirectView.as_view(url='altruist/', permanent=False), name='home'),
# ===== API endpoints ======
]
