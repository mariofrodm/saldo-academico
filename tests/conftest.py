import os
import subprocess
import sys
import uuid
from urllib.parse import urlsplit, urlunsplit
import psycopg
from psycopg import sql
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope='session',autouse=True)
def isolated_database():
    original=os.environ['DATABASE_URL']
    parsed=urlsplit(original)
    name='saldo_test_'+uuid.uuid4().hex[:12]
    admin_url=urlunsplit(parsed._replace(path='/postgres'))
    with psycopg.connect(admin_url,autocommit=True) as conn:
        conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    test_url=urlunsplit(parsed._replace(path='/'+name))
    os.environ['DATABASE_URL']=test_url
    try:
        subprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True)
        yield
    finally:
        os.environ['DATABASE_URL']=original
        with psycopg.connect(admin_url,autocommit=True) as conn:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


@pytest.fixture
def client(isolated_database,monkeypatch):
    from backend.db import db
    from backend.seed import seed
    from backend.main import app,attempts
    monkeypatch.setenv('APP_ENV','local')
    monkeypatch.setenv('COOKIE_SECURE','false')
    monkeypatch.delenv('GROQ_API_KEY',raising=False)
    for key in ('ADMIN_PASSWORD','DEMO_PASSWORD','BI_PASSWORD'):
        monkeypatch.setenv(key,'test-only-password-1234')
    with db() as conn:
        conn.execute('TRUNCATE audit,tool_runs,provider_calls,requests,conversations,budgets,savings,goals,payments,obligations,recurring,categories,sessions,knowledge,services,users RESTART IDENTITY CASCADE')
    attempts.clear(); seed()
    with TestClient(app,base_url='https://testserver') as instance:
        yield instance


@pytest.fixture
def auth(client):
    result=client.post('/api/v1/auth/login',json={'email':'demo@example.test','password':'test-only-password-1234'})
    assert result.status_code==200
    return {'Authorization':'Bearer '+result.json()['access_token']}


@pytest.fixture
def admin_auth(client):
    result=client.post('/api/v1/auth/login',json={'email':'admin@example.test','password':'test-only-password-1234'})
    assert result.status_code==200
    return {'Authorization':'Bearer '+result.json()['access_token']}
