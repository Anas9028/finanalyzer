import os
import re
import warnings
import logging
from datetime import datetime, date, timedelta, timezone
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from markupsafe import escape
from werkzeug.utils import secure_filename
import json

warnings.filterwarnings("ignore", category=UserWarning, module='openpyxl')

# ==================== LOGGING SETUP ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('security.log'),
        logging.StreamHandler()
    ]
)
security_logger = logging.getLogger('security')

# ==================== FLASK APP SETUP ====================
app = Flask(__name__)

# ── Security Configuration ──────────────────────────────
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(32))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finanalyzer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024   # 16 MB

# ── Session Security ─────────────────────────────────────
app.config['SESSION_COOKIE_HTTPONLY'] = True      # JS cannot read the cookie
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'    # CSRF protection
app.config['SESSION_COOKIE_SECURE'] = False       # Set True in production (HTTPS)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Auto-logout

# ── WTF CSRF ─────────────────────────────────────────────
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600          # Token valid for 1 hour

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ==================== EXTENSIONS ====================
db       = SQLAlchemy(app)
bcrypt   = Bcrypt(app)
csrf     = CSRFProtect(app)

# ── Rate Limiter ─────────────────────────────────────────
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# ==================== SECURITY HELPERS ====================

ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

def allowed_file(filename: str) -> bool:
    """Validate file extension is in the whitelist."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_input(value: str, max_length: int = 500) -> str:
    """
    Escape HTML special characters and strip whitespace.
    Prevents XSS by ensuring user input is never rendered as raw HTML.
    """
    if not value:
        return ''
    return str(escape(str(value).strip()))[:max_length]


def validate_username(username: str) -> bool:
    """Only allow alphanumeric characters and underscores."""
    return bool(re.match(r'^[a-zA-Z0-9_]{3,80}$', username))


def validate_email(email: str) -> bool:
    """Simple e-mail format validation."""
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Enforce strong-password policy:
      - At least 8 characters
      - At least one uppercase letter
      - At least one lowercase letter
      - At least one digit
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number."
    return True, "OK"


def check_session_timeout() -> bool:
    """
    Return True if the session has timed out (idle > 30 minutes).
    Updates 'last_activity' timestamp on every valid request.
    """
    if 'user_id' not in session:
        return False
    last_activity = session.get('last_activity')
    if last_activity:
        idle = datetime.now(timezone.utc) - datetime.fromisoformat(last_activity).replace(tzinfo=timezone.utc)
        if idle > timedelta(minutes=30):
            security_logger.warning(
                f"Session timeout for user_id={session.get('user_id')} "
                f"after {idle.seconds // 60} minutes of inactivity."
            )
            return True
    session['last_activity'] = datetime.now(timezone.utc).isoformat()
    return False


# ── Language helper ──────────────────────────────────────
def get_lang() -> str:
    """
    Read preferred language from cookie 'finanalyzer_lang'.
    JS sets this cookie on every page load via:
        document.cookie = 'finanalyzer_lang=' + localStorage.getItem('finanalyzer_lang') + '; path=/';
    Falls back to 'en'.
    """
    return request.cookies.get('finanalyzer_lang', 'en') if 'en' != request.cookies.get('finanalyzer_lang', 'en') else \
           request.cookies.get('finanalyzer_lang', 'en')


@app.context_processor
def inject_lang():
    """Make current language available in ALL templates as {{ lang }}"""
    return {'lang': get_lang()}


# ── Audit Log helper ─────────────────────────────────────
def log_audit(action: str, entity_type: str = None, entity_id: int = None,
              entity_name: str = None, details: dict = None):
    """
    Write a structured audit record to the audit_log table.
    Must be called BEFORE db.session.commit() in the same request.
    """
    try:
        uid   = session.get('user_id')
        uname = session.get('username', 'system')
        ip    = request.remote_addr
        entry = AuditLog(
            user_id     = uid,
            username    = uname,
            action      = action,
            entity_type = entity_type,
            entity_id   = entity_id,
            entity_name = entity_name,
            details     = json.dumps(details, default=str) if details else None,
            ip_address  = ip,
        )
        db.session.add(entry)
    except Exception as exc:
        security_logger.error(f"[AuditLog] Failed to write entry: {exc}")


# ── Security headers on every response ──────────────────
@app.after_request
def set_security_headers(response):
    """
    Add HTTP security headers to every response.
    These protect against XSS, clickjacking, MIME-sniffing, etc.
    """
    response.headers['X-Content-Type-Options']  = 'nosniff'
    response.headers['X-Frame-Options']          = 'DENY'
    response.headers['X-XSS-Protection']         = '1; mode=block'
    response.headers['Referrer-Policy']           = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy']  = (
        "default-src 'self'; "
        "connect-src 'self'; "
        "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
        "font-src 'self' cdn.jsdelivr.net; "
        "img-src 'self' data:;"
    )
    return response


# ==================== DATABASE MODELS ====================
user_company = db.Table(
    'user_company',
    db.Column('user_id',    db.Integer, db.ForeignKey('user.id'),    primary_key=True),
    db.Column('company_id', db.Integer, db.ForeignKey('company.id'), primary_key=True)
)


class User(db.Model):
    __tablename__ = 'user'
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    full_name     = db.Column(db.String(200), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin      = db.Column(db.Boolean, default=False)
    # Role: 'developer', 'company_manager', 'financial_analyst', 'auditor'
    # developer = full system control (you)
    # company_manager = manages assigned companies + their users
    # financial_analyst = uploads data, runs analysis, exports PDF
    # auditor = read-only + export PDF only
    role          = db.Column(db.String(30), default='financial_analyst', nullable=False)
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_login    = db.Column(db.DateTime)

    # ── Brute-force protection fields ───────────────────
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until          = db.Column(db.DateTime, nullable=True)

    companies = db.relationship('Company', secondary=user_company, backref='users')

    # ── Role helpers ──────────────────────────────────────
    def _role(self):
        """Safe role accessor - handles NULL/empty role in DB"""
        # If is_admin=True but role is missing/null, treat as developer (backwards compat)
        if not self.role:
            return 'developer' if self.is_admin else 'financial_analyst'
        return self.role

    def is_developer(self):
        return self._role() == 'developer'

    def is_company_manager(self):
        return self._role() == 'company_manager'

    def is_financial_analyst(self):
        return self._role() == 'financial_analyst'

    def is_auditor(self):
        return self._role() == 'auditor'

    def can_upload(self):
        """Financial Analyst only"""
        return self._role() == 'financial_analyst'

    def can_view_analysis(self):
        """Company-level roles only — developer manages system, not company data"""
        return self._role() in ('financial_analyst', 'auditor', 'company_manager')

    def can_export_pdf(self):
        """Company-level roles only — developer does not export company reports"""
        return self._role() in ('financial_analyst', 'auditor', 'company_manager')

    def can_manage_users(self):
        """Developer and Company Manager only"""
        return self._role() in ('developer', 'company_manager')

    def can_manage_companies(self):
        """Developer only"""
        return self._role() == 'developer'

    def can_assign_companies(self):
        """Developer and Company Manager"""
        return self._role() in ('developer', 'company_manager')

    def can_view_audit_log(self):
        """Developer and Auditor only"""
        return self._role() in ('developer', 'auditor')

    def can_edit_company(self):
        return self._role() == 'developer'

    def get_role_display(self):
        roles = {
            'developer': 'Developer',
            'company_manager': 'Company Manager',
            'financial_analyst': 'Financial Analyst',
            'auditor': 'Auditor'
        }
        return roles.get(self.role, self.role)

    def is_locked(self) -> bool:
        """Return True if the account is currently locked out."""
        if self.locked_until and datetime.now(timezone.utc) < self.locked_until:
            return True
        return False

    def increment_failed_login(self):
        """Increment counter; lock account for 15 min after 5 failures."""
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= 5:
            self.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            security_logger.warning(
                f"Account LOCKED: username='{self.username}' "
                f"after {self.failed_login_attempts} failed attempts."
            )

    def reset_failed_login(self):
        """Reset counter after a successful login."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def __repr__(self):
        return f'<User {self.username}>'


class Company(db.Model):
    __tablename__ = 'company'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    industry    = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_by  = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    financial_data = db.relationship('FinancialData', backref='company', lazy=True, cascade='all, delete-orphan')
    analyses       = db.relationship('Analysis',      backref='company', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Company {self.name}>'


class FinancialData(db.Model):
    __tablename__ = 'financial_data'
    id           = db.Column(db.Integer, primary_key=True)
    company_id   = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    period_start = db.Column(db.Date, nullable=False)
    period_end   = db.Column(db.Date, nullable=False)
    raw_data_json = db.Column(db.Text, nullable=False)
    uploaded_by  = db.Column(db.Integer, db.ForeignKey('user.id'))
    uploaded_at  = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    analyses     = db.relationship('Analysis', backref='financial_data', lazy=True)

    @property
    def raw_data(self):
        return json.loads(self.raw_data_json) if self.raw_data_json else {}

    @raw_data.setter
    def raw_data(self, value):
        self.raw_data_json = json.dumps(value, default=str)

    def __repr__(self):
        return f'<FinancialData {self.company_id} - {self.period_end}>'


class Analysis(db.Model):
    __tablename__ = 'analysis'
    id                 = db.Column(db.Integer, primary_key=True)
    company_id         = db.Column(db.Integer, db.ForeignKey('company.id'),       nullable=False)
    financial_data_id  = db.Column(db.Integer, db.ForeignKey('financial_data.id'), nullable=False)
    ratios_json        = db.Column(db.Text, nullable=False)
    ai_analysis_json   = db.Column(db.Text, nullable=False)
    created_by         = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at         = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def ratios(self):
        return json.loads(self.ratios_json) if self.ratios_json else {}

    @ratios.setter
    def ratios(self, value):
        self.ratios_json = json.dumps(value, default=str)

    @property
    def ai_analysis(self):
        return json.loads(self.ai_analysis_json) if self.ai_analysis_json else {}

    @ai_analysis.setter
    def ai_analysis(self, value):
        self.ai_analysis_json = json.dumps(value, default=str)

    def __repr__(self):
        return f'<Analysis {self.id} - Company {self.company_id}>'


class AuditLog(db.Model):
    """
    Audit trail: records every significant action performed in the system.
    Stores who did what, on which entity, when, and from which IP address.
    """
    __tablename__ = 'audit_log'
    id          = db.Column(db.Integer, primary_key=True)
    timestamp   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)   # nullable → system events
    username    = db.Column(db.String(80),  nullable=False)                         # denormalized for history
    action      = db.Column(db.String(50),  nullable=False, index=True)             # e.g. 'UPLOAD', 'EDIT_COMPANY'
    entity_type = db.Column(db.String(50),  nullable=True)                          # 'Company', 'User', 'Analysis'
    entity_id   = db.Column(db.Integer,     nullable=True)                          # FK value of the affected row
    entity_name = db.Column(db.String(200), nullable=True)                          # human-readable name snapshot
    details     = db.Column(db.Text,        nullable=True)                          # JSON with extra context
    ip_address  = db.Column(db.String(45),  nullable=True)                          # supports IPv6

    # Relationship (optional – gives easy access to User object)
    user = db.relationship('User', backref=db.backref('audit_logs', lazy='dynamic'), foreign_keys=[user_id])

    def __repr__(self):
        return f'<AuditLog {self.id} {self.action} by {self.username}>'


# ==================== IMPORT MODULES ====================
from ai_analyzer      import AIAnalyzer
from ratio_calculator import RatioCalculator
from report_generator import ReportGenerator
from data_parser      import DataParser
from job_manager      import job_manager

ai_analyzer       = AIAnalyzer()
ratio_calculator  = RatioCalculator()
report_generator  = ReportGenerator()
data_parser       = DataParser()


# ==================== DECORATORS ====================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))

        # ── Session timeout check ────────────────────────
        if check_session_timeout():
            session.clear()
            flash('Your session has expired due to inactivity. Please log in again.', 'warning')
            return redirect(url_for('login'))

        # ── Verify user still exists in database ─────────
        user = db.session.get(User, session['user_id'])
        if not user:
            session.clear()
            security_logger.warning(
                f"Session cleared: user_id={session.get('user_id')} no longer exists in DB "
                f"IP={request.remote_addr}"
            )
            flash('Your account no longer exists. Please log in again.', 'warning')
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))

        if check_session_timeout():
            session.clear()
            flash('Your session has expired due to inactivity. Please log in again.', 'warning')
            return redirect(url_for('login'))

        user = db.session.get(User, session['user_id'])
        if not user or not user.is_admin:
            security_logger.warning(
                f"Unauthorized admin access attempt by user_id={session.get('user_id')} "
                f"IP={request.remote_addr} path={request.path}"
            )
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))

        return f(*args, **kwargs)
    return decorated_function




def developer_required(f):
    """Only Developer role can access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        if check_session_timeout():
            session.clear()
            flash('Your session has expired.', 'warning')
            return redirect(url_for('login'))
        user = db.session.get(User, session['user_id'])
        if not user or not user.is_developer():
            security_logger.warning(
                f"Unauthorized developer access: user_id={session.get('user_id')} path={request.path}"
            )
            flash('Developer access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def get_user_accessible_company_ids(user: 'User') -> list[int]:
    """
    Row-Level Security helper.
    Returns the list of company IDs the current user is allowed to access.
    - developer        → ALL companies
    - company_manager  → only assigned companies
    - financial_analyst → only assigned companies
    - auditor          → only assigned companies
    """
    if user.is_developer():
        return [c.id for c in db.session.execute(db.select(Company)).scalars().all()]
    return [c.id for c in user.companies]


def assert_company_access(user: 'User', company_id: int) -> bool:
    """
    Returns True if the user has RLS access to the given company_id.
    Logs a warning to security_logger and audit_log on denial.
    """
    allowed = get_user_accessible_company_ids(user)
    if company_id not in allowed:
        security_logger.warning(
            f"[RLS] Access denied: user='{user.username}' role='{user.role}' "
            f"company_id={company_id} IP={request.remote_addr} path={request.path}"
        )
        # Also write to audit_log for traceability
        try:
            entry = AuditLog(
                user_id     = user.id,
                username    = user.username,
                action      = 'ACCESS_DENIED',
                entity_type = 'Company',
                entity_id   = company_id,
                entity_name = f'Company#{company_id}',
                details     = f'{{"path": "{request.path}", "method": "{request.method}"}}',
                ip_address  = request.remote_addr,
            )
            db.session.add(entry)
            db.session.commit()
        except Exception:
            pass  # Don't let audit failure block the denial
        return False
    return True


def manager_or_developer_required(f):
    """Developer or Company Manager can access."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        if check_session_timeout():
            session.clear()
            flash('Your session has expired.', 'warning')
            return redirect(url_for('login'))
        user = db.session.get(User, session['user_id'])
        if not user or not user.can_manage_users():
            flash('Access denied.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def company_access_required(f):
    """
    Decorator that enforces Row-Level Security for any route with <company_id>.
    - Checks login & session timeout.
    - Blocks developer role (they manage system, not company data).
    - Verifies the user is assigned to the requested company.
    Usage: place AFTER @login_required on any route with company_id.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        company_id = kwargs.get('company_id')
        if company_id is None:
            # Fallback: no company_id in route, skip RLS
            return f(*args, **kwargs)

        user = db.session.get(User, session.get('user_id'))
        if not user:
            session.clear()
            flash('Session invalid. Please log in again.', 'warning')
            return redirect(url_for('login'))

        if not assert_company_access(user, company_id):
            flash('You do not have access to this company.', 'danger')
            return redirect(url_for('dashboard'))

        return f(*args, **kwargs)
    return decorated_function

# ==================== ROUTES ====================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')


# ── LOGIN  (Rate-limited: max 10 attempts / minute per IP) ──
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"],
               error_message="Too many login attempts. Please wait a minute and try again.")
def login():
    if request.method == 'POST':
        # Sanitize inputs before using them
        username = sanitize_input(request.form.get('username', ''), max_length=80)
        password = request.form.get('password', '')   # Don't escape password before checking hash

        # Input validation
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('login.html')

        user = db.session.execute(
            db.select(User).filter_by(username=username)
        ).scalar_one_or_none()

        # ── Account lockout check ────────────────────────
        if user and user.is_locked():
            remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
            security_logger.warning(
                f"Login blocked for locked account username='{username}' IP={request.remote_addr}"
            )
            flash(
                f'Account is temporarily locked due to too many failed attempts. '
                f'Please try again in {remaining + 1} minute(s).',
                'danger'
            )
            return render_template('login.html')

        # ── Password verification ────────────────────────
        if user and bcrypt.check_password_hash(user.password_hash, password):
            user.reset_failed_login()
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()

            # Regenerate session to prevent session fixation attacks
            session.clear()
            session.permanent = True
            session['user_id']       = user.id
            session['username']      = user.username
            session['is_admin']      = user.is_admin
            session['role']          = user.role
            session['last_activity'] = datetime.now(timezone.utc).isoformat()

            security_logger.info(
                f"Successful login: username='{user.username}' IP={request.remote_addr}"
            )
            log_audit('LOGIN', entity_type='User', entity_id=user.id, entity_name=user.username)
            db.session.commit()
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('dashboard'))

        else:
            # Increment failed counter even when user doesn't exist (timing-safe)
            if user:
                user.increment_failed_login()
                db.session.commit()

            security_logger.warning(
                f"Failed login attempt: username='{username}' IP={request.remote_addr}"
            )
            # Generic message — do NOT reveal whether the username exists
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
def logout():
    username = session.get('username', 'User')
    uid      = session.get('user_id')
    security_logger.info(f"Logout: username='{username}' IP={request.remote_addr}")
    log_audit('LOGOUT', entity_type='User', entity_id=uid, entity_name=username)
    try:
        db.session.commit()
    except Exception:
        pass
    session.clear()
    flash(f'Goodbye {username}! You have been logged out successfully.', 'info')
    return redirect(url_for('index'))


# ── USER MANAGEMENT ──────────────────────────────────────

@app.route('/admin/users')
@manager_or_developer_required
def admin_users():
    current_user = db.session.get(User, session['user_id'])
    if current_user.is_developer():
        # Developer sees all non-developer users
        users = db.session.execute(
            db.select(User).filter(User.role != 'developer')
        ).scalars().all()
    elif current_user.is_company_manager():
        # Company Manager sees ONLY users assigned to their companies (excluding developers)
        linked_users = set()
        for company in current_user.companies:
            for u in company.users:
                if not u.is_developer():
                    linked_users.add(u)
        users = list(linked_users)
    else:
        # financial_analyst / auditor have no business here — redirect
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('users.html', users=users)


@app.route('/admin/users/add', methods=['GET', 'POST'])
@manager_or_developer_required
def add_user():
    if request.method == 'POST':
        username  = sanitize_input(request.form.get('username', ''),  max_length=80)
        email     = sanitize_input(request.form.get('email', ''),     max_length=120)
        full_name = sanitize_input(request.form.get('full_name', ''), max_length=200)
        password  = request.form.get('password', '')
        is_admin  = request.form.get('is_admin') == 'on'
        role      = sanitize_input(request.form.get('role', 'financial_analyst'), max_length=30)

        current_user = db.session.get(User, session['user_id'])
        # Validate role selection based on who is creating the user
        allowed_roles = ['developer', 'company_manager', 'financial_analyst', 'auditor']
        if role not in allowed_roles:
            role = 'financial_analyst'
        # Company managers cannot create developers or other managers
        if current_user.is_company_manager() and role in ('developer', 'company_manager'):
            flash('Company Managers can only create Financial Analysts or Auditors.', 'danger')
            return redirect(url_for('add_user'))
        # Derive is_admin from role
        is_admin = (role == 'developer')

        # ── Input validation ─────────────────────────────
        if not validate_username(username):
            flash('Username must be 3–80 characters and contain only letters, numbers, or underscores.', 'danger')
            return redirect(url_for('add_user'))

        if not validate_email(email):
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('add_user'))

        ok, msg = validate_password_strength(password)
        if not ok:
            flash(msg, 'danger')
            return redirect(url_for('add_user'))

        if db.session.execute(db.select(User).filter_by(username=username)).scalar_one_or_none():
            flash('Username already exists.', 'danger')
            return redirect(url_for('add_user'))

        if db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none():
            flash('Email already exists.', 'danger')
            return redirect(url_for('add_user'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(
            username=username, email=email,
            full_name=full_name, password_hash=hashed_password,
            is_admin=is_admin, role=role
        )
        db.session.add(new_user)
        db.session.commit()

        log_audit('ADD_USER', entity_type='User', entity_id=new_user.id,
                  entity_name=username,
                  details={'full_name': full_name, 'email': email, 'is_admin': is_admin})
        db.session.commit()

        security_logger.info(
            f"New user created: username='{username}' is_admin={is_admin} "
            f"by admin='{session.get('username')}'"
        )
        # ── Assign new user to selected companies (manager chooses) ──
        if current_user.is_company_manager() and current_user.companies:
            selected_ids = request.form.getlist('company_ids')
            selected_ids = [int(i) for i in selected_ids if str(i).isdigit()]
            manager_company_ids = [c.id for c in current_user.companies]

            assigned_names = []
            for cid in selected_ids:
                if cid in manager_company_ids:   # security: only manager's own companies
                    company = db.session.get(Company, cid)
                    if company and company not in new_user.companies:
                        new_user.companies.append(company)
                        assigned_names.append(company.name)
            db.session.commit()

            if assigned_names:
                flash(f'User {full_name} created and assigned to: {", ".join(assigned_names)}', 'success')
            else:
                flash(f'User {full_name} created. No company assigned yet — you can assign them later from the company page.', 'warning')
        else:
            flash(f'User {full_name} created successfully!', 'success')
        return redirect(url_for('admin_users'))

    # GET: pass manager's companies to template for checkboxes
    current_user = db.session.get(User, session['user_id'])
    manager_companies = current_user.companies if current_user.is_company_manager() else []
    return render_template('add_user.html', manager_companies=manager_companies)


@app.route('/admin/users/edit/<int:user_id>', methods=['GET', 'POST'])
@manager_or_developer_required
def edit_user(user_id):
    user_to_edit = db.session.get(User, user_id)
    if not user_to_edit:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_users'))

    # Company Manager can only edit users assigned to their companies
    editor = db.session.get(User, session['user_id'])
    if editor.is_company_manager():
        manager_user_ids = set()
        for company in editor.companies:
            for u in company.users:
                manager_user_ids.add(u.id)
        if user_to_edit.id not in manager_user_ids:
            security_logger.warning(
                f"Company Manager '{editor.username}' attempted to edit user '{user_to_edit.username}' not in their companies"
            )
            flash('You can only edit users assigned to your companies.', 'danger')
            return redirect(url_for('admin_users'))
        # Company Manager cannot edit another manager or developer
        if user_to_edit.role in ('developer', 'company_manager'):
            flash('You cannot edit this user.', 'danger')
            return redirect(url_for('admin_users'))

    total_admins = db.session.execute(
        db.select(db.func.count(User.id)).filter_by(is_admin=True)
    ).scalar()

    if request.method == 'POST':
        full_name = sanitize_input(request.form.get('full_name', ''), max_length=200)
        email     = sanitize_input(request.form.get('email', ''),     max_length=120)
        username  = sanitize_input(request.form.get('username', ''),  max_length=80)
        new_password = request.form.get('new_password', '')
        role      = sanitize_input(request.form.get('role', user_to_edit.role), max_length=30)

        current_user = db.session.get(User, session['user_id'])
        allowed_roles = ['developer', 'company_manager', 'financial_analyst', 'auditor']
        if role not in allowed_roles:
            role = user_to_edit.role
        # Company managers cannot assign developer/manager roles
        if current_user.is_company_manager() and role in ('developer', 'company_manager'):
            flash('Company Managers can only assign Financial Analyst or Auditor roles.', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))
        is_admin  = (role == 'developer')

        if not validate_username(username):
            flash('Invalid username format.', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))

        if not validate_email(email):
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))

        if new_password:
            ok, msg = validate_password_strength(new_password)
            if not ok:
                flash(msg, 'danger')
                return redirect(url_for('edit_user', user_id=user_id))

        existing_user = db.session.execute(
            db.select(User).filter_by(username=username)
        ).scalar_one_or_none()
        if existing_user and existing_user.id != user_id:
            flash('Username already exists.', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))

        existing_email = db.session.execute(
            db.select(User).filter_by(email=email)
        ).scalar_one_or_none()
        if existing_email and existing_email.id != user_id:
            flash('Email already exists.', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))

        if user_to_edit.is_admin and not is_admin and total_admins == 1:
            flash('Cannot remove admin privileges from the last administrator.', 'danger')
            return redirect(url_for('edit_user', user_id=user_id))

        user_to_edit.full_name = full_name
        user_to_edit.email     = email
        user_to_edit.username  = username
        user_to_edit.is_admin  = is_admin
        user_to_edit.role      = role

        if new_password:
            user_to_edit.password_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')

        db.session.commit()
        security_logger.info(
            f"User updated: username='{username}' by admin='{session.get('username')}'"
        )
        log_audit('EDIT_USER', entity_type='User', entity_id=user_id,
                  entity_name=username,
                  details={'email': email, 'is_admin': is_admin,
                           'password_changed': bool(new_password)})
        db.session.commit()
        flash(f'User {username} updated successfully!', 'success')
        return redirect(url_for('admin_users'))

    return render_template('edit_user.html', user=user_to_edit, total_admins=total_admins)


@app.route('/admin/users/delete/<int:user_id>')
@manager_or_developer_required
def delete_user(user_id):
    user_to_delete = db.session.get(User, user_id)
    if not user_to_delete:
        flash('User not found.', 'danger')
        return redirect(url_for('admin_users'))

    if user_to_delete.id == session['user_id']:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin_users'))

    # Company Manager can only delete users assigned to their companies
    deleter = db.session.get(User, session['user_id'])
    if deleter.is_company_manager():
        manager_user_ids = set()
        for company in deleter.companies:
            for u in company.users:
                manager_user_ids.add(u.id)
        if user_to_delete.id not in manager_user_ids:
            flash('You can only delete users assigned to your companies.', 'danger')
            return redirect(url_for('admin_users'))
        if user_to_delete.role in ('developer', 'company_manager'):
            flash('You cannot delete this user.', 'danger')
            return redirect(url_for('admin_users'))

    if user_to_delete.is_admin:
        total_admins = db.session.execute(
            db.select(db.func.count(User.id)).filter_by(is_admin=True)
        ).scalar()
        if total_admins == 1:
            flash('Cannot delete the last administrator.', 'danger')
            return redirect(url_for('admin_users'))

    username = user_to_delete.username
    db.session.delete(user_to_delete)
    db.session.commit()
    log_audit('DELETE_USER', entity_type='User', entity_id=user_id,
              entity_name=username)
    db.session.commit()
    security_logger.info(
        f"User deleted: username='{username}' by admin='{session.get('username')}'"
    )
    flash(f'User {username} deleted successfully.', 'success')
    return redirect(url_for('admin_users'))


# ── COMPANY MANAGEMENT ───────────────────────────────────

@app.route('/admin/company/<int:company_id>/assign', methods=['GET', 'POST'])
@login_required
def assign_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('dashboard'))

    current_user = db.session.get(User, session['user_id'])
    if not current_user.can_assign_companies():
        flash('You do not have permission to assign companies.', 'danger')
        return redirect(url_for('dashboard'))

    # Company managers can only assign companies that are assigned to them
    if current_user.is_company_manager() and company not in current_user.companies:
        flash('You can only manage companies assigned to you.', 'danger')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        user_id = request.form.get('user_id')
        user = db.session.get(User, user_id)
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('assign_company', company_id=company_id))

        if company in user.companies:
            flash(f'Company already assigned to {user.full_name}.', 'warning')
        else:
            user.companies.append(company)
            log_audit('ASSIGN_COMPANY', entity_type='Company', entity_id=company.id,
                      entity_name=company.name, details={'assigned_to_user': user.username,
                                                         'assigned_to_user_id': user.id})
            db.session.commit()
            flash(f'Company "{company.name}" assigned to {user.full_name} successfully!', 'success')

        return redirect(url_for('company_profile', company_id=company_id))

    # Show only analyst/auditor/manager roles for assignment; exclude developers
    from sqlalchemy import and_
    users = db.session.execute(
        db.select(User).filter(User.role.in_(['financial_analyst', 'auditor', 'company_manager']))
    ).scalars().all()
    # Company managers only see users they could manage
    if current_user.is_company_manager():
        pass  # all analysts/auditors are visible to them
    assigned_users = company.users
    return render_template('assign_company.html',
                           company=company, users=users, assigned_users=assigned_users)


@app.route('/admin/company/<int:company_id>/unassign/<int:user_id>')
@login_required
def unassign_company(company_id, user_id):
    company = db.session.get(Company, company_id)
    user    = db.session.get(User, user_id)
    current_user = db.session.get(User, session['user_id'])
    if not company or not user:
        flash('Company or user not found.', 'danger')
        return redirect(url_for('dashboard'))
    if not current_user.can_assign_companies():
        flash('You do not have permission to unassign companies.', 'danger')
        return redirect(url_for('dashboard'))
    if current_user.is_company_manager() and company not in current_user.companies:
        flash('You can only manage companies assigned to you.', 'danger')
        return redirect(url_for('dashboard'))

    if company in user.companies:
        user.companies.remove(company)
        log_audit('UNASSIGN_COMPANY', entity_type='Company', entity_id=company_id,
                  entity_name=company.name, details={'removed_from_user': user.username,
                                                     'removed_from_user_id': user_id})
        db.session.commit()
        flash(f'Company "{company.name}" unassigned from {user.full_name}.', 'success')
    else:
        flash('Company not assigned to this user.', 'warning')

    return redirect(url_for('assign_company', company_id=company_id))


@app.route('/company/add', methods=['GET', 'POST'])
@developer_required
def add_company():
    if request.method == 'POST':
        name             = sanitize_input(request.form.get('company_name', ''), max_length=200)
        industry         = sanitize_input(request.form.get('industry', ''),     max_length=100)
        description      = sanitize_input(request.form.get('description', ''),  max_length=500)
        assigned_user_id = request.form.get('assigned_user')

        if not assigned_user_id:
            flash('Company must be linked to a user account! Please select a user.', 'danger')
            return redirect(url_for('add_company'))

        if not name or not industry:
            flash('Company name and industry are required.', 'danger')
            return redirect(url_for('add_company'))

        # ── Validate industry against whitelist ──────────
        allowed_industries = [
            'Manufacturing', 'Automotive', 'Chemicals', 'Food & Beverage',
            'Textiles', 'Construction Materials',
            'Technology', 'Software Development', 'Telecommunications',
            'E-commerce', 'Digital Marketing', 'AI & Machine Learning',
            'Finance', 'Banking', 'Insurance', 'Investment',
            'Accounting', 'Consulting',
            'Retail', 'Wholesale', 'Real Estate', 'Hospitality',
            'Tourism', 'Restaurants', 'Services',
            'Healthcare', 'Pharmaceuticals', 'Medical Equipment',
            'Education', 'Training',
            'Energy', 'Renewable Energy', 'Oil & Gas', 'Environmental Services',
            'Transportation', 'Logistics', 'Shipping', 'Aviation',
            'Media', 'Entertainment', 'Advertising', 'Publishing',
            'Agriculture', 'Livestock', 'Fishing', 'Mining',
            'Construction', 'Government', 'NGO', 'Legal Services',
            'Security Services', 'Other'
        ]
        if industry not in allowed_industries:
            flash('Invalid industry selected.', 'danger')
            return redirect(url_for('add_company'))

        if db.session.execute(db.select(Company).filter_by(name=name)).scalar_one_or_none():
            flash(f'Company name "{name}" already exists. Please choose a different name.', 'danger')
            return redirect(url_for('add_company'))

        try:
            new_company = Company(
                name=name, industry=industry,
                description=description if description else None,
                created_by=session['user_id']
            )
            db.session.add(new_company)
            db.session.flush()

            assigned_user = db.session.get(User, assigned_user_id)
            if not assigned_user:
                db.session.rollback()
                flash('Selected user not found. Company creation cancelled.', 'danger')
                return redirect(url_for('add_company'))

            if assigned_user.is_developer():
                db.session.rollback()
                flash('Cannot assign companies to Developer accounts.', 'danger')
                return redirect(url_for('add_company'))

            assigned_user.companies.append(new_company)
            log_audit('ADD_COMPANY', entity_type='Company', entity_id=new_company.id,
                      entity_name=name, details={'industry': industry,
                                                 'assigned_to': assigned_user.username})
            db.session.commit()

            security_logger.info(
                f"Company created: '{name}' assigned to '{assigned_user.username}' "
                f"by admin='{session.get('username')}'"
            )
            flash(f'Company "{name}" created and linked to {assigned_user.full_name} successfully!', 'success')
            return redirect(url_for('company_profile', company_id=new_company.id))

        except Exception as e:
            db.session.rollback()
            security_logger.error(f"Error creating company: {e}")
            flash(f'Error creating company: {str(e)}', 'danger')
            return redirect(url_for('add_company'))

    users = db.session.execute(
        db.select(User).filter(User.role.in_(['company_manager', 'financial_analyst', 'auditor']))
    ).scalars().all()
    if len(users) == 0:
        flash('No users available! Create a user account first before adding companies.', 'warning')
    return render_template('add_company.html', users=users)


@app.route('/dashboard')
@login_required
def dashboard():
    user = db.session.get(User, session['user_id'])

    if not user:
        session.clear()
        flash('Your account no longer exists. Please log in again.', 'warning')
        return redirect(url_for('login'))

    if user.is_developer():
        companies = db.session.execute(db.select(Company)).scalars().all()
        recent_analyses = []
        orphaned = [c for c in companies if len(c.users) == 0]
        if orphaned:
            flash(
                f'Warning: {len(orphaned)} companies are not linked to any user accounts. '
                'Please assign them to users.', 'warning'
            )
    else:
        # ── Row-Level Security: non-developer sees ONLY assigned companies ──
        companies = user.companies
        company_ids = [c.id for c in companies]
        recent_analyses = db.session.execute(
            db.select(Analysis)
            .filter(Analysis.company_id.in_(company_ids))
            .order_by(Analysis.created_at.desc())
            .limit(5)
        ).scalars().all() if company_ids else []

    # Build chart data for interactive dashboard charts
    companies_chart_data = []
    for company in companies:
        health_score = 0
        analyses_list = []
        for fd in company.financial_data:
            for a in fd.analyses:
                overall    = a.ai_analysis.get('overall', {}) if a.ai_analysis else {}
                hs_data    = a.ai_analysis.get('health_score', {}) if a.ai_analysis else {}
                cat_scores = hs_data.get('category_scores', {})
                h_score    = overall.get('health_score', 0) or 0
                health_score = h_score
                analyses_list.append({
                    'period_label':        fd.period_end.strftime('%Y-%m') if fd.period_end else 'N/A',
                    'health_score':        h_score,
                    'liquidity_score':     cat_scores.get('liquidity', 0) or 0,
                    'profitability_score': cat_scores.get('profitability', 0) or 0,
                    'solvency_score':      cat_scores.get('solvency', 0) or 0,
                    'efficiency_score':    cat_scores.get('efficiency', 0) or 0,
                })
        companies_chart_data.append({
            'id':           company.id,
            'name':         company.name,
            'industry':     company.industry or 'Other',
            'health_score': health_score,
            'analyses':     analyses_list,
        })

    # Role-specific stats
    stats = {}
    if user.is_developer():
        total_users     = db.session.execute(db.select(db.func.count(User.id))).scalar()
        total_analyses  = db.session.execute(db.select(db.func.count(Analysis.id))).scalar()
        orphaned_count  = sum(1 for c in companies if len(c.users) == 0)
        stats = {
            'total_users':     total_users,
            'total_companies': len(companies),
            'total_analyses':  total_analyses,
            'orphaned':        orphaned_count,
        }
    elif user.is_company_manager():
        all_users = set()
        for c in companies:
            for u in c.users:
                all_users.add(u.id)
        analyzed = sum(1 for c in companies if any(len(fd.analyses) > 0 for fd in c.financial_data))
        stats = {
            'my_companies':   len(companies),
            'total_team':     len(all_users),
            'total_analyses': sum(len(fd.analyses) for c in companies for fd in c.financial_data),
            'analyzed':       analyzed,
        }
    elif user.is_financial_analyst():
        latest_date = None
        for a in recent_analyses:
            if latest_date is None or a.created_at > latest_date:
                latest_date = a.created_at
        stats = {
            'my_companies':   len(companies),
            'total_uploads':  sum(len(c.financial_data) for c in companies),
            'total_analyses': sum(len(fd.analyses) for c in companies for fd in c.financial_data),
            'latest_date':    latest_date.strftime('%b %d') if latest_date else 'None',
        }
    elif user.is_auditor():
        critical = sum(1 for d in companies_chart_data if 0 < d['health_score'] < 40)
        stats = {
            'my_companies':   len(companies),
            'total_analyses': sum(len(fd.analyses) for c in companies for fd in c.financial_data),
            'critical':       critical,
            'total_periods':  sum(len(c.financial_data) for c in companies),
        }

    return render_template('dashboard.html',
                           user=user, companies=companies,
                           recent_analyses=recent_analyses,
                           companies_chart_data=companies_chart_data,
                           stats=stats)


# ── FILE UPLOAD ──────────────────────────────────────────

@app.route('/company/<int:company_id>/upload', methods=['GET', 'POST'])
@login_required
def upload_financial_data(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('dashboard'))

    user = db.session.get(User, session['user_id'])

    # ── Row-Level Security ────────────────────────────────
    if not assert_company_access(user, company_id):
        flash('You do not have access to this company.', 'danger')
        return redirect(url_for('dashboard'))

    if not user.can_upload():
        flash('Only Financial Analysts can upload financial data.', 'warning')
        return redirect(url_for('company_profile', company_id=company_id))

    if request.method == 'POST':
        if 'income_file' not in request.files or 'balance_file' not in request.files:
            return jsonify({'error': 'Please upload both files.'}), 400

        income_file  = request.files['income_file']
        balance_file = request.files['balance_file']

        if income_file.filename == '' or balance_file.filename == '':
            return jsonify({'error': 'No files selected.'}), 400

        if not allowed_file(income_file.filename):
            return jsonify({'error': 'Income Statement must be an Excel file (.xlsx or .xls).'}), 400

        if not allowed_file(balance_file.filename):
            return jsonify({'error': 'Balance Sheet must be an Excel file (.xlsx or .xls).'}), 400

        try:
            import time
            timestamp = str(int(time.time()))

            income_filename  = f"{timestamp}_{secure_filename(income_file.filename)}"
            balance_filename = f"{timestamp}_{secure_filename(balance_file.filename)}"

            income_path  = os.path.join(app.config['UPLOAD_FOLDER'], income_filename)
            balance_path = os.path.join(app.config['UPLOAD_FOLDER'], balance_filename)

            income_file.save(income_path)
            balance_file.save(balance_path)

            # ── Create background job and start processing ──
            job_id = job_manager.create_job()
            lang   = get_lang()

            def process_upload(job, b_path, i_path, cid, uid, _lang):
                """Runs in a daemon thread — updates job progress at each step."""
                with app.app_context():
                    try:
                        job.update(10, 'Reading Excel files…')
                        _data = data_parser.read_company_files(b_path, i_path)
                        _company = db.session.get(Company, cid)
                        _data['industry'] = _company.industry or 'Services'

                        job.update(30, 'Calculating financial ratios…')
                        _ratios = ratio_calculator.calculate_ratios(_data)

                        job.update(50, 'Running AI analysis… (this may take 30–60 s)')
                        _ai = ai_analyzer.analyze_ratios(_ratios, _data, lang=_lang)

                        job.update(80, 'Saving results to database…')
                        _fd = FinancialData(
                            company_id=cid,
                            period_start=_data.get('from date'),
                            period_end=_data.get('to date'),
                            raw_data=_data,
                            uploaded_by=uid
                        )
                        db.session.add(_fd)
                        db.session.flush()

                        _analysis = Analysis(
                            company_id=cid,
                            financial_data_id=_fd.id,
                            ratios=_ratios,
                            ai_analysis=_ai,
                            created_by=uid
                        )
                        db.session.add(_analysis)

                        _comp_name = db.session.get(Company, cid).name
                        log_audit('UPLOAD_DATA', entity_type='Analysis',
                                  entity_id=_analysis.id,
                                  entity_name=_comp_name,
                                  details={
                                      'period_start':     str(_data.get('from date')),
                                      'period_end':       str(_data.get('to date')),
                                      'financial_data_id': _fd.id
                                  })
                        db.session.commit()

                        security_logger.info(
                            f"Data uploaded (async): company='{_comp_name}' "
                            f"analysis_id={_analysis.id} user_id={uid}"
                        )

                        job.update(100, 'Done!')
                        job.status = 'success'
                        job.result = {'analysis_id': _analysis.id, 'company_id': cid}

                    except Exception as exc:
                        db.session.rollback()
                        security_logger.error(f"Background upload error: {exc}")
                        job.status = 'failed'
                        job.error  = str(exc)
                    finally:
                        for path in [b_path, i_path]:
                            try:
                                if path and os.path.exists(path):
                                    os.remove(path)
                            except Exception:
                                pass

            job_manager.start(
                job_id,
                process_upload,
                args=(balance_path, income_path,
                      company_id, session['user_id'], lang)
            )

            # Return job_id immediately — frontend polls /api/upload/status/<job_id>
            return jsonify({'job_id': job_id}), 202

        except Exception as e:
            security_logger.error(f"Upload initiation error: {e}")
            return jsonify({'error': str(e)}), 500

    return render_template('upload_data.html', company=company, user=user)


@app.route('/api/upload/status/<job_id>')
@login_required
@limiter.limit("300 per hour")   # dedicated limit — polling every 2–15 s won't hit this
def upload_status(job_id):
    """Frontend polls this (with exponential backoff) to track background upload progress."""
    status = job_manager.get_status(job_id)
    if not status:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(status)


# ── ANALYSIS ─────────────────────────────────────────────

@app.route('/analysis/<int:analysis_id>')
@login_required
def view_analysis(analysis_id):
    analysis = db.session.get(Analysis, analysis_id)
    if not analysis:
        flash('Analysis not found.', 'danger')
        return redirect(url_for('dashboard'))

    company = db.session.get(Company, analysis.company_id)
    user    = db.session.get(User, session['user_id'])

    # ── Row-Level Security: verify company access FIRST ──
    if not assert_company_access(user, analysis.company_id):
        flash('You do not have access to this analysis.', 'danger')
        return redirect(url_for('dashboard'))

    if not user.can_view_analysis():
        flash('You do not have permission to view analyses.', 'danger')
        return redirect(url_for('dashboard'))

    # ── Integrity check: analysis must belong to an accessible company ──
    if not company:
        flash('Associated company not found.', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('analysis_view.html', analysis=analysis, company=company, user=user)


@app.route('/analysis/<int:analysis_id>/download-pdf')
@login_required
def download_analysis_pdf(analysis_id):
    analysis = db.session.get(Analysis, analysis_id)
    if not analysis:
        flash('Analysis not found.', 'danger')
        return redirect(url_for('dashboard'))

    company = db.session.get(Company, analysis.company_id)
    user    = db.session.get(User, session['user_id'])

    # ── Row-Level Security: verify company access FIRST ──
    if not assert_company_access(user, analysis.company_id):
        flash('You do not have access to this analysis.', 'danger')
        return redirect(url_for('dashboard'))

    if not user.can_export_pdf():
        flash('You do not have permission to export PDFs.', 'warning')
        return redirect(url_for('dashboard'))

    if not company:
        flash('Associated company not found.', 'danger')
        return redirect(url_for('dashboard'))

    pdf_path = report_generator.generate_analysis_report(analysis, company)
    log_audit('DOWNLOAD_PDF', entity_type='Analysis', entity_id=analysis_id,
              entity_name=company.name)
    try:
        db.session.commit()
    except Exception:
        pass
    return send_file(pdf_path, as_attachment=True,
                     download_name=f'{company.name}_analysis_{analysis.id}.pdf')


# ── COMPARE ──────────────────────────────────────────────

@app.route('/compare', methods=['GET', 'POST'])
@login_required
def compare():
    user = db.session.get(User, session['user_id'])

    if user.is_developer():
        # Developer manages system — no access to company analysis
        flash('Developers do not have access to financial comparisons.', 'warning')
        return redirect(url_for('dashboard'))
    companies = user.companies
    can_compare_companies = len(companies) >= 2
    can_compare_periods   = len(companies) >= 1

    if request.method == 'POST':
        compare_type = sanitize_input(request.form.get('compare_type', ''), max_length=20)

        if not user.can_view_analysis():
            flash('You do not have permission to perform comparisons.', 'danger')
            return redirect(url_for('compare'))

        if compare_type == 'companies':
            if len(companies) < 2:
                flash('You need at least 2 companies assigned to compare.', 'warning')
                return redirect(url_for('compare'))

            company1_id  = request.form.get('company1')
            company2_id  = request.form.get('company2')
            analysis1_id = request.form.get('analysis1')
            analysis2_id = request.form.get('analysis2')

            if not company1_id or not company2_id:
                flash('Please select both companies.', 'warning')
                return redirect(url_for('compare'))

            if not analysis1_id or not analysis2_id:
                flash('Please select analysis reports for both companies.', 'warning')
                return redirect(url_for('compare'))

            if company1_id == company2_id:
                flash('Please select two different companies.', 'warning')
                return redirect(url_for('compare'))

            company1 = db.session.get(Company, company1_id)
            company2 = db.session.get(Company, company2_id)

            if not assert_company_access(user, int(company1_id)) or \
               not assert_company_access(user, int(company2_id)):
                flash('You can only compare companies assigned to you.', 'danger')
                return redirect(url_for('compare'))

            analysis1 = db.session.get(Analysis, analysis1_id)
            analysis2 = db.session.get(Analysis, analysis2_id)

            if not analysis1 or analysis1.company_id != int(company1_id):
                flash('Invalid analysis selected for first company.', 'warning')
                return redirect(url_for('compare'))

            if not analysis2 or analysis2.company_id != int(company2_id):
                flash('Invalid analysis selected for second company.', 'warning')
                return redirect(url_for('compare'))

            try:
                comparison = ai_analyzer.compare_companies(analysis1, analysis2)
                return render_template('comparison_result.html',
                                       comparison=comparison,
                                       analysis1=analysis1, analysis2=analysis2,
                                       compare_type='companies', user=user)
            except Exception as e:
                security_logger.error(f"Comparison error: {e}")
                flash(f'Error generating comparison: {str(e)}', 'danger')
                return redirect(url_for('compare'))

        else:   # periods
            company_id = request.form.get('company')
            period1_id = request.form.get('period1')
            period2_id = request.form.get('period2')

            if not company_id:
                flash('Please select a company.', 'warning')
                return redirect(url_for('compare'))

            company = db.session.get(Company, company_id)
            if not company or not assert_company_access(user, int(company_id)):
                flash('You do not have access to this company.', 'danger')
                return redirect(url_for('compare'))

            if not period1_id or not period2_id or period1_id == period2_id:
                flash('Please select two different periods.', 'warning')
                return redirect(url_for('compare'))

            try:
                analysis1 = db.session.get(Analysis, int(period1_id))
                analysis2 = db.session.get(Analysis, int(period2_id))

                if not analysis1 or not analysis2:
                    flash('Invalid period selection.', 'warning')
                    return redirect(url_for('compare'))

                if analysis1.company_id != analysis2.company_id or analysis1.company_id != int(company_id):
                    flash('Selected periods must belong to the same company.', 'warning')
                    return redirect(url_for('compare'))

                analysis_company = db.session.get(Company, analysis1.company_id)
                if not assert_company_access(user, analysis1.company_id):
                    flash('You do not have access to these analyses.', 'danger')
                    return redirect(url_for('compare'))

                comparison = ai_analyzer.compare_periods(analysis1, analysis2)
                return render_template('comparison_result.html',
                                       comparison=comparison,
                                       analysis1=analysis1, analysis2=analysis2,
                                       compare_type='periods', user=user)
            except Exception as e:
                security_logger.error(f"Period comparison error: {e}")
                flash(f'Error generating comparison: {str(e)}', 'danger')
                return redirect(url_for('compare'))

    return render_template('compare.html',
                           companies=companies,
                           can_compare_companies=can_compare_companies,
                           can_compare_periods=can_compare_periods,
                           user=user)


@app.route('/api/comparison/export-pdf', methods=['POST'])
@login_required
def export_comparison_pdf():
    try:
        user = db.session.get(User, session['user_id'])
        if not user.can_export_pdf():
            return jsonify({'error': 'You do not have permission to export PDFs'}), 403

        data         = request.get_json()
        compare_type = data.get('type')
        analysis1_id = data.get('analysis1_id')
        analysis2_id = data.get('analysis2_id')

        analysis1 = db.session.get(Analysis, analysis1_id)
        analysis2 = db.session.get(Analysis, analysis2_id)

        if not analysis1 or not analysis2:
            return jsonify({'error': 'Analyses not found'}), 404

        company1 = db.session.get(Company, analysis1.company_id)
        company2 = db.session.get(Company, analysis2.company_id)

        if not assert_company_access(user, analysis1.company_id) or \
           not assert_company_access(user, analysis2.company_id):
            return jsonify({'error': 'You do not have access to these companies'}), 403

        if compare_type == 'companies':
            comparison = ai_analyzer.compare_companies(analysis1, analysis2)
        else:
            comparison = ai_analyzer.compare_periods(analysis1, analysis2)

        pdf_path = report_generator.generate_comparison_report(
            analysis1, analysis2, comparison, compare_type
        )

        filename = f"Comparison_{company1.name.replace(' ', '_')}"
        if compare_type == 'companies':
            filename += f"_vs_{company2.name.replace(' ', '_')}"
        else:
            filename += "_Period_Analysis"
        filename += ".pdf"

        return send_file(pdf_path, as_attachment=True,
                         download_name=filename, mimetype='application/pdf')

    except Exception as e:
        security_logger.error(f"PDF export error: {e}")
        return jsonify({'error': str(e)}), 500


# ── COMPANY PROFILE / EDIT / DELETE ──────────────────────

@app.route('/company/<int:company_id>')
@login_required
def company_profile(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('dashboard'))

    user = db.session.get(User, session['user_id'])

    # ── Row-Level Security ────────────────────────────────
    if not assert_company_access(user, company_id):
        flash('You do not have access to this company.', 'danger')
        return redirect(url_for('dashboard'))

    financial_data = db.session.execute(
        db.select(FinancialData)
        .filter_by(company_id=company_id)
        .order_by(FinancialData.period_end.desc())
    ).scalars().all()

    analyses = db.session.execute(
        db.select(Analysis)
        .filter_by(company_id=company_id)
        .order_by(Analysis.created_at.desc())
    ).scalars().all()

    assigned_users = company.users if user.can_assign_companies() else None

    return render_template('company_profile.html',
                           company=company, financial_data=financial_data,
                           analyses=analyses, user=user, assigned_users=assigned_users,
                           can_view_analysis=user.can_view_analysis(),
                           can_upload=user.can_upload())


@app.route('/company/<int:company_id>/edit', methods=['GET', 'POST'])
@developer_required
def edit_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('dashboard'))

    user = db.session.get(User, session['user_id'])

    if request.method == 'POST':
        name        = sanitize_input(request.form.get('company_name', ''), max_length=200)
        industry    = sanitize_input(request.form.get('industry', ''),     max_length=100)
        description = sanitize_input(request.form.get('description', ''),  max_length=500)

        if not name or not industry:
            flash('Company name and industry are required.', 'danger')
            return redirect(url_for('edit_company', company_id=company_id))

        existing = db.session.execute(
            db.select(Company).filter_by(name=name)
        ).scalar_one_or_none()
        if existing and existing.id != company_id:
            flash(f'Company name "{name}" is already taken.', 'danger')
            return redirect(url_for('edit_company', company_id=company_id))

        try:
            old_name     = company.name
            old_industry = company.industry
            company.name        = name
            company.industry    = industry
            company.description = description if description else None
            log_audit('EDIT_COMPANY', entity_type='Company', entity_id=company_id,
                      entity_name=name,
                      details={'old_name': old_name, 'new_name': name,
                               'old_industry': old_industry, 'new_industry': industry})
            db.session.commit()

            security_logger.info(
                f"Company updated: id={company_id} name='{name}' "
                f"by admin='{session.get('username')}'"
            )
            flash(f'Company "{name}" updated successfully!', 'success')
            return redirect(url_for('company_profile', company_id=company_id))

        except Exception as e:
            db.session.rollback()
            security_logger.error(f"Error updating company: {e}")
            flash(f'Error updating company: {str(e)}', 'danger')
            return redirect(url_for('edit_company', company_id=company_id))

    return render_template('edit_company.html', company=company, user=user)


@app.route('/company/<int:company_id>/delete')
@developer_required
def delete_company(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        flash('Company not found.', 'danger')
        return redirect(url_for('dashboard'))

    company_name = company.name
    try:
        log_audit('DELETE_COMPANY', entity_type='Company', entity_id=company_id,
                  entity_name=company_name,
                  details={'industry': company.industry,
                           'users_count': len(company.users),
                           'analyses_count': len(company.analyses)})
        db.session.delete(company)
        db.session.commit()
        security_logger.info(
            f"Company deleted: '{company_name}' by admin='{session.get('username')}'"
        )
        flash(f'Company "{company_name}" and all associated data deleted successfully.', 'success')
        return redirect(url_for('dashboard'))

    except Exception as e:
        db.session.rollback()
        security_logger.error(f"Error deleting company: {e}")
        flash(f'Error deleting company: {str(e)}', 'danger')
        return redirect(url_for('company_profile', company_id=company_id))


# ── AUDIT LOG ────────────────────────────────────────────

@app.route('/admin/audit-log')
@login_required
def audit_log():
    """
    Developer and Auditor page that displays the full audit trail with filtering support.
    """
    current_user = db.session.get(User, session['user_id'])
    if not current_user.can_view_audit_log():
        flash('Access denied. Only Developers and Auditors can view the audit log.', 'danger')
        return redirect(url_for('dashboard'))

    # ── Auditor scope: only logs related to their companies ──────────
    is_auditor_scope = current_user.is_auditor()
    auditor_company_ids  = []   # company entity IDs auditor can see
    auditor_company_names = []  # company names for label
    auditor_usernames    = set()  # usernames of users in those companies

    if is_auditor_scope:
        for company in current_user.companies:
            auditor_company_ids.append(company.id)
            auditor_company_names.append(company.name)
            for u in company.users:
                auditor_usernames.add(u.username)
        # also include auditor's own username
        auditor_usernames.add(current_user.username)

    # ── Query filters ────────────────────────────────────
    action_filter      = request.args.get('action', '').strip()
    user_filter        = request.args.get('username', '').strip()
    entity_filter      = request.args.get('entity_type', '').strip()
    entity_name_filter = request.args.get('entity_name', '').strip()
    ip_filter          = request.args.get('ip_address', '').strip()
    date_from          = request.args.get('date_from', '').strip()
    date_to            = request.args.get('date_to', '').strip()
    page               = request.args.get('page', 1, type=int)
    per_page           = 50

    query = db.select(AuditLog).order_by(AuditLog.timestamp.desc())

    # ── Auditor: filter to only their company-related logs ──────────
    if is_auditor_scope:
        from sqlalchemy import or_, and_
        # Show logs where:
        # 1. entity_type is Company/Analysis/FinancialData AND entity_id is one of their companies
        # 2. OR the username belongs to a user in their companies (actions by their team)
        # 3. OR entity_type is Analysis/FinancialData linked to their company
        # We keep it practical: filter by username in their team + company entity_id
        query = query.filter(
            or_(
                # Logs about the company itself
                and_(
                    AuditLog.entity_type == 'Company',
                    AuditLog.entity_id.in_(auditor_company_ids)
                ),
                # Logs about analyses/uploads in their companies
                and_(
                    AuditLog.entity_type.in_(['Analysis', 'FinancialData']),
                    AuditLog.entity_name.in_(auditor_company_names)
                ),
                # Actions performed by users in their companies
                AuditLog.username.in_(list(auditor_usernames))
            )
        )

    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if user_filter:
        query = query.filter(AuditLog.username.ilike(f'%{user_filter}%'))
    if entity_filter:
        query = query.filter(AuditLog.entity_type == entity_filter)
    if entity_name_filter:
        query = query.filter(AuditLog.entity_name.ilike(f'%{entity_name_filter}%'))
    if ip_filter:
        query = query.filter(AuditLog.ip_address.ilike(f'%{ip_filter}%'))
    if date_from:
        try:
            query = query.filter(AuditLog.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(AuditLog.timestamp < dt_to)
        except ValueError:
            pass

    # Paginate
    all_logs    = db.session.execute(query).scalars().all()
    total       = len(all_logs)
    paginated   = all_logs[(page - 1) * per_page : page * per_page]
    total_pages = (total + per_page - 1) // per_page

    # Aggregate stats from ALL visible logs (not just current page)
    from collections import Counter
    action_counts = Counter(log.action for log in all_logs)
    stats_uploads   = action_counts.get('UPLOAD_DATA', 0)
    stats_edits     = sum(v for k, v in action_counts.items() if k.startswith('EDIT_'))
    stats_deletions = sum(v for k, v in action_counts.items() if k.startswith('DELETE_'))

    # Distinct values for filter dropdowns (scoped to visible unfiltered logs)
    base_query = db.select(AuditLog)
    if is_auditor_scope:
        from sqlalchemy import or_, and_
        base_query = base_query.filter(
            or_(
                and_(AuditLog.entity_type == 'Company',
                     AuditLog.entity_id.in_(auditor_company_ids)),
                and_(AuditLog.entity_type.in_(['Analysis', 'FinancialData']),
                     AuditLog.entity_name.in_(auditor_company_names)),
                AuditLog.username.in_(list(auditor_usernames))
            )
        )
    all_base_logs     = db.session.execute(base_query).scalars().all()
    distinct_actions  = sorted(set(log.action      for log in all_base_logs))
    distinct_entities = sorted(set(log.entity_type for log in all_base_logs if log.entity_type))

    # Build export URL preserving all active filters
    export_params = {k: v for k, v in {
        'action': action_filter, 'username': user_filter,
        'entity_type': entity_filter, 'entity_name': entity_name_filter,
        'ip_address': ip_filter, 'date_from': date_from, 'date_to': date_to
    }.items() if v}
    from urllib.parse import urlencode
    export_url = '/api/admin/audit-log/export' + (('?' + urlencode(export_params)) if export_params else '')

    active_filters_count = sum(1 for v in [
        action_filter, user_filter, entity_filter,
        entity_name_filter, ip_filter, date_from, date_to
    ] if v)

    return render_template(
        'audit_log.html',
        logs                  = paginated,
        total                 = total,
        page                  = page,
        total_pages           = total_pages,
        per_page              = per_page,
        distinct_actions      = distinct_actions,
        distinct_entities     = distinct_entities,
        is_auditor_scope      = is_auditor_scope,
        auditor_companies     = auditor_company_names,
        stats_uploads         = stats_uploads,
        stats_edits           = stats_edits,
        stats_deletions       = stats_deletions,
        export_url            = export_url,
        active_filters_count  = active_filters_count,
        # Pass current filters back to template
        filter_action         = action_filter,
        filter_username       = user_filter,
        filter_entity_type    = entity_filter,
        filter_entity_name    = entity_name_filter,
        filter_ip_address     = ip_filter,
        filter_date_from      = date_from,
        filter_date_to        = date_to,
    )


@app.route('/api/admin/audit-log/export')
@login_required
def export_audit_log():
    """Export audit log as CSV for compliance / archiving."""
    current_user = db.session.get(User, session['user_id'])
    if not current_user.can_view_audit_log():
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
    import csv, io

    action_filter      = request.args.get('action', '').strip()
    user_filter        = request.args.get('username', '').strip()
    entity_filter      = request.args.get('entity_type', '').strip()
    entity_name_filter = request.args.get('entity_name', '').strip()
    ip_filter          = request.args.get('ip_address', '').strip()
    date_from          = request.args.get('date_from', '').strip()
    date_to            = request.args.get('date_to', '').strip()

    query = db.select(AuditLog).order_by(AuditLog.timestamp.desc())

    # ── Auditor: restrict to their companies ────────────
    if current_user.is_auditor():
        from sqlalchemy import or_, and_
        auditor_company_ids   = [c.id   for c in current_user.companies]
        auditor_company_names = [c.name for c in current_user.companies]
        auditor_usernames = set()
        for company in current_user.companies:
            for u in company.users:
                auditor_usernames.add(u.username)
        auditor_usernames.add(current_user.username)

        query = query.filter(
            or_(
                and_(AuditLog.entity_type == 'Company',
                     AuditLog.entity_id.in_(auditor_company_ids)),
                and_(AuditLog.entity_type.in_(['Analysis', 'FinancialData']),
                     AuditLog.entity_name.in_(auditor_company_names)),
                AuditLog.username.in_(list(auditor_usernames))
            )
        )

    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if user_filter:
        query = query.filter(AuditLog.username.ilike(f'%{user_filter}%'))
    if entity_filter:
        query = query.filter(AuditLog.entity_type == entity_filter)
    if entity_name_filter:
        query = query.filter(AuditLog.entity_name.ilike(f'%{entity_name_filter}%'))
    if ip_filter:
        query = query.filter(AuditLog.ip_address.ilike(f'%{ip_filter}%'))
    if date_from:
        try:
            query = query.filter(AuditLog.timestamp >= datetime.strptime(date_from, '%Y-%m-%d'))
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(AuditLog.timestamp < dt_to)
        except ValueError:
            pass

    logs = db.session.execute(query).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Timestamp', 'Username', 'Action',
                     'Entity Type', 'Entity ID', 'Entity Name', 'Details', 'IP Address'])

    for log in logs:
        writer.writerow([
            log.id,
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '',
            log.username,
            log.action,
            log.entity_type or '',
            log.entity_id or '',
            log.entity_name or '',
            log.details or '',
            log.ip_address or '',
        ])

    output.seek(0)
    log_audit('EXPORT_AUDIT_LOG', entity_type='AuditLog',
              details={'filters': {
                  'action': action_filter, 'username': user_filter,
                  'entity_type': entity_filter, 'entity_name': entity_name_filter,
                  'ip_address': ip_filter, 'date_from': date_from, 'date_to': date_to
              }, 'records_exported': len(logs)})
    try:
        db.session.commit()
    except Exception:
        pass

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition':
                 f'attachment; filename=audit_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'}
    )


# ── API ENDPOINTS ─────────────────────────────────────────

@app.route('/api/company/<int:company_id>/periods')
@login_required
def company_periods(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    user = db.session.get(User, session['user_id'])
    # ── Row-Level Security: always check access FIRST ────
    if not assert_company_access(user, company_id):
        return jsonify({'error': 'Access denied'}), 403
    if not user.can_view_analysis():
        return jsonify({'error': 'Access denied'}), 403
    financial_data_list = db.session.execute(
        db.select(FinancialData)
        .filter_by(company_id=company_id)
        .order_by(FinancialData.period_end.desc())
    ).scalars().all()

    periods = []
    for fd in financial_data_list:
        analysis = db.session.execute(
            db.select(Analysis)
            .filter_by(financial_data_id=fd.id)
            .order_by(Analysis.created_at.desc())
        ).scalars().first()

        if analysis:
            periods.append({
                'id':           analysis.id,
                'label':        f"{fd.period_start.strftime('%Y-%m-%d')} to {fd.period_end.strftime('%Y-%m-%d')}",
                'period_start': fd.period_start.strftime('%Y-%m-%d'),
                'period_end':   fd.period_end.strftime('%Y-%m-%d'),
                'created_at':   analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })

    return jsonify(periods)


@app.route('/api/company/<int:company_id>/analyses')
@login_required
def company_analyses(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    user = db.session.get(User, session['user_id'])
    # ── Row-Level Security: always check access FIRST ────
    if not assert_company_access(user, company_id):
        return jsonify({'error': 'Access denied'}), 403
    if not user.can_view_analysis():
        return jsonify({'error': 'Access denied'}), 403

    analyses = db.session.execute(
        db.select(Analysis)
        .filter_by(company_id=company_id)
        .order_by(Analysis.created_at.desc())
    ).scalars().all()

    result = []
    for a in analyses:
        fd = db.session.get(FinancialData, a.financial_data_id)
        result.append({
            'id':           a.id,
            'label':        f"Analysis #{a.id} - {fd.period_end.strftime('%Y-%m-%d')}",
            'period_start': fd.period_start.strftime('%Y-%m-%d'),
            'period_end':   fd.period_end.strftime('%Y-%m-%d'),
            'health_score': a.ai_analysis.get('overall', {}).get('health_score', 'N/A'),
            'created_at':   a.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    return jsonify(result)


@app.route('/api/company/<int:company_id>/trends')
@login_required
def company_trends(company_id):
    company = db.session.get(Company, company_id)
    if not company:
        return jsonify({'error': 'Company not found'}), 404

    user = db.session.get(User, session['user_id'])
    # ── Row-Level Security: always check access FIRST ────
    if not assert_company_access(user, company_id):
        return jsonify({'error': 'Access denied'}), 403
    if not user.can_view_analysis():
        return jsonify({'error': 'Access denied'}), 403

    analyses = db.session.execute(
        db.select(Analysis)
        .filter_by(company_id=company_id)
        .order_by(Analysis.created_at)
    ).scalars().all()

    trends = {
        'dates': [], 'current_ratio': [], 'quick_ratio': [],
        'net_profit_margin': [], 'roa': [], 'roe': [], 'debt_to_equity': []
    }

    for a in analyses:
        fd = db.session.get(FinancialData, a.financial_data_id)
        trends['dates'].append(fd.period_end.strftime('%Y-%m-%d'))
        r = a.ratios
        trends['current_ratio'].append(r.get('Current Ratio'))
        trends['quick_ratio'].append(r.get('Quick Ratio'))
        trends['net_profit_margin'].append(r.get('Net Profit Margin (%)'))
        trends['roa'].append(r.get('ROA'))
        trends['roe'].append(r.get('ROE'))
        trends['debt_to_equity'].append(r.get('Debt to Equity'))

    return jsonify(trends)


# ── AI CHAT ASSISTANT ─────────────────────────────────────

@app.route('/api/analysis/<int:analysis_id>/chat', methods=['POST'])
@login_required
def analysis_chat(analysis_id):
    """
    AI Chat endpoint: lets the user ask questions about a specific analysis.
    The analysis ratios & AI insights are injected into the system prompt so
    the model has full context without any extra calls.
    """
    analysis = db.session.get(Analysis, analysis_id)
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404

    company = db.session.get(Company, analysis.company_id)
    user    = db.session.get(User, session['user_id'])

    # ── Row-Level Security: verify company access FIRST ──
    if not assert_company_access(user, analysis.company_id):
        return jsonify({'error': 'Access denied'}), 403

    if not user.can_view_analysis():
        return jsonify({'error': 'Access denied for your role'}), 403

    if not company:
        return jsonify({'error': 'Associated company not found'}), 404

    data = request.get_json(silent=True) or {}
    user_message = sanitize_input(data.get('message', ''), max_length=1000)
    history      = data.get('history', [])   # list of {role, content}

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    # ── Build context from analysis data ────────────────
    ratios      = analysis.ratios or {}
    ai_analysis = analysis.ai_analysis or {}
    fd          = db.session.get(FinancialData, analysis.financial_data_id)
    period      = f"{fd.period_start} → {fd.period_end}" if fd else "N/A"

    health  = ai_analysis.get('health_score', {})
    overall = ai_analysis.get('overall', {})
    recs    = ai_analysis.get('recommendations', {})
    alerts  = ai_analysis.get('alerts', [])

    # Format ratios compactly
    ratio_lines = "\n".join(
        f"  • {k}: {round(v, 3) if isinstance(v, float) else v}"
        for k, v in ratios.items() if v is not None
    )

    critical_alerts = [a for a in alerts if a.get('severity') in ('critical', 'high')]
    alert_lines = "\n".join(
        f"  ⚠ [{a.get('severity','').upper()}] {a.get('message','')}"
        for a in critical_alerts[:5]
    ) or "  None"

    immediate_actions = "\n".join(
        f"  - {r}" for r in recs.get('immediate_actions', [])
    ) or "  None"

    system_prompt = f"""You are an expert AI financial analyst assistant for FinAnalyzer Pro.
You are answering questions about the financial analysis of **{company.name}** ({company.industry} industry).

=== ANALYSIS CONTEXT ===
Period         : {period}
Health Score   : {overall.get('health_score', 'N/A')}/100  |  Grade: {overall.get('grade', 'N/A')} – {overall.get('grade_description', '')}
Risk Level     : {overall.get('risk_level', 'N/A')}
Investment     : {overall.get('investment_rating', 'N/A')}

Category Scores:
  Liquidity      : {health.get('category_scores', {}).get('liquidity', 'N/A')}/100
  Profitability  : {health.get('category_scores', {}).get('profitability', 'N/A')}/100
  Solvency       : {health.get('category_scores', {}).get('solvency', 'N/A')}/100
  Efficiency     : {health.get('category_scores', {}).get('efficiency', 'N/A')}/100

Key Ratios:
{ratio_lines}

Active Alerts (High/Critical):
{alert_lines}

Immediate Recommendations:
{immediate_actions}

=== INSTRUCTIONS ===
- Answer in the same language the user uses (Arabic or English).
- Be concise, specific, and always reference the actual numbers above.
- When asked WHY a metric is low/high, explain the financial logic clearly.
- When asked for priorities, rank by severity using the health score and alerts.
- Never make up numbers not present in the context above.
- Keep responses under 300 words unless the question genuinely requires more detail."""

    # ── Call Groq via the existing ai_analyzer client ───
    if not ai_analyzer.client:
        return jsonify({'error': 'AI service is not configured (missing GROQ_API_KEY)'}), 503

    # Validate & trim history (keep last 10 turns to save tokens)
    safe_history = []
    for msg in history[-10:]:
        if isinstance(msg, dict) and msg.get('role') in ('user', 'assistant') and msg.get('content'):
            safe_history.append({
                'role': msg['role'],
                'content': sanitize_input(str(msg['content']), max_length=800)
            })

    messages = [{'role': 'system', 'content': system_prompt}] + safe_history + \
               [{'role': 'user', 'content': user_message}]

    try:
        response = ai_analyzer.client.chat.completions.create(
            model=ai_analyzer.model,
            messages=messages,
            temperature=0.5,
            max_tokens=500
        )
        reply = response.choices[0].message.content.strip()
        return jsonify({'reply': reply})

    except Exception as e:
        security_logger.error(f"Chat API error: {e}")
        return jsonify({'error': 'AI service temporarily unavailable. Please try again.'}), 503


# ==================== INITIALIZATION ====================
# Exempt the JSON comparison PDF export API from CSRF form-token check.
# The route is still protected by @login_required (session cookie).
csrf.exempt(export_comparison_pdf)
csrf.exempt(analysis_chat)

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("=" * 60)
        print("✅ Database tables created successfully")
        print("=" * 60)

        try:
            admin = db.session.execute(
                db.select(User).filter_by(username='admin')
            ).scalar_one_or_none()

            if not admin:
                hashed_password = bcrypt.generate_password_hash('Admin@1234').decode('utf-8')
                admin = User(
                    username='admin',
                    email='admin@finanalyzer.com',
                    full_name='System Administrator',
                    password_hash=hashed_password,
                    is_admin=True,
                    role='developer'
                )
                db.session.add(admin)
                db.session.commit()
                print("\n✅ Developer user created successfully!")
                print("   👤 Username : admin")
                print("   🔑 Password : Admin@1234")
                print("   🎭 Role     : Developer (full access)")
                print("   ⚠️  Please change the default password after first login!")
            else:
                print("\n✅ Developer user already exists")
        except Exception as e:
            print(f"\n⚠️ Error creating admin user: {e}")
            db.session.rollback()

    print("\n" + "=" * 60)
    print("🚀 Starting FinAnalyzer Pro - AI Financial Analysis System")
    print("=" * 60)
    print("🌐 URL: http://localhost:5000")
    print("\n🔐 Security Features Active:")
    print("   ✓ bcrypt password hashing (cost factor 12)")
    print("   ✓ CSRF protection on all forms")
    print("   ✓ Rate limiting  → 10 login attempts / minute")
    print("   ✓ Account lockout → 15 min after 5 bad passwords")
    print("   ✓ Session timeout → 30 minutes of inactivity")
    print("   ✓ Session fixation prevention on login")
    print("   ✓ XSS protection via input sanitization + CSP headers")
    print("   ✓ Clickjacking protection (X-Frame-Options: DENY)")
    print("   ✓ File-type whitelist for uploads (.xlsx / .xls only)")
    print("   ✓ Security audit log → security.log")
    print("\n⌨️  Press CTRL+C to stop the server")
    print("=" * 60 + "\n")

    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)