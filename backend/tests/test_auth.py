import asyncio
from datetime import timedelta

import pytest

from app.core.exceptions import CredentialException, ForbiddenException
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    require_roles,
    verify_password,
)
from app.utils.payload import Payload
from app.utils.role import Role


DATA = {"sub": "7", "profile_id": 3, "role": "teacher"}


def test_password_di_hash_tidak_sama_dengan_aslinya_dan_bisa_diverifikasi():
    hashed = hash_password("rahasia123")
    assert hashed != "rahasia123"
    assert verify_password("rahasia123", hashed) is True
    assert verify_password("salah", hashed) is False


def test_password_sama_di_hash_dua_kali_menghasilkan_hash_berbeda():
    assert hash_password("rahasia123") != hash_password("rahasia123")


def test_token_bolak_balik_mempertahankan_seluruh_payload():
    payload = decode_access_token(create_access_token(DATA))
    assert isinstance(payload, Payload)
    assert (payload.sub, payload.profile_id, payload.role) == ("7", 3, Role.TEACHER)
    assert payload.iat is not None and payload.exp is not None


def test_token_kedaluwarsa_ditolak():
    token = create_access_token(DATA, expires_delta=timedelta(seconds=-1))
    with pytest.raises(CredentialException):
        decode_access_token(token)


def test_token_berbentuk_sembarang_ditolak():
    with pytest.raises(CredentialException):
        decode_access_token("bukan.token.valid")


def test_token_berisi_role_tidak_dikenal_ditolak():
    token = create_access_token({**DATA, "role": "kepala_sekolah"})
    with pytest.raises(CredentialException):
        decode_access_token(token)


def test_role_yang_diizinkan_dilewatkan_apa_adanya():
    dependency = require_roles(Role.TEACHER, Role.ADMIN)
    user = Payload(sub="1", profile_id=1, role=Role.TEACHER)
    assert asyncio.run(dependency(user)) is user


def test_role_yang_tidak_diizinkan_ditolak():
    dependency = require_roles(Role.TEACHER)
    user = Payload(sub="1", profile_id=1, role=Role.STUDENT)
    with pytest.raises(ForbiddenException):
        asyncio.run(dependency(user))
