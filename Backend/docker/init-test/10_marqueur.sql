-- Base-témoin de l'instance de tests.
--
-- Son existence est la **seule** preuve qu'une instance a été provisions
-- volontairement pour les tests. `tests/conftest.py` la vérifie au démarrage de
-- chaque session et refuse de s'exécuter si elle est absente : c'est ce qui
-- empêche une session de tests de viser une instance de développement, quel que
-- soit le contenu de `TEST_DATABASE_URL`.
--
-- Le nom est fixe et volontairement distinct des noms de production : rien de
-- réel ne porte ce nom, et rien de jetable ne le portera.

CREATE DATABASE sysdent_instance_test_marker;

COMMENT ON DATABASE sysdent_instance_test_marker IS
    'Marqueur d''instance dediee aux tests. Ne pas utiliser ailleurs.';