"""
Dépendances d'authentification de la console Super Admin (base Master).

Le contrôle est volontairement distinct de celui des utilisateurs de cabinet :
un Super Admin n'a pas de `tenant_id`, et un token de cabinet ne doit jamais
donner accès à la console Master. On vérifie donc explicitement le rôle plutôt que
de se contenter de la présence d'un `sub`.
"""

import uuid
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.database import get_master_db
from src.core.exceptions import AuthenticationException, PermissionDeniedException
from src.core.security import decode_token
from src.modules.master.models import SuperAdmin


def _extraire_token(request: Request) -> str | None:
    """Bearer prioritaire, cookie en repli (même convention que le login tenant)."""
    authorization = request.headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return request.cookies.get("master_access_token")


async def get_super_admin_token(request: Request) -> dict:
    """Extrait et valide le JWT porteur du rôle SUPER_ADMIN."""
    token = _extraire_token(request)
    if not token:
        raise AuthenticationException("Authentification requise.", code="AUTHENTICATION_REQUIRED")

    payload = decode_token(token)

    if payload.get("type") != "access":
        raise AuthenticationException("Type de jeton invalide : un access token est requis.")

    role = payload.get("role")
    # Un token de cabinet (tenant_id présent) n'est jamais accepté ici, même si
    # son rôle forgeait SUPER_ADMIN.
    if role != "SUPER_ADMIN" or payload.get("tenant_id"):
        raise AuthenticationException("Accès réservé à la console d'administration.", code="SUPER_ADMIN_REQUIRED")

    return payload


async def get_current_super_admin(
    request: Request,
    payload: dict = Depends(get_super_admin_token),
    db: AsyncSession = Depends(get_master_db),
) -> SuperAdmin:
    """
    Exige un Super Admin authentifié et encore actif.

    Erreur volontairement indistincte entre token absent, invalide, rôle
    insuffisant et compte désactivé : un attaquant ne doit pas pouvoir
    distinguer « token valide mais mauvais rôle » de « token absent ».
    """
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationException("Jeton invalide.", code="TOKEN_INVALID")

    try:
        uuid_user = uuid.UUID(str(user_id))
    except ValueError:
        raise AuthenticationException("Jeton invalide.", code="TOKEN_INVALID")

    admin = (
        await db.execute(select(SuperAdmin).where(SuperAdmin.id == uuid_user))
    ).scalar_one_or_none()

    if admin is None or not admin.actif:
        raise AuthenticationException("Accès refusé.", code="AUTHENTICATION_REQUIRED")

    return admin


def exiger_role(expected: str):
    """
    Garde générique de rôle, utilisable si l'on introduit plusieurs niveaux de
    console (lecture seule, exploitation, etc.).

    `get_current_super_admin` couvre déjà le cas SUPER_ADMIN ; cette fonction
    existe pour que l'ajout de rôles plus fins reste explicite.
    """

    def _garde(admin: SuperAdmin = Depends(get_current_super_admin)) -> SuperAdmin:
        if getattr(admin, "role", "SUPER_ADMIN") != expected:
            raise PermissionDeniedException("Permission insuffisante pour la console Master.")
        return admin

    return _garde
