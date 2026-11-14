from django.contrib import admin
from django.urls import include, path

urlpatterns = [path("admin/", admin.site.urls), path("", include("club.urls"))]
admin.site.site_header = "纸间 · 管理后台"
admin.site.site_title = "Paper Club"
