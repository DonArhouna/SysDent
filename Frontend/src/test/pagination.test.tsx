import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Pagination } from '@/components/ui/pagination'

/**
 * La barre de pagination est aujourd'hui partagée par les patients, les
 * fournisseurs et les commandes : un défaut ici se reproduit sur plusieurs
 * écrans, ce qui justifie un test propre.
 */

const META = {
  page: 1,
  limit: 20,
  total_records: 45,
  total_pages: 3,
  has_next: true,
  has_previous: false,
}

describe('Pagination', () => {
  it('ne rend rien quand il n’y a rien à compter', () => {
    const { container } = render(
      <Pagination meta={undefined} page={1} limit={20} onPageChange={() => {}} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('affiche le décompte et masque les boutons sur une seule page', () => {
    // Le décompte reste visible même sur une page unique : « 3 sur 3 » informe,
    // un tableau vide sans rien dire fait douter l'utilisateur de la requête.
    const { container } = render(
      <Pagination
        meta={{ ...META, total_records: 3, total_pages: 1, has_next: false }}
        page={1}
        limit={20}
        onPageChange={() => {}}
        libelle="fournisseurs"
      />,
    )
    // Le texte est réparti sur plusieurs `<span>` (les nombres sont mis en valeur),
    // donc on lit le `textContent` du paragraphe. Première page de 3 éléments :
    // « de 1 à 3 » — les bornes se calculent, elles ne sont pas recopiées.
    expect(container.querySelector('p')?.textContent).toBe(
      'Affichage de 1 à 3 sur 3 fournisseurs',
    )
    expect(screen.queryByRole('button', { name: /Suivant/ })).not.toBeInTheDocument()
  })

  it('désactive « Précédent » en première page et « Suivant » en dernière', async () => {
    const surPage = vi.fn()
    const { rerender } = render(
      <Pagination meta={META} page={1} limit={20} onPageChange={surPage} />,
    )
    expect(screen.getByRole('button', { name: /Précédent/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Suivant/ })).toBeEnabled()

    await userEvent.click(screen.getByRole('button', { name: /Suivant/ }))
    expect(surPage).toHaveBeenCalledWith(2)

    rerender(
      <Pagination
        meta={{ ...META, page: 3, has_next: false, has_previous: true }}
        page={3}
        limit={20}
        onPageChange={surPage}
      />,
    )
    expect(screen.getByRole('button', { name: /Suivant/ })).toBeDisabled()
  })

  it('récupère l’utilisateur si la page demandée n’existe plus', () => {
    // Les données ont disparu entre deux requêtes : la page 12 d'un fichier
    // réduit à 3 pages. Rester dessus afficherait un tableau vide sans explication.
    const surPageHorsBornes = vi.fn()
    render(
      <Pagination
        meta={{ ...META, total_pages: 3 }}
        page={12}
        limit={20}
        onPageChange={() => {}}
        onPageHorsBornes={surPageHorsBornes}
      />,
    )
    expect(surPageHorsBornes).toHaveBeenCalled()
  })
})