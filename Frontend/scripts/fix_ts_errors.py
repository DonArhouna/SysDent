"""Correctif global des erreurs TypeScript du frontend SysDent.

Trois familles :
1. `.data.data` -> `.data` : les services retournent deja l'enveloppe APIResponse.
   (Ne touche PAS dashboard.tsx ou les composants useQuery ou `.data.data` est legitime.)
2. `res.data.items` / `res.data.meta` -> `res.items` / `res.meta` (PaginatedResponse deja depliee).
3. Imports / variables locales inutilises (TS6133/TS6196).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"

# ---------------------------------------------------------------------------
# 1. Double depliage : les services facturation/rbac/ordonnances retournent
#    deja APIResponse<T>, donc `res.data.data` doit devenir `res.data`.
#    Exclusions : dashboard.tsx et tout composant qui consomme le `.data`
#    d'un useQuery (resultat TanStack) — non listes ci-dessous.
# ---------------------------------------------------------------------------
FICHIERS_DATA_DATA = [
    "features/facturation/components/devis-modal.tsx",
    "features/facturation/components/echelonnement-modal.tsx",
    "features/facturation/components/paiement-modal.tsx",
    "features/facturation/pages/devis-list-page.tsx",
    "features/facturation/pages/facture-detail-page.tsx",
    "features/ordonnances/components/medicament-modal.tsx",
    "features/ordonnances/components/ordonnance-modal.tsx",
    "features/ordonnances/pages/ordonnances-list-page.tsx",
    "features/rbac/components/permission-matrix.tsx",
    "features/rbac/components/role-modal.tsx",
    "features/rbac/pages/roles-page.tsx",
]

for rel in FICHIERS_DATA_DATA:
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    avant = s.count(".data.data")
    s = s.replace(".data.data", ".data")
    p.write_text(s, encoding="utf-8", newline="\n")
    print(f"[data.data] {rel}: {avant} remplacement(s)")

# ---------------------------------------------------------------------------
# 2. PaginatedResponse deja depliee : `res.data.items` -> `res.items`,
#    `res.data.meta` -> `res.meta` (audit-page : res = api.get direct).
# ---------------------------------------------------------------------------
p = ROOT / "features/audit/pages/audit-page.tsx"
s = p.read_text(encoding="utf-8")
s = s.replace("res.data.items", "res.items").replace("res.data.meta", "res.meta")
p.write_text(s, encoding="utf-8", newline="\n")
print("[paginated] audit-page.tsx corrige")

# facture-detail : echelonnement peut etre null -> garde
p = ROOT / "features/facturation/pages/facture-detail-page.tsx"
s = p.read_text(encoding="utf-8")
s = s.replace(
    "setEchelonnement(resEchelonnement.data)",
    "setEchelonnement(resEchelonnement.data ?? null)",
)
p.write_text(s, encoding="utf-8", newline="\n")
print("[null-guard] facture-detail-page.tsx corrige")

# ---------------------------------------------------------------------------
# 3. Imports / variables inutilises — retraits chirurgicaux.
# ---------------------------------------------------------------------------
def retirer(texte: str, motif: str, remplacement: str = "") -> str:
    if motif not in texte:
        print(f"  !! introuvable: {motif[:60]!r}")
        return texte
    return texte.replace(motif, remplacement, 1)


edits: list[tuple[str, str, str]] = [
    # audit-page : Eye inutilise ; totalRecords lu mais jamais affiche -> garder setter seulement
    ("features/audit/pages/audit-page.tsx",
     "import { ChevronDown, ChevronRight, Eye, ShieldAlert, User } from 'lucide-react'",
     "import { ChevronDown, ChevronRight, ShieldAlert, User } from 'lucide-react'"),
    ("features/audit/pages/audit-page.tsx",
     "  const [totalRecords, setTotalRecords] = useState(0)",
     "  const [, setTotalRecords] = useState(0)"),

    # consultations-list : imports lucide inutilises + type Consultation
    ("features/consultations/pages/consultations-list-page.tsx",
     "  Stethoscope,\n  Plus,\n  RefreshCw,\n  Search,\n  Filter,\n  FileText,\n  Calendar,\n  Clock,\n  User,\n",
     "  Stethoscope,\n  Plus,\n  RefreshCw,\n"),
    ("features/consultations/pages/consultations-list-page.tsx",
     "import type { Consultation, StatutConsultation } from '../types'",
     "import type { StatutConsultation } from '../types'"),
    # consultations-list : page/setPage — setPage inutilise (pagination via data.meta non affichee)
    ("features/consultations/pages/consultations-list-page.tsx",
     "  const [page, setPage] = useState(1)\n",
     "  const [page] = useState(1)\n"),
    ("features/consultations/pages/consultations-list-page.tsx",
     "  const [cabinetId, setCabinetId] = useState(cabinetActifId ?? '')",
     "  const [cabinetId] = useState(cabinetActifId ?? '')"),
    ("features/consultations/pages/consultations-list-page.tsx",
     "  const consultations = data?.items ?? []\n  const meta = data?.meta\n",
     "  const consultations = data?.items ?? []\n"),

    # consultation-detail : Clock inutilise, refetch inutilise
    ("features/consultations/pages/consultation-detail-page.tsx",
     "  Save,\n  Clock,\n  ClipboardList,\n",
     "  Save,\n  ClipboardList,\n"),
    ("features/consultations/pages/consultation-detail-page.tsx",
     "  const { data: resDetail, isLoading, refetch } = useQuery({",
     "  const { data: resDetail, isLoading } = useQuery({"),

    # facture-detail : CheckCircle2/Clock inutilises, navigate inutilise
    ("features/facturation/pages/facture-detail-page.tsx",
     "  ArrowLeft,\n  Ban,\n  Calendar,\n  CheckCircle2,\n  Clock,\n  CreditCard,\n  Layers,\n  Printer,\n",
     "  ArrowLeft,\n  Ban,\n  Calendar,\n  CreditCard,\n  Layers,\n  Printer,\n"),
    ("features/facturation/pages/facture-detail-page.tsx",
     "import { Link, useNavigate, useParams } from 'react-router-dom'",
     "import { Link, useParams } from 'react-router-dom'"),
    ("features/facturation/pages/facture-detail-page.tsx",
     "  const navigate = useNavigate()\n", ""),

    # devis-list : FileText/Trash2 inutilises, STATUT_DEVIS_OPTIONS inutilise, selectedDevis inutilise
    ("features/facturation/pages/devis-list-page.tsx",
     "  ArrowRight,\n  CheckCircle2,\n  FileCheck,\n  FileSpreadsheet,\n  FileText,\n  Plus,\n  Send,\n  Trash2,\n  XCircle,\n",
     "  ArrowRight,\n  CheckCircle2,\n  FileCheck,\n  FileSpreadsheet,\n  Plus,\n  Send,\n  XCircle,\n"),
    ("features/facturation/pages/devis-list-page.tsx",
     "const STATUT_DEVIS_OPTIONS = [\n  { value: '', label: 'Tous les devis' },\n  { value: 'BROUILLON', label: 'Brouillon' },\n  { value: 'ENVOYE', label: 'Envoyé au patient' },\n  { value: 'ACCEPTE', label: 'Accepté / Signé' },\n  { value: 'REFUSE', label: 'Refusé' },\n  { value: 'EXPIRE', label: 'Expiré' },\n]\n\n", ""),
    ("features/facturation/pages/devis-list-page.tsx",
     "  const [selectedDevis, setSelectedDevis] = useState<DevisResponse | null>(null)\n", ""),

    # devis-modal : FileText inutilise
    ("features/facturation/components/devis-modal.tsx",
     "import { FileText, Plus, Trash2 } from 'lucide-react'",
     "import { Plus, Trash2 } from 'lucide-react'"),

    # echelonnement-modal : Calendar inutilise
    ("features/facturation/components/echelonnement-modal.tsx",
     "import { Calendar, Layers } from 'lucide-react'",
     "import { Layers } from 'lucide-react'"),

    # paiement-modal : ligne d'imports entierement inutilisee
    ("features/facturation/components/paiement-modal.tsx",
     "import { CheckCircle2, CreditCard, DollarSign, Smartphone } from 'lucide-react'\n", ""),

    # journal-caisse : formatDateFr, Calendar, FileText, Search inutilises ; page/setPage
    ("features/facturation/pages/journal-caisse-page.tsx",
     "import { formatFcfa, formatDateFr, formatDateTimeFr } from '@/lib/format'",
     "import { formatFcfa, formatDateTimeFr } from '@/lib/format'"),
    ("features/facturation/pages/journal-caisse-page.tsx",
     "  ArrowLeft,\n  Banknote,\n  Calendar,\n  CreditCard,\n  FileText,\n  Printer,\n  Search,\n  Smartphone,\n",
     "  ArrowLeft,\n  Banknote,\n  CreditCard,\n  Printer,\n  Smartphone,\n"),
    ("features/facturation/pages/journal-caisse-page.tsx",
     "  const [page, setPage] = useState(1)\n",
     "  const [page] = useState(1)\n"),

    # odontogramme-page : Search/Activity/HeartPulse inutilises
    ("features/odontogramme/pages/odontogramme-page.tsx",
     "  ClipboardList,\n  RefreshCw,\n  ArrowLeft,\n  Search,\n  Activity,\n  User,\n  HeartPulse,\n  Plus,\n",
     "  ClipboardList,\n  RefreshCw,\n  ArrowLeft,\n  User,\n  Plus,\n"),

    # medicament-modal : setPrecautions inutilise (champ en lecture seule ? non —
    # le setter est omis dans la destructuration du state ; on prefixe par underscore)
    ("features/ordonnances/components/medicament-modal.tsx",
     "  const [precautions, setPrecautions] = useState('')",
     "  const [precautions] = useState('')"),

    # ordonnance-modal : AlertCircle inutilise
    ("features/ordonnances/components/ordonnance-modal.tsx",
     "import { AlertCircle, AlertTriangle, CheckCircle2, Plus, ShieldAlert, Trash2 } from 'lucide-react'",
     "import { AlertTriangle, CheckCircle2, Plus, ShieldAlert, Trash2 } from 'lucide-react'"),

    # praticiens : AlertTriangle inutilise, type Praticien inutilise
    ("features/praticiens/pages/praticiens-page.tsx",
     "  ShieldCheck,\n  Calendar,\n  AlertTriangle,\n",
     "  ShieldCheck,\n  Calendar,\n"),
    ("features/praticiens/pages/praticiens-page.tsx",
     "import type { Disponibilite, Praticien } from '../types'",
     "import type { Disponibilite } from '../types'"),

    # rbac permission-matrix : Button et X inutilises
    ("features/rbac/components/permission-matrix.tsx",
     "import { Button } from '@/components/ui/button'\n", ""),
    ("features/rbac/components/permission-matrix.tsx",
     "import { Check, Lock, ShieldCheck, X } from 'lucide-react'",
     "import { Check, Lock, ShieldCheck } from 'lucide-react'"),

    # rdv-form-modal : Badge inutilise
    ("features/rendezvous/components/rdv-form-modal.tsx",
     "import { Badge } from '@/components/ui/badge'\n", ""),

    # agenda : User et RotateCcw inutilises ; import Card entierement inutilise
    ("features/rendezvous/pages/agenda-page.tsx",
     "  Clock,\n  User,\n  Armchair,\n",
     "  Clock,\n  Armchair,\n"),
    ("features/rendezvous/pages/agenda-page.tsx",
     "  Play,\n  RotateCcw,\n",
     "  Play,\n"),
    ("features/rendezvous/pages/agenda-page.tsx",
     "import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'\n", ""),

    # stock-page : Select (composant) et Calendar inutilises
    ("features/stock/pages/stock-page.tsx",
     "import { Select } from '@/components/ui/select'\n", ""),
    ("features/stock/pages/stock-page.tsx",
     "  Boxes,\n  Calendar,\n  Clock,\n",
     "  Boxes,\n  Clock,\n"),
]

for rel, avant, apres in edits:
    p = ROOT / rel
    s = p.read_text(encoding="utf-8")
    if avant not in s:
        print(f"  !! introuvable dans {rel}: {avant[:60]!r}")
        continue
    s = s.replace(avant, apres, 1)
    p.write_text(s, encoding="utf-8", newline="\n")
    print(f"[import] {rel} corrige")

print("\nTermine.")
