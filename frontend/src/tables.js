// Uch dinamika jadvalining tuzilishi (sarlavhalar va ustunlar)
// Ustun turlari: n = son (bosiladi), p = foiz, d = dinamika (↑↓)
const n = (m, kind, cls = '') => ({ t: 'n', m, kind, cls })
const d = (m, pol) => ({ t: 'd', m, pol })
const p = (num, den) => ({ t: 'p', num, den })
const H = (l, o = {}) => ({ l, ...o })

// pol: bad  = o'sish yomon (qizil ↑, ko'k ↓)
//      mid  = o'sish ko'k, kamayish qizil
//      good = o'sish yashil, kamayish qizil
export const TABLES = {
  konsentrator: {
    title: "hududida CAS dasturida mavjud konsentratorlar holati bo'yicha",
    short: 'Konsentratorlar',
    perm: 'view.konsentrator',
    drill: 'tr',
    head: [
      [H('Hudud nomi', { rs: 3, c: 'h-name' }), H('Dasturda mavjud transformatorlar soni', { rs: 3, c: 'vert' }),
        H('Konsentratorlar', { cs: 5 }), H("Konsentratorlarning obxod olish darajasi bo'yicha soni", { cs: 10, c: 'blue' }),
        H("Iste'molchi biriktirilmagan konsentratorlar soni", { rs: 3, c: 'vert red' })],
      [H('CAS ga yuklangan', { rs: 2, c: 'vert' }), H('shundan', { cs: 4, c: 'sub' }),
        H('0%', { cs: 2 }), H('1-30%', { cs: 2 }), H('30-50%', { cs: 2 }), H('50-80%', { cs: 2 }), H('80-100%', { cs: 2 })],
      [H('Online', { c: 'green' }), H('Offline (jami)', { c: 'red' }), H('shundan 3 kundan ortiq', { c: 'red' }), H('↑↓', { c: 'arr' }),
        ...Array.from({ length: 5 }, () => [H('soni', { c: 'red s' }), H('↑↓', { c: 'arr' })]).flat()],
    ],
    cols: [
      n('tp_total', 'tr', 'b'), n('cas_loaded', 'tr', 'b'), n('online', 'tr', 'green'), n('offline', 'tr', 'red'), n('offline3', 'tr', 'red'), d('offline', 'bad'),
      n('lv0', 'tr', 'red'), d('lv0', 'bad'), n('lv1', 'tr', 'red'), d('lv1', 'bad'), n('lv2', 'tr', 'red'), d('lv2', 'bad'),
      n('lv3', 'tr', 'red'), d('lv3', 'mid'), n('lv4', 'tr', 'b'), d('lv4', 'good'),
      n('unattached', 'tr', 'red'),
    ],
  },
  aloqa: {
    title: "hududida CAS dasturida aloqaga chiqmagan hisoblagichlar bo'yicha",
    short: 'Aloqadan chiqib ketgan hisoblagichlar',
    perm: 'view.aloqa',
    drill: 'meters',
    head: [
      [H('Hudud nomi', { rs: 4, c: 'h-name' }),
        H('Aloqaga chiqmay qolgan hisoblagichlar soni', { cs: 17, c: 'red' }), H('Umuman aloqaga chiqmagan hisoblagichlar', { cs: 2, rs: 2, c: 'red' }),
        H("To'g'ridan-to'g'ri ulanish (peremichka)", { cs: 2, rs: 2, c: 'purple' })],
      [H('Jami', { cs: 3 }), H("Iste'molchi turi kesimida", { cs: 6, c: 'green it' }), H('Vaqtlar kesimida', { cs: 8, c: 'blue it' })],
      [H('soni', { rs: 2, c: 'red s' }), H('%', { rs: 2, c: 's' }), H('↑↓', { rs: 2, c: 'arr' }),
        H('Aholi', { cs: 2, c: 'green' }), H('Ulgurji', { cs: 2, c: 'blue' }), H('Balans', { cs: 2, c: 'amber' }),
        H('2-7 kun', { cs: 2 }), H('7-30 kun', { cs: 2 }), H('1-3 oy', { cs: 2 }), H('3 oydan ortiq', { cs: 2 }),
        H('soni', { rs: 2, c: 'red s' }), H('↑↓', { rs: 2, c: 'arr' }), H('soni', { rs: 2, c: 's' }), H('↑↓', { rs: 2, c: 'arr' })],
      Array.from({ length: 7 }, () => [H('soni', { c: 's red' }), H('↑↓', { c: 'arr' })]).flat(),
    ],
    cols: [
      n('out_total', 'meters', 'red b'), p('out_total', 'm_total'), d('out_total', 'bad'),
      n('out_aholi', 'meters', 'b'), d('out_aholi', 'bad'), n('out_ulgurji', 'meters', 'b'), d('out_ulgurji', 'bad'), n('out_balans', 'meters', 'amber'), d('out_balans', 'bad'),
      n('out_2_7', 'meters', 'b'), d('out_2_7', 'bad'), n('out_7_30', 'meters', 'b'), d('out_7_30', 'bad'), n('out_30_90', 'meters', 'b'), d('out_30_90', 'bad'), n('out_90p', 'meters', 'b'), d('out_90p', 'bad'),
      n('m_nopoll', 'meters', 'red'), d('m_nopoll', 'bad'),
      n('m_direct', 'meters', 'purple b'), d('m_direct', 'bad'),
    ],
  },
  obxod: {
    title: 'hududida 48 soat ichida obxod bergan hisoblagichlar bo\'yicha',
    short: '48 soat obxod',
    perm: 'view.obxod',
    drill: 'meters',
    head: [
      [H('Hudud nomi', { rs: 3, c: 'h-name' }), H('Jami hisoblagichlar', { cs: 4, rs: 2 }), H('shundan', { cs: 12, c: 'sub' })],
      [H("Aholi iste'molchilari", { cs: 4, c: 'green' }), H("Ulgurji iste'molchilar", { cs: 4, c: 'amber' }), H('Balans hisoblagichlar', { cs: 4, c: 'purple' })],
      ...[[H('Jami soni', { c: 's' }), H('shundan obxod olgan', { c: 's green' }), H('%', { c: 's' }), H('↑↓', { c: 'arr' })]]
        .map((g) => [...g, ...g, ...g, ...g]),
    ],
    cols: [
      n('m_total', 'meters', 'b'), n('polled', 'meters', 'b'), p('polled', 'm_total'), d('polled', 'mid'),
      n('a_total', 'meters', ''), n('a_polled', 'meters', 'b'), p('a_polled', 'a_total'), d('a_polled', 'mid'),
      n('u_total', 'meters', ''), n('u_polled', 'meters', 'b'), p('u_polled', 'u_total'), d('u_polled', 'mid'),
      n('b_total', 'meters', ''), n('b_polled', 'meters', 'b'), p('b_polled', 'b_total'), d('b_polled', 'mid'),
    ],
  },
}

// Ro'yxat sarlavhalari (raqam ustiga bosilganda)
export const METRIC_TITLES = {
  tp_total: 'Dasturdagi barcha TP / konsentratorlar', cas_loaded: 'CAS ga yuklangan konsentratorlar', online: 'Online konsentratorlar',
  offline: 'Offline konsentratorlar', offline3: '3 kundan ortiq offline konsentratorlar',
  lv0: 'Obxod olish darajasi 0%', lv1: 'Obxod olish darajasi 1-30%', lv2: 'Obxod olish darajasi 30-50%',
  lv3: 'Obxod olish darajasi 50-80%', lv4: 'Obxod olish darajasi 80-100%', unattached: "Iste'molchi biriktirilmagan konsentratorlar",
  m_total: 'Barcha hisoblagichlar', m_conn: 'Aloqaga chiqqan hisoblagichlar (2 kun ichida)', out_total: 'Aloqaga chiqmay qolgan hisoblagichlar (2 kundan ortiq)',
  out_aholi: 'Aloqaga chiqmay qolgan — aholi', out_ulgurji: 'Aloqaga chiqmay qolgan — ulgurji', out_balans: 'Aloqaga chiqmay qolgan — balans',
  out_2_7: 'Aloqaga chiqmay qolgan: 2-7 kun', out_7_30: 'Aloqaga chiqmay qolgan: 7-30 kun', out_30_90: 'Aloqaga chiqmay qolgan: 1-3 oy', out_90p: 'Aloqaga chiqmay qolgan: 3 oydan ortiq',
  m_nopoll: 'Umuman aloqaga chiqmagan hisoblagichlar', m_direct: "To'g'ridan-to'g'ri ulangan hisoblagichlar (peremichka)", polled: '48 soat ichida obxod bergan hisoblagichlar',
  a_total: 'Aholi hisoblagichlari', a_polled: 'Aholi: 48 soat ichida obxod bergan', u_total: 'Ulgurji hisoblagichlar',
  u_polled: 'Ulgurji: 48 soat ichida obxod bergan', b_total: 'Balans hisoblagichlar', b_polled: 'Balans: 48 soat ichida obxod bergan',
}
