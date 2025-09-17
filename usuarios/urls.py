from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('usuarios/', views.usuarios_list_view, name='usuarios_list'),
    path('usuarios/delete/<int:user_id>/', views.delete_user_view, name='delete_user'),
    path('seguridad-accesos/', views.seguridad_accesos_view, name='seguridad_accesos'),
]