from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('name/', views.choose_name_view, name='choose_name'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('predict/', views.prediction_view, name='prediction'),
    path('admin-panel/', views.admin_dashboard_view, name='admin_dashboard'),
    path('results/', views.results_view, name='results'),
]
