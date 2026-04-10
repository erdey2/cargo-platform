from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.views import defaults as default_views

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from drf_spectacular.utils import extend_schema

# JWT
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView, TokenVerifyView

# dj-rest-auth
from dj_rest_auth.views import (
    LoginView, LogoutView, PasswordChangeView,
    PasswordResetView, PasswordResetConfirmView, UserDetailsView
)
from dj_rest_auth.registration.views import (
    RegisterView, ResendEmailVerificationView, VerifyEmailView
)

AUTH_TAG = ["Authentication"]

# JWT Views
TokenObtainPairView = extend_schema(
    tags=AUTH_TAG,
    summary="Login (JWT)",
    description="Get access and refresh tokens using email and password.",
)(TokenObtainPairView)

TokenRefreshView = extend_schema(
    tags=AUTH_TAG,
    summary="Refresh Token",
)(TokenRefreshView)

TokenVerifyView = extend_schema(
    tags=AUTH_TAG,
    summary="Verify Token",
)(TokenVerifyView)

# dj-rest-auth Views
LoginView = extend_schema(tags=AUTH_TAG)(LoginView)
LogoutView = extend_schema(tags=AUTH_TAG)(LogoutView)
RegisterView = extend_schema(tags=AUTH_TAG)(RegisterView)
UserDetailsView = extend_schema(tags=AUTH_TAG)(UserDetailsView)
PasswordChangeView = extend_schema(tags=AUTH_TAG)(PasswordChangeView)
PasswordResetView = extend_schema(tags=AUTH_TAG)(PasswordResetView)
PasswordResetConfirmView = extend_schema(tags=AUTH_TAG)(PasswordResetConfirmView)
ResendEmailVerificationView = extend_schema(tags=AUTH_TAG)(ResendEmailVerificationView)
VerifyEmailView = extend_schema(tags=AUTH_TAG)(VerifyEmailView)

# URL Patterns
urlpatterns = [
    # Admin
    path(settings.ADMIN_URL, admin.site.urls),

    # Redirect root → docs
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),

    # Core APIs
    path("api/users/", include("apps.users.api.urls")),
    path("api/admin/", include("apps.admin_api.api.urls")),
    path("api/", include("apps.shipments.api.urls")),
    path("api/", include("apps.vehicles.api.urls")),
    path("api/", include("apps.tracking.api.urls")),
    path("api/", include("apps.assignment.api.urls")),
    path("api/", include("apps.payments.api.urls")),
    path("api/matching/", include("apps.matching.api.urls")),

    # JWT Authentication
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),

    # dj-rest-auth
    path("api/auth/login/", LoginView.as_view(), name="rest_login"),
    path("api/auth/logout/", LogoutView.as_view(), name="rest_logout"),
    path("api/auth/user/", UserDetailsView.as_view(), name="user_details"),

    path("api/auth/password/change/", PasswordChangeView.as_view()),
    path("api/auth/password/reset/", PasswordResetView.as_view()),
    path("api/auth/password/reset/confirm/", PasswordResetConfirmView.as_view()),

    path("api/auth/registration/", RegisterView.as_view(), name="rest_register"),
    path("api/auth/registration/verify-email/", VerifyEmailView.as_view()),
    path("api/auth/registration/resend-email/", ResendEmailVerificationView.as_view()),

    # API Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Media
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Debug
if settings.DEBUG:
    urlpatterns += [
        path("400/", default_views.bad_request, kwargs={"exception": Exception("Bad Request!")}),
        path("403/", default_views.permission_denied, kwargs={"exception": Exception("Permission Denied")}),
        path("404/", default_views.page_not_found, kwargs={"exception": Exception("Page not Found")}),
        path("500/", default_views.server_error),
    ]

    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]