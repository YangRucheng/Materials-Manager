const UUID_PATTERN = /[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i;

function extractMaterialUuid(value) {
  const match = String(value || '').match(UUID_PATTERN);
  return match ? match[0].toLowerCase() : '';
}

function createClientRequestId() {
  return `mp-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

module.exports = {
  createClientRequestId,
  extractMaterialUuid,
};
