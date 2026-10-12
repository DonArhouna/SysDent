"""Le catalogue de permissions doit porter tout ce que le serveur exige.

**L'ecran ne peut pas inventer une permission.** `Rôles et Permissions` se
contredit de la sortie de `GET /rbac/permissions`, qui lit la table
`permissions` du cabinet. Si une permission n'y est pas, un administrateur ne
peut pas l'accorder, alors que les routes la reclament.

**Pourquoi ce defaut a survecu.** Les tests accordent les droits par programme,
via une permutation de liens, sans passer par le catalogue. Ils prouvent donc
que le code respecte les permissions, jamais qu'un administrateur peut les
attribuer. Le chemin de l'ecran n'etait jamais exerce.

**Ce que le test fixe.** Toute permission que le code peut exiger doit etre
present dans le catalogue. La comparaison se fait entre `CATALOGUE_PERMISSIONS`,
la source de verite du cote serveur, et la reponse de l'endpoint : pas de liste
redigee a la main dans le test, qui reproduirait le defaut qu'on cherche.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from src.common.permissions import CATALOGUE_PERMISSIONS, format_permission

BASE = "/api/v1/rbac"


async def _cles_du_catalogue(client: AsyncClient) -> set[str]:
    reponse = await client.get(f"{BASE}/permissions")
    assert reponse.status_code == 200, reponse.text
    return {item["cle"] for item in reponse.json()["data"]}


@pytest.mark.asyncio
async def test_le_catalogue_expose_toutes_les_permissions_du_serveur(
    client_authenticated: AsyncClient,
) -> None:
    """Aucune permission exigee par le code ne doit manquer a l'ecran."""
    attendu = {format_permission(module, action) for module, action in CATALOGUE_PERMISSIONS}
    present = await _cles_du_catalogue(client_authenticated)

    manquantes = sorted(attendu - present)
    assert not manquantes, (
        "permissions declarees par le serveur et absentes du catalogue affiche : "
        + ", ".join(manquantes)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cle",
    ["TARIFS:READ", "TARIFS:WRITE", "ASSURANCE:READ", "ASSURANCE:WRITE_PATIENT"],
)
async def test_les_quatre_permissions_de_tarification_sont_attribuables(
    client_authenticated: AsyncClient, cle: str
) -> None:
    present = await _cles_du_catalogue(client_authenticated)
    assert cle in present, f"{cle} n'est pas attribuable depuis l'ecran"


@pytest.mark.asyncio
async def test_le_catalogue_ne_contient_pas_de_permission_inconnue_du_code(
    client_authenticated: AsyncClient,
) -> None:
    """L'inverse : la table ne doit pas porter une permission que le code ignore."""
    attendu = {format_permission(module, action) for module, action in CATALOGUE_PERMISSIONS}
    present = await _cles_du_catalogue(client_authenticated)

    en_trop = sorted(present - attendu)
    assert not en_trop, "permissions en base que le code ne connait pas : " + ", ".join(en_trop)