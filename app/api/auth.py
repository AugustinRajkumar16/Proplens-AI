# app/api/auth.py
from ninja import Router
from pydantic import BaseModel
import jwt
import os
import datetime

router = Router()
SECRET = os.getenv('JWT_SECRET', 'supersecret')

class LoginIn(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str

@router.post('/login/', response=TokenOut)
def login(request, payload: LoginIn):
    # NOTE: Replace with real user validation (Django auth)
    if payload.username == 'demo' and payload.password == 'demo':
        now = datetime.datetime.utcnow()
        token = jwt.encode({'sub': payload.username, 'exp': now + datetime.timedelta(hours=8)}, SECRET, algorithm='HS256')
        return {'access_token': token}
    return request.json_response({'detail': 'Invalid credentials'}, status=401)

# Simple dependency to validate token
from ninja.security import HttpBearer
class JWTBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            payload = jwt.decode(token, SECRET, algorithms=['HS256'])
            return payload['sub']
        except Exception:
            return None