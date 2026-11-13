export function formatDuration(value) {
  const total = Math.ceil(Math.abs(Number(value)));
  if (!Number.isFinite(total)) return '—';
  const days = Math.floor(total / 1440);
  const hours = Math.floor((total % 1440) / 60);
  const minutes = total % 60;
  const parts = [];
  if (days) parts.push(`${days} ${days === 1 ? 'día' : 'días'}`);
  if (hours) parts.push(`${hours} ${hours === 1 ? 'hora' : 'horas'}`);
  if (minutes || !parts.length) parts.push(`${minutes} min`);
  return parts.join(' ');
}
