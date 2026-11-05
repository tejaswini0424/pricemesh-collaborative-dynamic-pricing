import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from .database import DATA_DIR, LoginSession, User, get_db

def secret_key():
    value=os.getenv('JWT_SECRET')
    if value:
        if len(value)<32: raise RuntimeError('JWT_SECRET must have at least 32 characters')
        return value.encode()
    if os.getenv('APP_ENV')=='production': raise RuntimeError('JWT_SECRET is required in production')
    path=DATA_DIR/'.jwt-secret'
    try:
        with path.open('x',encoding='utf8') as f: f.write(secrets.token_urlsafe(48))
    except FileExistsError: pass
    return path.read_text().encode()

SECRET=secret_key()
def b64(data): return base64.urlsafe_b64encode(data).rstrip(b'=').decode()
def unb64(data): return base64.urlsafe_b64decode(data+'='*(-len(data)%4))
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def hash_password(password):
    salt=secrets.token_bytes(16)
    derived=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000)
    return f'pbkdf2_sha256$600000${b64(salt)}${b64(derived)}'
def verify_password(password,stored):
    try:
        _,rounds,salt,value=stored.split('$')
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),unb64(salt),int(rounds))
        return hmac.compare_digest(actual,unb64(value))
    except (ValueError,TypeError): return False
DUMMY_PASSWORD_HASH=hash_password('unusable-'+secrets.token_urlsafe(32))
def access_token(user_id,session_id):
    header=b64(b'{"alg":"HS256","typ":"JWT"}')
    body=b64(json.dumps(dict(sub=user_id,sid=session_id,iss='pricemesh',aud='pricemesh-api',exp=int(time.time())+1800),separators=(',',':')).encode())
    signature=b64(hmac.new(SECRET,f'{header}.{body}'.encode(),hashlib.sha256).digest())
    return f'{header}.{body}.{signature}'
def decode_token(token):
    try:
        header,payload,signature=token.split('.')
        expected=hmac.new(SECRET,f'{header}.{payload}'.encode(),hashlib.sha256).digest()
        if not hmac.compare_digest(unb64(signature),expected): raise ValueError()
        if json.loads(unb64(header)) != {'alg':'HS256','typ':'JWT'}: raise ValueError()
        data=json.loads(unb64(payload))
        if data['exp']<=time.time() or data['iss']!='pricemesh' or data['aud']!='pricemesh-api': raise ValueError()
        return data
    except Exception: raise HTTPException(401,'Invalid or expired session')
def current_user(request:Request,db=Depends(get_db)):
    token=request.headers.get('authorization','')
    if not token.startswith('Bearer '): raise HTTPException(401,'Sign in to continue')
    data=decode_token(token[7:])
    session=db.get(LoginSession,data['sid'])
    user=db.get(User,data['sub'])
    if not user or not user.active or not session or session.user_id!=user.id or session.revoked or session.expires_at<=time.time():
        raise HTTPException(401,'Session revoked or expired')
    return user
