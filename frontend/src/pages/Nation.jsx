import { Globe2 } from 'lucide-react'
import { PdfDynPage } from './Republic'

// Respublika dinamikasi: barcha viloyatlar (R-Dynamic PDF) — reyting, Qashqadaryo qatori ajratilgan, jadval rasmlari.
export default function Nation() {
  return <PdfDynPage base="/nation" perm="nation" tab="nation" fileLabel="Respublika_dinamikasi" scope="Respublika" title="Respublika dinamikasi"
    rank images Icon={Globe2} origHint="Respublika markazi yuborgan asl R-Dynamic PDF fayl" note="respublika PDF'i bo'yicha" />
}
