from fastapi import APIRouter, Request, Response, status

from app.api.auth_deps import (
    AuthContextDep,
    AuthServiceDep,
    ClientIp,
    OptionalAuthDep,
    SettingsDep,
)
from app.api.cookies import clear_session_cookie, set_session_cookie
from app.core.security import csrf_token_for
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    EmailOnlyRequest,
    GoogleLoginRequest,
    LoginRequest,
    MessageResponse,
    NonceResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenRequest,
    UpdateProfileRequest,
    UserRead,
)
from app.services.auth import GENERIC_EMAIL_MESSAGE, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _signed_in(
    response: Response,
    service: AuthService,
    settings: SettingsDep,
    user: User,
    token: str,
    *,
    is_new_user: bool = False,
) -> AuthResponse:
    set_session_cookie(response, token, settings)
    return AuthResponse(
        user=service.profile(user),
        csrf_token=csrf_token_for(token, settings.secret_key),
        is_new_user=is_new_user,
    )


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, service: AuthServiceDep, ip: ClientIp) -> MessageResponse:
    """Create an account and email a verification link. You cannot sign in until it is used."""
    service.register(data, ip)
    return MessageResponse(
        message="Account created. Check your email for a link to verify your address."
    )


@router.post("/login", response_model=AuthResponse)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    ip: ClientIp,
) -> AuthResponse:
    user, token = service.login(data, ip, request.headers.get("user-agent"))
    return _signed_in(response, service, settings, user, token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response, service: AuthServiceDep, settings: SettingsDep, auth: OptionalAuthDep
) -> Response:
    if auth is not None:
        service.logout(auth.session.id)
    clear_session_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
def logout_all(
    response: Response, service: AuthServiceDep, settings: SettingsDep, auth: AuthContextDep
) -> Response:
    service.logout_everywhere(auth.user)
    clear_session_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=AuthResponse)
def me(service: AuthServiceDep, auth: AuthContextDep) -> AuthResponse:
    """Who is signed in. The frontend calls this on load to restore its state."""
    return AuthResponse(user=service.profile(auth.user), csrf_token=auth.csrf_token)


@router.patch("/me", response_model=UserRead)
def update_me(
    data: UpdateProfileRequest, service: AuthServiceDep, auth: AuthContextDep
) -> UserRead:
    return service.profile(service.update_profile(auth.user, data))


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    data: ChangePasswordRequest, service: AuthServiceDep, auth: AuthContextDep
) -> MessageResponse:
    """Signs you out everywhere else."""
    service.change_password(auth.user, data, auth.session.id)
    return MessageResponse(message="Password changed. Other devices have been signed out.")


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(data: TokenRequest, service: AuthServiceDep, ip: ClientIp) -> MessageResponse:
    service.verify_email(data.token, ip)
    return MessageResponse(message="Your email address is verified. You can sign in now.")


@router.post(
    "/resend-verification", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
def resend_verification(
    data: EmailOnlyRequest, service: AuthServiceDep, ip: ClientIp
) -> MessageResponse:
    """Always answers the same way, so it cannot be used to discover registered emails."""
    service.resend_verification(data.email, ip)
    return MessageResponse(message=GENERIC_EMAIL_MESSAGE)


@router.post(
    "/forgot-password", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED
)
def forgot_password(
    data: EmailOnlyRequest, service: AuthServiceDep, ip: ClientIp
) -> MessageResponse:
    """Always answers the same way, so it cannot be used to discover registered emails."""
    service.forgot_password(data.email, ip)
    return MessageResponse(message=GENERIC_EMAIL_MESSAGE)


@router.post("/reset-password/check", response_model=MessageResponse)
def check_reset_link(data: TokenRequest, service: AuthServiceDep, ip: ClientIp) -> MessageResponse:
    """Lets the reset page warn about a used or expired link before the user types a password."""
    service.check_reset_token(data.token, ip)
    return MessageResponse(message="This link is valid.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    data: ResetPasswordRequest, service: AuthServiceDep, ip: ClientIp
) -> MessageResponse:
    service.reset_password(data.token, data.password, ip)
    return MessageResponse(message="Password updated. Please sign in with your new password.")


@router.get("/google/nonce", response_model=NonceResponse)
def google_nonce(service: AuthServiceDep) -> NonceResponse:
    """A short-lived, signed value the Google button includes in the ID token it requests."""
    return NonceResponse(nonce=service.new_google_nonce())


@router.post("/google", response_model=AuthResponse)
def google_login(
    data: GoogleLoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
    ip: ClientIp,
) -> AuthResponse:
    """Sign in or sign up with a Google ID token. The token is verified here, never trusted."""
    user, token, is_new = service.google_login(
        data.credential, data.nonce, ip, request.headers.get("user-agent")
    )
    return _signed_in(response, service, settings, user, token, is_new_user=is_new)
