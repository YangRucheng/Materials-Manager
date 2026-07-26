const UUID_PATTERN = /[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i;
const COMPACT_UUID_PATTERN = /(?:^|[^0-9a-f])([0-9a-f]{12}[1-5][0-9a-f]{3}[89ab][0-9a-f]{15})(?=$|[^0-9a-f])/i;

function extractMaterialUuid(value) {
  let source = String(value || '');
  try {
    source = decodeURIComponent(source);
  } catch (_error) {
    source = String(value || '');
  }
  const standardMatch = source.match(UUID_PATTERN);
  if (standardMatch) {
    return standardMatch[0].toLowerCase();
  }
  const compactMatch = source.match(COMPACT_UUID_PATTERN);
  if (!compactMatch) {
    return '';
  }
  const uuid = compactMatch[1].toLowerCase();
  return `${uuid.slice(0, 8)}-${uuid.slice(8, 12)}-${uuid.slice(12, 16)}-${uuid.slice(16, 20)}-${uuid.slice(20)}`;
}

function createClientRequestId() {
  return `mp-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

module.exports = {
  createClientRequestId,
  extractMaterialUuid,
};
