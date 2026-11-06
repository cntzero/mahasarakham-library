"""Owner-recorded access workflow. This module never configures the router."""
import ipaddress,sqlite3,time
import accounts

def event(db,actor,address,text):
    db.execute('INSERT INTO access_events(actor,email,event,created) VALUES(?,?,?,?)',(actor,address,text,int(time.time())))

def record_event(actor,address,text):
    with accounts.connection() as db:event(db,actor,accounts.email(address),text)

def save_person(data,actor):
    address=accounts.email(data.get('email'));mode=data.get('mode');role=data.get('role','user')
    if mode not in ('local','remote') or role not in ('user','super'):raise ValueError('Choose local/remote access and User/Super user.')
    with accounts.connection() as db:
        db.execute('INSERT INTO access_people VALUES(?,?,?,?) ON CONFLICT(email) DO UPDATE SET mode=excluded.mode,planned_role=excluded.planned_role,updated=excluded.updated',(address,mode,role,int(time.time())))
        event(db,actor,address,'Setup details saved: '+mode)
    return {'email':address}

def save_device(data,actor):
    address=accounts.email(data.get('email'))
    if any(not isinstance(data.get(k,''),str) for k in ('label','routerProfile','address')):raise ValueError('Device name, router profile and address must be text.')
    if not isinstance(data.get('requestRemoval',False),bool):raise ValueError('Invalid removal checklist value.')
    label=data.get('label','').strip();profile=data.get('routerProfile','').strip();ip=data.get('address','').strip()
    if not label or len(label)>80 or len(profile)>80:raise ValueError('Use a device name of 1–80 characters; router profile names may be up to 80 characters.')
    if ip:
        try:
            interface=ipaddress.IPv4Interface(ip if '/' in ip else ip+'/32')
            if interface.network.prefixlen!=32 or interface.ip not in ipaddress.IPv4Network('10.5.5.0/24') or int(interface.ip.packed[-1]) in (0,1,255):raise ValueError()
            ip=str(interface.ip)
        except Exception:raise ValueError('Use the device address assigned by this router, such as 10.5.5.3/32.')
    flags={key:data.get(key,False) for key in ('routerCreated','configShared','certificateInstalled','tested','routerRemoved')}
    if any(not isinstance(value,bool) for value in flags.values()):raise ValueError('Invalid checklist values.')
    if flags['routerCreated'] and (not ip or not profile):raise ValueError('Record the actual router profile name and assigned address first.')
    if flags['tested'] and not all(flags[key] for key in ('routerCreated','configShared','certificateInstalled')):raise ValueError('Record the router, configuration delivery and certificate steps before marking the test complete.')
    ident=data.get('id')
    if ident is not None and (not isinstance(ident,int) or isinstance(ident,bool)):raise ValueError('Invalid device identifier.')
    with accounts.connection() as db:
        if not db.execute('SELECT 1 FROM access_people WHERE email=?',(address,)).fetchone():raise ValueError('Save this person’s setup details first.')
        old=db.execute('SELECT * FROM vpn_devices WHERE id=? AND email=?',(ident,address)).fetchone() if ident is not None else None
        if ident is not None and not old:raise ValueError('Device not found for this person.')
        removed=flags['routerRemoved'];revoked=bool(data.get('requestRemoval',False)) or removed or bool(old and old['revoke_requested'])
        if old and old['router_removed'] and not removed:raise ValueError('Keep removed profiles as history; create a new device record for a new router profile.')
        values=(label,profile,ip or None,int(flags['routerCreated']),int(flags['configShared']),int(flags['certificateInstalled']),int(flags['tested']),int(revoked),int(removed),int(time.time()))
        try:
            if old:db.execute('UPDATE vpn_devices SET label=?,router_profile=?,address=?,router_created=?,config_shared=?,certificate_installed=?,tested=?,revoke_requested=?,router_removed=?,updated=? WHERE id=?',values+(ident,))
            else:
                cursor=db.execute('INSERT INTO vpn_devices(label,router_profile,address,router_created,config_shared,certificate_installed,tested,revoke_requested,router_removed,updated,email) VALUES(?,?,?,?,?,?,?,?,?,?,?)',values+(address,));ident=cursor.lastrowid
        except sqlite3.IntegrityError:raise ValueError('That VPN address is already recorded for another profile that has not been removed.')
        event(db,actor,address,'Device checklist saved: '+label+(' (router removal recorded)' if removed else ' (router removal required)' if revoked else ''))
    return {'id':ident}

def revoke_invite(address,actor):
    address=accounts.email(address)
    with accounts.connection() as db:
        db.execute('UPDATE invitations SET used=2 WHERE email=? AND used=0',(address,));event(db,actor,address,'Pending invitation canceled')
    return {'revoked':True}

def disable_access(address,actor):
    address=accounts.email(address)
    with accounts.connection() as db:
        db.execute('BEGIN IMMEDIATE');user=db.execute('SELECT * FROM users WHERE email=?',(address,)).fetchone()
        if not user and not db.execute('SELECT 1 FROM access_people WHERE email=?',(address,)).fetchone() and not db.execute('SELECT 1 FROM invitations WHERE email=?',(address,)).fetchone():raise ValueError('No account or setup plan exists for this email.')
        if user and user['role']=='super' and user['active']:
            if db.execute("SELECT COUNT(*) FROM users WHERE role='super' AND active=1").fetchone()[0]<=1:raise ValueError('Keep at least one active Super user.')
        if user:
            db.execute('UPDATE users SET active=0 WHERE id=?',(user['id'],));db.execute('DELETE FROM sessions WHERE user_id=?',(user['id'],))
        db.execute('UPDATE invitations SET used=2 WHERE email=? AND used=0',(address,))
        db.execute('UPDATE vpn_devices SET revoke_requested=1,updated=? WHERE email=? AND router_removed=0',(int(time.time()),address))
        event(db,actor,address,'Library access disabled; outstanding router profiles require manual removal')
    return {'disabled':True,'routerRemovalRequired':True}

def overview():
    now=int(time.time())
    with accounts.connection() as db:
        users={r['email']:dict(r) for r in db.execute('SELECT id,email,role,active FROM users')}
        people={r['email']:dict(r) for r in db.execute('SELECT * FROM access_people')}
        invites={r['email']:dict(r) for r in db.execute('SELECT email,role,expires,used FROM invitations')}
        devices=[dict(r) for r in db.execute('SELECT * FROM vpn_devices ORDER BY id')]
        events=[dict(r) for r in db.execute('SELECT actor,email,event,created FROM access_events ORDER BY id DESC LIMIT 100')]
    result=[]
    for address in sorted(set(users)|set(people)|set(invites)):
        person=people.get(address,{'email':address,'mode':'local','planned_role':users.get(address,invites.get(address,{})).get('role','user')})
        invite=invites.get(address)
        person['user']=users.get(address)
        person['invitation']=None if not invite else {'status':'accepted' if invite['used']==1 else 'canceled' if invite['used']==2 else 'expired' if invite['expires']<=now else 'pending','expires':invite['expires'],'role':invite['role']}
        person['devices']=[d for d in devices if d['email']==address];result.append(person)
    return {'people':result,'events':events,'endpoint':'vpn.discerntechnologies.com:51820','libraryUrl':'https://192.168.1.64/','routerUrl':'http://192.168.1.1/'}
