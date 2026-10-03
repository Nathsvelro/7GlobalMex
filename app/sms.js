// Observation SMS code v1 (PLAN.md §5). One SMS (<=160 chars), GSM-7 only, works on 2G.
//   CAF1 <member> <code> <conf> <yyyymmdd> <lat>,<lon>|- #<obs>
//   CAF1 M0123 ROYA 87 20261004 16.91,-92.11 #K3F9

export const CODES = {
  sano: 'SANO', roya: 'ROYA', minador: 'MINA', phoma: 'PHOM',
  cercospora: 'CERC', acaro_rojo: 'ACAR', otro: 'OTRO', duda: 'DUDA',
};

export const CODE_RE =
  /^CAF1 M\d{4} (SANO|ROYA|MINA|PHOM|CERC|ACAR|OTRO|DUDA) \d{1,2} \d{8} (-?\d{1,2}\.\d{2},-?\d{1,3}\.\d{2}|-) #[0-9A-Z]{4}$/;

export function buildCode(o) {
  const loc = o.lat != null && o.lon != null ? o.lat.toFixed(2) + ',' + o.lon.toFixed(2) : '-';
  const conf = Math.max(0, Math.min(99, Math.round(o.conf || 0)));
  const code = ['CAF1', o.member_id, o.code, conf, o.date, loc, '#' + o.obs_id].join(' ');
  if (code.length > 160 || !CODE_RE.test(code)) throw new Error('bad SMS code: ' + code);
  return code;
}

// sms: link for the phone's own SMS app. The user still has to tap Send there.
export function smsLink(number, body) {
  return 'sms:' + number + '?body=' + encodeURIComponent(body);
}

export function today() {
  const d = new Date();
  return '' + d.getFullYear() + String(d.getMonth() + 1).padStart(2, '0') + String(d.getDate()).padStart(2, '0');
}
