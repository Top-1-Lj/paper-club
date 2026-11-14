from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

app_name = "club"
urlpatterns = [
    path("", views.paper_list, name="paper_list"),
    path("accounts/register/", views.register, name="register"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("papers/new/", views.paper_create, name="paper_create"),
    path("papers/<int:pk>/", views.paper_detail, name="paper_detail"),
    path("papers/<int:pk>/edit/", views.paper_update, name="paper_update"),
    path("papers/<int:pk>/delete/", views.paper_delete, name="paper_delete"),
    path("papers/<int:pk>/bibtex/", views.paper_bibtex_export, name="paper_bibtex"),
    path("papers/<int:paper_pk>/cards/new/", views.card_create, name="card_create"),
    path("papers/<int:paper_pk>/progress/", views.progress_update, name="progress_update"),
    path("cards/mine/", views.my_cards, name="my_cards"),
    path("cards/<int:pk>/", views.card_detail, name="card_detail"),
    path("cards/<int:pk>/edit/", views.card_update, name="card_update"),
    path("cards/<int:pk>/delete/", views.card_delete, name="card_delete"),
    path("cards/<int:pk>/markdown/", views.card_markdown_export, name="card_markdown"),
    path("cards/<int:card_pk>/comments/", views.comment_create, name="comment_create"),
    path("comments/<int:pk>/edit/", views.comment_update, name="comment_update"),
    path("comments/<int:pk>/delete/", views.comment_delete, name="comment_delete"),
]
