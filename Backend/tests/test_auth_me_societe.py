"""
`/auth/me` rend deux noms distincts :

- `societe_nom` : la société, en base master, que la console renomme ;
- `cabinet_nom` : le site, en base du tenant.

Avant `societe_nom`, renommer un cabinet depuis la console ne changeait rien
dans l'application : la barre latérale lisait le nom du site.
"""

from src.modules.auth import router as auth_router


async def test_me_rend_le_nom_de_la_societe_et_celui_du_site(client_authenticated, cabinet, monkeypatch):
    async def _identite(_tenant_id):
        return "Clinique Renommée", "/api/v1/logos/t1?v=2"

    monkeypatch.setattr(auth_router, "_identite_cabinet", _identite)

    r = await client_authenticated.get("/api/v1/auth/me")
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert data["societe_nom"] == "Clinique Renommée"
    assert data["cabinet_logo_url"] == "/api/v1/logos/t1?v=2"
    assert data["cabinet_nom"] == cabinet["cabinet"].nom


async def test_me_sans_base_master_ne_casse_pas(client_authenticated, monkeypatch):
    async def _identite(_tenant_id):
        return None, None

    monkeypatch.setattr(auth_router, "_identite_cabinet", _identite)

    r = await client_authenticated.get("/api/v1/auth/me")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["societe_nom"] is None
