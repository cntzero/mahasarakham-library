"""Local accounts, hashed invitation tokens, and revocable cookie sessions."""
import contextlib, getpass, hashlib, hmac, json, os, secrets, sqlite3, time
from pathlib import Path

DB=Path(os.environ.get('MAHA_AUTH_DB','/srv/maha-library-api/accounts.sqlite'))

def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def password_hash(password,salt):return hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex()
def validate_password(password):
    if not isinstance(password,str) or not 12<=len(password)<=256:raise ValueError('Use a password of 12–256 characters.')
def email(value):
    if not isinstance(value,str) or len(value)>254 or '@' not in value or any(c.isspace() for c in value):raise ValueError('Enter a valid email address.')
    return value.strip().casefold()
@contextlib.contextmanager
def connection():
    db=sqlite3.connect(DB,timeout=20);db.row_factory=sqlite3.Row
    try:
        yield db;db.commit()
    except Exception:db.rollback();raise
    finally:db.close()
def initialize():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with connection() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,role TEXT NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS invitations(token TEXT PRIMARY KEY,email TEXT NOT NULL,role TEXT NOT NULL,expires INTEGER NOT NULL,used INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS access_people(email TEXT PRIMARY KEY,mode TEXT NOT NULL DEFAULT 'local',planned_role TEXT NOT NULL DEFAULT 'user',updated INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS vpn_devices(id INTEGER PRIMARY KEY,email TEXT NOT NULL,label TEXT NOT NULL,router_profile TEXT NOT NULL DEFAULT '',address TEXT,router_created INTEGER NOT NULL DEFAULT 0,config_shared INTEGER NOT NULL DEFAULT 0,certificate_installed INTEGER NOT NULL DEFAULT 0,tested INTEGER NOT NULL DEFAULT 0,revoke_requested INTEGER NOT NULL DEFAULT 0,router_removed INTEGER NOT NULL DEFAULT 0,updated INTEGER NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS vpn_live_address ON vpn_devices(address) WHERE router_removed=0;
        CREATE TABLE IF NOT EXISTS access_events(id INTEGER PRIMARY KEY,actor INTEGER,email TEXT NOT NULL,event TEXT NOT NULL,created INTEGER NOT NULL);''')
    os.chmod(DB,0o600)
def public(user):return {k:user[k] for k in ('id','email','role')}
def session(token):
    if not token:return None
    with connection() as db:
        row=db.execute('SELECT u.* FROM users u JOIN sessions s ON u.id=s.user_id WHERE s.token=? AND s.expires>? AND u.active=1',(digest(token),int(time.time()))).fetchone()
    return public(row) if row else None
def login(address,password,client):
    address=email(address);key=digest(client+'|'+address);now=int(time.time())
    with connection() as db:
        attempt=db.execute('SELECT * FROM attempts WHERE key=?',(key,)).fetchone()
        if attempt and attempt['expires']>now and attempt['count']>=8:raise ValueError('Too many attempts. Please wait 15 minutes.')
        row=db.execute('SELECT * FROM users WHERE email=? AND active=1',(address,)).fetchone()
        actual=password_hash(password if isinstance(password,str) and len(password)<=256 else '',row['salt'] if row else 'unknown-account')
        valid=row and hmac.compare_digest(actual,row['password'])
        if not valid:
            count=attempt['count']+1 if attempt and attempt['expires']>now else 1
            db.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?)',(key,count,now+900))
        else:
            db.execute('DELETE FROM attempts WHERE key=?',(key,));token=secrets.token_urlsafe(32)
            db.execute('DELETE FROM sessions WHERE expires<=?',(now,))
            db.execute('INSERT INTO sessions VALUES(?,?,?)',(digest(token),row['id'],now+7*86400))
    if not valid:raise ValueError('Email or password was not recognized.')
    return public(row),token
def logout(token):
    with connection() as db:db.execute('DELETE FROM sessions WHERE token=?',(digest(token or ''),))
def invite(address,role):
    address=email(address)
    if role not in ('super','user'):raise ValueError('Choose Super user or User.')
    token=secrets.token_urlsafe(32)
    with connection() as db:
        if db.execute('SELECT 1 FROM users WHERE email=?',(address,)).fetchone():raise ValueError('That email already has an account.')
        db.execute('DELETE FROM invitations WHERE email=?',(address,))
        db.execute('INSERT INTO invitations VALUES(?,?,?,?,0)',(digest(token),address,role,int(time.time())+7*86400))
    return token
def accept(token,password):
    validate_password(password);now=int(time.time());salt=secrets.token_hex(16);hashed=password_hash(password,salt)
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM invitations WHERE token=? AND used=0 AND expires>?',(digest(token),now)).fetchone()
        if not row:raise ValueError('This invitation has expired or has already been used.')
        if db.execute('SELECT 1 FROM users WHERE email=?',(row['email'],)).fetchone():raise ValueError('That account already exists.')
        db.execute('INSERT INTO users(email,role,salt,password) VALUES(?,?,?,?)',(row['email'],row['role'],salt,hashed))
        db.execute('UPDATE invitations SET used=1 WHERE token=?',(digest(token),))
        db.execute('INSERT INTO access_events(actor,email,event,created) VALUES(NULL,?,?,?)',(row['email'],'Library invitation accepted',now))
    return True
def users():
    with connection() as db:return [dict(r) for r in db.execute('SELECT id,email,role,active FROM users ORDER BY email')]
def update_user(ident,role,active,actor):
    if role not in ('super','user') or not isinstance(active,bool):raise ValueError('Invalid role or status.')
    with connection() as db:
        db.execute('BEGIN IMMEDIATE');row=db.execute('SELECT * FROM users WHERE id=?',(ident,)).fetchone()
        if not row:raise ValueError('Account not found.')
        if row['role']=='super' and row['active'] and (role!='super' or not active):
            count=db.execute("SELECT COUNT(*) FROM users WHERE role='super' AND active=1").fetchone()[0]
            if count<=1:raise ValueError('Keep at least one active Super user.')
        db.execute('UPDATE users SET role=?,active=? WHERE id=?',(role,int(active),ident))
        db.execute('DELETE FROM sessions WHERE user_id=?',(ident,))

if __name__=='__main__':
    initialize()
    if any(u['role']=='super' and u['active'] for u in users()):
        print('An active Super user already exists; no account changed.')
    else:
        print('Create your first MAHA Super user. Credentials stay on this server.')
        address=email(input('Email address: ').strip());password=getpass.getpass('Library password (at least 12 characters): ');validate_password(password)
        if password!=getpass.getpass('Repeat library password: '):raise SystemExit('Passwords did not match; no account created.')
        salt=secrets.token_hex(16)
        with connection() as db:db.execute('INSERT INTO users(email,role,salt,password) VALUES(?,?,?,?)',(address,'super',salt,password_hash(password,salt)))
        print('Super user created.')
