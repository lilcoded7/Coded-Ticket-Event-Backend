from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.permissions import AllowAny
from drf_yasg.views import get_schema_view
from drf_yasg import openapi


schema_view = get_schema_view(
    openapi.Info(
        title="Event",
        default_version="v1",
        description="API documentation for Event",
        terms_of_service="",
        contact=openapi.Contact(email="info@superfixed.com"),
        license=openapi.License(name="Test License"),
    ),
    public=True,
    permission_classes=(AllowAny,),
)

urlpatterns = [
    path('env/', admin.site.urls),
    path('api/v1/ticket/', include('tiket.urls'))
]

if settings.DEBUG == True:
    urlpatterns_extra = [
        path(
            "doc",
            schema_view.with_ui("swagger", cache_timeout=0),
            name="schema-swagger-ui",
        ),
    ]
    urlpatterns += urlpatterns_extra

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)