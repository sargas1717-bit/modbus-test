from django.urls import path

from .views import UserCreateView, UserDeleteView, UserListView, UserUpdateView


app_name = "accounts"

urlpatterns = [
    path("users/", UserListView.as_view(), name="user_list"),
    path("users/create/", UserCreateView.as_view(), name="user_create"),
    path("users/<int:pk>/edit/", UserUpdateView.as_view(), name="user_update"),
    path("users/<int:pk>/delete/", UserDeleteView.as_view(), name="user_delete"),
]
