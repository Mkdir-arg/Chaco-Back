const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

export const dateKey = (value) => {
  if (!value) return '';

  if (typeof value === 'string') {
    const dateOnly = value.match(DATE_ONLY_PATTERN);
    if (dateOnly) return value;
  }

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return '';

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

export const formatDate = (value, { includeTime = false } = {}) => {
  if (!value) return '-';

  if (typeof value === 'string') {
    const dateOnly = value.match(DATE_ONLY_PATTERN);
    if (dateOnly) {
      const [, year, month, day] = dateOnly;
      return `${day}/${month}/${year}`;
    }
  }

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);

  const options = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  };
  if (includeTime) {
    options.hour = '2-digit';
    options.minute = '2-digit';
  }
  return date.toLocaleString('es-AR', options);
};
