"""
migrate_db.py
Run this script ONCE to add the new security columns to the existing database.
Usage: python migrate_db.py
"""

import sqlite3
import os

try:
    import bcrypt as _bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

def find_db():
    """Search for finanalyzer.db in common locations"""
    possible_paths = [
        r'D:\AnasPython\instance\finanalyzer.db',
        r'D:\AnasPython\finanalyzer.db',
        r'D:\AnasPython - Copy\instance\finanalyzer.db',
        r'D:\AnasPython - Copy\finanalyzer.db',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'finanalyzer.db'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'finanalyzer.db'),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None



def is_bcrypt_hash(value: str) -> bool:
    """
    Return True if the value looks like a valid bcrypt hash.
    Bcrypt hashes always start with $2b$ or $2a$ and are exactly 60 chars long.
    """
    if not value:
        return False
    return (value.startswith('$2b$') or value.startswith('$2a$')) and len(value) == 60


def migrate_passwords(cursor, conn):
    """
    Check every user's password_hash column.
    - If it is already a valid bcrypt hash  → skip (safe).
    - If it is plaintext (or any other format) → hash it with bcrypt and update.

    A backup of every changed row is printed to the console so nothing is lost.
    IMPORTANT: After this migration all affected users will keep their current
    password (now properly hashed). No passwords are changed or reset.
    """
    print("\n🔐 Checking password encryption for all users...")

    if not BCRYPT_AVAILABLE:
        print("   ❌ 'bcrypt' package not found. Run:  pip install bcrypt")
        print("   ⏭️  Skipping password migration.")
        return

    # Check if password_hash column exists
    cursor.execute("PRAGMA table_info(user)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'password_hash' not in columns:
        print("   ⚠️  Column 'password_hash' not found in user table. Skipping.")
        return

    cursor.execute("SELECT id, username, password_hash FROM user")
    users = cursor.fetchall()

    if not users:
        print("   ℹ️  No users found in the database.")
        return

    fixed   = 0
    skipped = 0
    errors  = 0

    for user_id, username, password_hash in users:
        # ── Already a valid bcrypt hash → nothing to do ──────────
        if is_bcrypt_hash(password_hash or ''):
            skipped += 1
            print(f"   ✅ [{user_id}] {username:<20} → already bcrypt-hashed (safe)")
            continue

        # ── Plaintext or unknown format → hash it now ────────────
        plaintext = password_hash or ''  # treat current value as the raw password

        if not plaintext:
            # Edge case: empty password — set a random secure placeholder.
            # The user will need to reset their password via admin.
            import secrets, string
            plaintext = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(16))
            print(f"   ⚠️  [{user_id}] {username:<20} → empty password! "
                  f"A random placeholder was set. User must reset password.")

        try:
            hashed = _bcrypt.hashpw(plaintext.encode('utf-8'), _bcrypt.gensalt(rounds=12)).decode('utf-8')
            cursor.execute(
                "UPDATE user SET password_hash = ? WHERE id = ?",
                (hashed, user_id)
            )
            conn.commit()
            fixed += 1
            print(f"   🔒 [{user_id}] {username:<20} → plaintext detected & hashed successfully")
        except Exception as e:
            errors += 1
            print(f"   ❌ [{user_id}] {username:<20} → Error hashing password: {e}")

    print(f"\n   📊 Password migration summary:")
    print(f"      Already hashed  : {skipped}")
    print(f"      Fixed (hashed)  : {fixed}")
    print(f"      Errors          : {errors}")
    if fixed > 0:
        print(f"   ✅ {fixed} password(s) have been encrypted successfully.")
    if errors > 0:
        print(f"   ⚠️  {errors} password(s) could not be processed. Check errors above.")


def migrate():
    print("=" * 50)
    print("🔍 Searching for finanalyzer.db ...")
    print("=" * 50)

    DB_PATH = find_db()

    if not DB_PATH:
        print("❌ Database not found in any known location.")
        print("\n📂 Searched in:")
        print("   D:\\AnasPython\\instance\\finanalyzer.db")
        print("   D:\\AnasPython\\finanalyzer.db")
        print("   D:\\AnasPython - Copy\\instance\\finanalyzer.db")
        print("   D:\\AnasPython - Copy\\finanalyzer.db")
        print("❌ Database not found, creating new one...")
        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'finanalyzer.db')
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    print(f"✅ Found database at: {DB_PATH}")
    print("=" * 50)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Show existing columns
    cursor.execute("PRAGMA table_info(user)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    print(f"📋 Existing columns: {existing_columns}")
    print()

    migrations = [
        {
            "column": "failed_login_attempts",
            "sql": "ALTER TABLE user ADD COLUMN failed_login_attempts INTEGER DEFAULT 0"
        },
        {
            "column": "locked_until",
            "sql": "ALTER TABLE user ADD COLUMN locked_until DATETIME"
        },
        {
            "column": "role",
            "sql": "ALTER TABLE user ADD COLUMN role VARCHAR(30) DEFAULT 'financial_analyst' NOT NULL"
        }
    ]

    for migration in migrations:
        col = migration["column"]
        if col not in existing_columns:
            try:
                cursor.execute(migration["sql"])
                print(f"✅ Added column: {col}")
            except Exception as e:
                print(f"❌ Error adding {col}: {e}")
        else:
            print(f"⏭️  Column already exists: {col}")

    conn.commit()

    # ── Update existing admin users to developer role ──────────────
    print("\n🔄 Updating admin users to developer role...")
    try:
        cursor.execute("UPDATE user SET role = 'developer' WHERE is_admin = 1 AND (role = 'financial_analyst' OR role IS NULL OR role = '')")
        updated = cursor.rowcount
        conn.commit()
        if updated:
            print(f"   ✅ Updated {updated} admin user(s) to Developer role")
        else:
            print("   ℹ️  No admin users needed role update")
    except Exception as e:
        print(f"   ⚠️  Could not update admin roles: {e}")

    # ── Create audit_log table if not exists ──────────────
    print("\n📋 Checking audit_log table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            user_id     INTEGER REFERENCES user(id) ON DELETE SET NULL,
            username    VARCHAR(80)  NOT NULL,
            action      VARCHAR(50)  NOT NULL,
            entity_type VARCHAR(50),
            entity_id   INTEGER,
            entity_name VARCHAR(200),
            details     TEXT,
            ip_address  VARCHAR(45)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_timestamp ON audit_log(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_audit_log_action    ON audit_log(action)")
    conn.commit()
    print("✅ audit_log table ready")

    # ── Password encryption check & fix ──────────────────
    migrate_passwords(cursor, conn)

    # Verify
    cursor.execute("PRAGMA table_info(user)")
    final_columns = [row[1] for row in cursor.fetchall()]
    print(f"\n📋 Final columns: {final_columns}")

    conn.close()

    print("\n✅ Migration completed successfully!")
    print("   You can now restart your Flask app.")
    print("=" * 50)


if __name__ == '__main__':
    migrate()