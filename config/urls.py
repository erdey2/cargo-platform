from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.views import defaults as default_views
from drf_spectacular.views import (SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,)
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView
from dj_rest_auth.registration.views import RegisterView, ResendEmailVerificationView, VerifyEmailView
from dj_rest_auth.views import LoginView, LogoutView, PasswordChangeView, PasswordResetView, PasswordResetConfirmView, UserDetailsView
from rest_framework.authtoken.views import ObtainAuthToken

# JWT auth views
TokenObtainPairView = extend_schema(
    tags=["Authentication & Users"],
    summary="Obtain JWT token pair",
    description="Returns an access and refresh token for valid user credentials."
)(TokenObtainPairView)

TokenRefreshView = extend_schema(
    tags=["Authentication & Users"],
    summary="Refresh JWT access token",
    description="Use a refresh token to obtain a new access token."
)(TokenRefreshView)

TokenVerifyView = extend_schema(
    tags=["Authentication & Users"],
    summary="Verify JWT token",
    description="Check if a token is valid and not expired."
)(TokenVerifyView)

# Authentication & Users group
RegisterView = extend_schema(tags=["Authentication & Users"])(RegisterView)
ResendEmailVerificationView = extend_schema(tags=["Authentication & Users"])(ResendEmailVerificationView)
VerifyEmailView = extend_schema(tags=["Authentication & Users"])(VerifyEmailView)
LoginView = extend_schema(tags=["Authentication & Users"])(LoginView)
LogoutView = extend_schema(tags=["Authentication & Users"])(LogoutView)
PasswordChangeView = extend_schema(tags=["Authentication & Users"])(PasswordChangeView)
PasswordResetView = extend_schema(tags=["Authentication & Users"])(PasswordResetView)
PasswordResetConfirmView = extend_schema(tags=["Authentication & Users"])(PasswordResetConfirmView)

# Explicit token and user views
TokenView = extend_schema(tags=["Authentication & Users"])(ObtainAuthToken)
UserDetailsView = extend_schema(tags=["Authentication & Users"])(UserDetailsView)

urlpatterns = [
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),

    path('', RedirectView.as_view(url='/api/docs/', permanent=False)),
    # User management
    path('api/accounts/', include("allauth.urls")),

    # custom urls
    path('api/users/', include("apps.users.api.urls")),
    path("api/", include("apps.shipments.api.urls")),
    path("api/", include("apps.vehicles.api.urls")),
    path("api/", include("apps.tracking.api.urls")),
    path("api/", include("apps.assignment.api.urls")),

    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # advanced auth
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/auth/', include('django.contrib.auth.urls')),

    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    # path('api/otp-reset/', include('online_car_market.otp_reset.api.urls')),

    # Schema in raw OpenAPI format:
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Swagger UI:
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # Redoc UI:
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]

