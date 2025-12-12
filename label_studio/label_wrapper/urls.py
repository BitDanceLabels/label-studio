from django.urls import path

from . import views

app_name = 'label_wrapper'

urlpatterns = [
    path('label/projects', views.LabelProjectsAPI.as_view(), name='label-projects'),
    path('label/tasks', views.LabelTasksAPI.as_view(), name='label-tasks'),
]
