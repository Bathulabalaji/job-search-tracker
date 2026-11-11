import logging
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import AuthError
from app.core.security import (
    generate_token,
    hash_identifier,
    hash_password,
    hash_token,
    make_signed_nonce,
    password_needs_rehash,
    password_problems,
    verify_password,
    verify_signed_nonce,
)
from app.emails.mailer import AuthMailer
from app.models.auth import AuthIdentity, AuthToken
from app.models.enums import AuthProvider, AuthTokenPurpose, UserStatus
from app.models.user import User
from app.repositories.user import (
    AuthIdentityRepository,
    AuthTokenRepository,
    UserRepository,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UpdateProfileRequest,
    UserRead,
)
from app.services.google_auth import GoogleAuthError, GoogleTokenVerifier
from app.services.legacy import claim_legacy_data
from app.services.rate_limit import RateLimiter
from app.services.sessions import SessionService

logger = logging.getLogger("app.auth")

HOUR = timedelta(hours=1)
FIFTEEN_MIN = timedelta(minutes=15)
NONCE_MAX_AGE_SECONDS = 600

# Attempt limits. Failures are what count for sign-in; every request counts elsewhere.
LOGIN_FAILURES_PER_EMAIL = 5
LOGIN_FAILURES_PER_IP = 20
REGISTER_PER_IP = 5
EMAIL_REQUESTS_PER_ADDRESS = 3  # resend-verification and forgot-password, per hour
EMAIL_REQUESTS_PER_IP = 10
TOKEN_ATTEMPTS_PER_IP = 30
GOOGLE_ATTEMPTS_PER_IP = 30
CHANGE_PASSWORD_FAILURES = 5

GENERIC_EMAIL_MESSAGE = "If an account exists for that email, we have sent instructions to it."


class AuthService:
    def __init__(
        self,
        session: Session,
        clock: Clock,
        settings: Settings,
        mailer: AuthMailer,
        google: GoogleTokenVerifier,
    ) -> None:
        self.session = session
        self.clock = clock
        self.settings = settings
        self.mailer = mailer
        self.google = google
        self.users = UserRepository(session)
        self.identities = AuthIdentityRepository(session)
        self.tokens = AuthTokenRepository(session)
        self.sessions = SessionService(session, clock, settings)
        self.limiter = RateLimiter(session, clock)

    # ---- registration ------------------------------------------------------------------------

    def register(self, data: RegisterRequest, ip: str) -> None:
        self.limiter.consume(f"register:ip:{ip}", REGISTER_PER_IP, HOUR)
        self.session.commit()  # keep the attempt count even if we reject below

        problems = password_problems(data.password, email=data.email, full_name=data.full_name)
        if problems:
            raise AuthError("weak_password", " ".join(problems), 422)
        if self.users.get_by_email(data.email) is not None:
            raise AuthError("email_taken", "An account with this email already exists.", 409)

        now = self.clock.now()
        user = User(
            email=data.email,
            full_name=data.full_name,
            password_hash=hash_password(data.password),
            status=UserStatus.active,
            terms_accepted_at=now,
            password_changed_at=now,
        )
        try:
            self.users.add(user)
        except IntegrityError as exc:  # two requests registered the same email at once
            self.session.rollback()
            raise AuthError(
                "email_taken", "An account with this email already exists.", 409
            ) from exc

        if self.settings.auto_verify_email:
            self._mark_verified(user)
        else:
            self._issue_verification(user)
        self.session.commit()
        logger.info("auth.register", extra={"user_id": user.id, "ip": ip})

    # ---- sign in / out -----------------------------------------------------------------------

    def login(self, data: LoginRequest, ip: str, user_agent: str | None) -> tuple[User, str]:
        email_bucket = f"login:email:{hash_identifier(data.email)}"
        ip_bucket = f"login:ip:{ip}"
        self.limiter.check(email_bucket, LOGIN_FAILURES_PER_EMAIL, FIFTEEN_MIN)
        self.limiter.check(ip_bucket, LOGIN_FAILURES_PER_IP, FIFTEEN_MIN)

        user = self.users.get_by_email(data.email)
        # Always runs a full hash verification, so unknown emails cost the same time as wrong
        # passwords and cannot be told apart by timing.
        password_ok = verify_password(data.password, user.password_hash if user else None)
        if user is None or not password_ok:
            self.limiter.record(email_bucket)
            self.limiter.record(ip_bucket)
            self.session.commit()
            logger.warning(
                "auth.login.failed",
                extra={"email_hash": hash_identifier(data.email), "ip": ip},
            )
            raise AuthError("invalid_credentials", "Invalid email or password.", 401)

        # Only after the password is proven do we say anything about the account's state.
        if user.status != UserStatus.active:
            logger.warning("auth.login.suspended", extra={"user_id": user.id, "ip": ip})
            raise AuthError("account_suspended", "This account has been suspended.", 403)
        if not user.email_verified:
            raise AuthError(
                "email_not_verified",
                "Please verify your email address before signing in.",
                403,
            )

        if user.password_hash and password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(data.password)
        self.limiter.reset(email_bucket)
        token = self._start_session(user, user_agent)
        self.session.commit()
        logger.info("auth.login.success", extra={"user_id": user.id, "ip": ip})
        return user, token

    def logout(self, session_id: int) -> None:
        self.sessions.revoke(session_id)
        self.session.commit()

    def logout_everywhere(self, user: User) -> None:
        self.sessions.revoke_all(user.id)
        self.session.commit()

    # ---- email verification ------------------------------------------------------------------

    def verify_email(self, raw_token: str, ip: str) -> User:
        self.limiter.consume(f"verify:ip:{ip}", TOKEN_ATTEMPTS_PER_IP, HOUR)
        self.session.commit()

        record = self._load_token(raw_token, AuthTokenPurpose.verify_email)
        user = self.users.get(record.user_id)
        if user is None or not self.tokens.consume(record.id, self.clock.now()):
            raise AuthError("invalid_token", "This link is invalid or has expired.", 400)
        self._mark_verified(user)
        self.tokens.invalidate_for_user(user.id, AuthTokenPurpose.verify_email, self.clock.now())
        self.session.commit()
        logger.info("auth.email.verified", extra={"user_id": user.id})
        return user

    def resend_verification(self, email: str, ip: str) -> None:
        self._limit_email_requests("resend", email, ip)
        user = self.users.get_by_email(email)
        if user is not None and user.status == UserStatus.active and not user.email_verified:
            self._issue_verification(user)
        self.session.commit()

    # ---- password reset ----------------------------------------------------------------------

    def forgot_password(self, email: str, ip: str) -> None:
        self._limit_email_requests("forgot", email, ip)
        user = self.users.get_by_email(email)
        if user is not None and user.status == UserStatus.active:
            now = self.clock.now()
            self.tokens.invalidate_for_user(user.id, AuthTokenPurpose.reset_password, now)
            raw = self._create_token(
                user,
                AuthTokenPurpose.reset_password,
                timedelta(minutes=self.settings.password_reset_ttl_minutes),
            )
            self.mailer.send_password_reset(user, raw)
            logger.info("auth.reset.requested", extra={"user_id": user.id, "ip": ip})
        self.session.commit()

    def check_reset_token(self, raw_token: str, ip: str) -> None:
        """Say whether a reset link is still usable, without using it up."""
        self.limiter.consume(f"resetcheck:ip:{ip}", TOKEN_ATTEMPTS_PER_IP, HOUR)
        self.session.commit()
        record = self._load_token(raw_token, AuthTokenPurpose.reset_password)
        user = self.users.get(record.user_id)
        if user is None or user.status != UserStatus.active:
            raise AuthError("invalid_token", "This link is invalid or has expired.", 400)

    def reset_password(self, raw_token: str, new_password: str, ip: str) -> None:
        self.limiter.consume(f"reset:ip:{ip}", TOKEN_ATTEMPTS_PER_IP, HOUR)
        self.session.commit()

        record = self._load_token(raw_token, AuthTokenPurpose.reset_password)
        user = self.users.get(record.user_id)
        if user is None or user.status != UserStatus.active:
            raise AuthError("invalid_token", "This link is invalid or has expired.", 400)
        # Validate the password before using up the one-time token, so a typo can be retried.
        problems = password_problems(new_password, email=user.email, full_name=user.full_name)
        if problems:
            raise AuthError("weak_password", " ".join(problems), 422)
        if not self.tokens.consume(record.id, self.clock.now()):
            raise AuthError("invalid_token", "This link is invalid or has expired.", 400)

        now = self.clock.now()
        user.password_hash = hash_password(new_password)
        user.password_changed_at = now
        # Receiving the email proves control of the mailbox, so this also verifies it.
        self._mark_verified(user)
        self.tokens.invalidate_for_user(user.id, AuthTokenPurpose.reset_password, now)
        self.sessions.revoke_all(user.id)  # whoever had the old password is signed out
        self.mailer.send_password_changed(user)
        self.session.commit()
        logger.info("auth.reset.completed", extra={"user_id": user.id, "ip": ip})

    # ---- account -----------------------------------------------------------------------------

    def profile(self, user: User) -> UserRead:
        return UserRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            status=user.status,
            email_verified=user.email_verified,
            has_password=user.password_hash is not None,
            google_linked=self.identities.exists_for_user(user.id, AuthProvider.google),
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        )

    def update_profile(self, user: User, data: UpdateProfileRequest) -> User:
        user.full_name = data.full_name
        self.session.commit()
        self.session.refresh(user)
        return user

    def change_password(
        self, user: User, data: ChangePasswordRequest, current_session_id: int
    ) -> None:
        bucket = f"chpw:user:{user.id}"
        self.limiter.check(bucket, CHANGE_PASSWORD_FAILURES, FIFTEEN_MIN)
        if user.password_hash is None:
            raise AuthError(
                "no_password",
                "This account has no password yet. Use 'Forgot password' to set one.",
                400,
            )
        if not verify_password(data.current_password, user.password_hash):
            self.limiter.record(bucket)
            self.session.commit()
            raise AuthError("incorrect_password", "Your current password is incorrect.", 400)
        problems = password_problems(data.new_password, email=user.email, full_name=user.full_name)
        if problems:
            raise AuthError("weak_password", " ".join(problems), 422)
        if verify_password(data.new_password, user.password_hash):
            raise AuthError(
                "password_reused", "Choose a password different from your current one.", 422
            )

        user.password_hash = hash_password(data.new_password)
        user.password_changed_at = self.clock.now()
        self.limiter.reset(bucket)
        self.sessions.revoke_all(user.id, except_session_id=current_session_id)
        self.mailer.send_password_changed(user)
        self.session.commit()
        logger.info("auth.password.changed", extra={"user_id": user.id})

    # ---- Google ------------------------------------------------------------------------------

    def new_google_nonce(self) -> str:
        return make_signed_nonce(self.clock.now(), self.settings.secret_key)

    def google_login(
        self, credential: str, nonce: str, ip: str, user_agent: str | None
    ) -> tuple[User, str, bool]:
        self.limiter.consume(f"google:ip:{ip}", GOOGLE_ATTEMPTS_PER_IP, FIFTEEN_MIN)
        self.session.commit()

        # The nonce must be one we issued recently AND be the one Google signed into the token:
        # a stolen ID token cannot be replayed against us.
        if not verify_signed_nonce(
            nonce, self.clock.now(), self.settings.secret_key, NONCE_MAX_AGE_SECONDS
        ):
            raise AuthError("google_auth_failed", "Google sign-in failed. Please try again.", 401)
        try:
            claims = self.google.verify(credential)
        except GoogleAuthError as exc:
            logger.warning("auth.google.rejected", extra={"ip": ip, "reason": str(exc)[:120]})
            raise AuthError(
                "google_auth_failed", "Google sign-in failed. Please try again.", 401
            ) from exc
        if claims.nonce != nonce:
            raise AuthError("google_auth_failed", "Google sign-in failed. Please try again.", 401)
        if not claims.email_verified:
            raise AuthError(
                "google_email_unverified", "Your Google email address is not verified.", 403
            )

        is_new = False
        email = claims.email.strip().lower()
        identity = self.identities.get_by_subject(AuthProvider.google, claims.subject)
        if identity is not None:
            user = self.users.get(identity.user_id)
            if user is None:
                raise AuthError("google_auth_failed", "Google sign-in failed.", 401)
        else:
            existing = self.users.get_by_email(email)
            if existing is not None:
                user = self._link_google_to_existing(existing, claims.subject, email)
            else:
                user = self._create_google_user(claims.subject, email, claims.name)
                is_new = True

        if user.status != UserStatus.active:
            raise AuthError("account_suspended", "This account has been suspended.", 403)
        if not user.email_verified:
            self._mark_verified(user)  # Google vouched for this address

        token = self._start_session(user, user_agent)
        self.session.commit()
        logger.info("auth.google.success", extra={"user_id": user.id, "new": is_new, "ip": ip})
        return user, token, is_new

    # ---- internals ---------------------------------------------------------------------------

    def _link_google_to_existing(self, user: User, subject: str, email: str) -> User:
        """A Google account with a verified email matches an existing account: link them.

        If that existing account never verified its email, whoever registered it may not own the
        mailbox (they could be squatting on the address to take over the real owner's account).
        So its password is discarded; the real owner proves control with Google instead.
        """
        if not user.email_verified:
            user.password_hash = None
            self.sessions.revoke_all(user.id)
            self.tokens.invalidate_for_user(
                user.id, AuthTokenPurpose.verify_email, self.clock.now()
            )
            logger.warning("auth.google.unverified_account_taken_over", extra={"user_id": user.id})
        self.identities.add(
            AuthIdentity(
                user_id=user.id, provider=AuthProvider.google, subject=subject, email=email
            )
        )
        return user

    def _create_google_user(self, subject: str, email: str, name: str | None) -> User:
        now = self.clock.now()
        full_name = (name or email.split("@")[0]).strip()[:100] or "User"
        user = self.users.add(
            User(
                email=email,
                full_name=full_name,
                password_hash=None,
                status=UserStatus.active,
                terms_accepted_at=now,  # the sign-up screen states that continuing accepts them
            )
        )
        self.identities.add(
            AuthIdentity(
                user_id=user.id, provider=AuthProvider.google, subject=subject, email=email
            )
        )
        return user

    def _start_session(self, user: User, user_agent: str | None) -> str:
        user.last_login_at = self.clock.now()
        return self.sessions.create(user, user_agent)

    def _mark_verified(self, user: User) -> None:
        if user.email_verified_at is None:
            user.email_verified_at = self.clock.now()
        self._maybe_claim_legacy_data(user)

    def _maybe_claim_legacy_data(self, user: User) -> None:
        """Hand pre-accounts data to its owner.

        With LEGACY_DATA_OWNER_EMAIL set, only that account can claim it. With it unset, the
        first verified account claims it, but only on a local setup: on a deployed site that
        would let the first stranger to sign up take the data, so nothing is claimed.
        """
        owner = self.settings.legacy_data_owner_email.strip().lower()
        if owner:
            if owner != user.email:
                return
        elif not self.settings.frontend_is_local:
            logger.warning(
                "legacy data not claimed: set LEGACY_DATA_OWNER_EMAIL to the owner's email",
                extra={"user_id": user.id},
            )
            return
        claim_legacy_data(self.session, user.id)

    def _issue_verification(self, user: User) -> None:
        now = self.clock.now()
        self.tokens.invalidate_for_user(user.id, AuthTokenPurpose.verify_email, now)
        raw = self._create_token(
            user,
            AuthTokenPurpose.verify_email,
            timedelta(hours=self.settings.email_verification_ttl_hours),
        )
        self.mailer.send_verification(user, raw)

    def _create_token(self, user: User, purpose: AuthTokenPurpose, ttl: timedelta) -> str:
        raw = generate_token()
        now = self.clock.now()
        self.tokens.add(
            AuthToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=hash_token(raw),
                expires_at=now + ttl,
                created_at=now,
            )
        )
        return raw

    def _load_token(self, raw: str, purpose: AuthTokenPurpose) -> AuthToken:
        record = self.tokens.get_by_hash(hash_token(raw), purpose)
        if record is None:
            raise AuthError("invalid_token", "This link is invalid or has expired.", 400)
        if record.used_at is not None:
            raise AuthError("token_used", "This link has already been used.", 400)
        if record.expires_at <= self.clock.now():
            raise AuthError(
                "token_expired", "This link has expired. Please request a new one.", 400
            )
        return record

    def _limit_email_requests(self, action: str, email: str, ip: str) -> None:
        self.limiter.consume(
            f"{action}:email:{hash_identifier(email)}", EMAIL_REQUESTS_PER_ADDRESS, HOUR
        )
        self.limiter.consume(f"{action}:ip:{ip}", EMAIL_REQUESTS_PER_IP, HOUR)
        self.session.commit()
