const LOCAL_KEYS = {
  apiUrl: 'ff_api_url',
  apiKey: 'ff_api_key',
};

const SESSION_KEYS = {
  draft: 'ff_builder_draft',
  picker: 'ff_picker_state',
  pickResult: 'ff_picker_result',
};

const sessionStorageArea = chrome.storage.session || chrome.storage.local;

function normalizeApiUrl(apiUrl) {
  return (apiUrl || '').trim().replace(/\/+$/, '');
}

function buildHeaders(apiKey) {
  const headers = { 'Content-Type': 'application/json' };
  if (apiKey && apiKey.trim()) {
    headers['X-API-Key'] = apiKey.trim();
  }
  return headers;
}

async function readStorage(area, keys) {
  return area.get(keys);
}

async function writeStorage(area, values) {
  await area.set(values);
}

async function removeStorage(area, keys) {
  await area.remove(keys);
}

async function handleTestConnection({ apiUrl, apiKey }) {
  const baseUrl = normalizeApiUrl(apiUrl);
  if (!baseUrl) {
    return { ok: false, error: 'API Base URL is required.' };
  }

  const response = await fetch(`${baseUrl}/api/config/scrape-templates`, {
    method: 'GET',
    headers: buildHeaders(apiKey),
  });

  if (!response.ok) {
    const text = await response.text();
    return { ok: false, error: `HTTP ${response.status}: ${text}` };
  }

  const data = await response.json();
  return { ok: true, count: Array.isArray(data?.items) ? data.items.length : 0 };
}

async function handleSaveTemplate({ apiUrl, apiKey, payload }) {
  const baseUrl = normalizeApiUrl(apiUrl);
  if (!baseUrl) {
    return { ok: false, error: 'API Base URL is required.' };
  }

  const response = await fetch(`${baseUrl}/api/config/scrape-templates`, {
    method: 'POST',
    headers: buildHeaders(apiKey),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const text = await response.text();
    return { ok: false, error: `HTTP ${response.status}: ${text}` };
  }

  const data = await response.json();
  return { ok: true, data };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.action === 'testConnection') {
    handleTestConnection(message)
      .then((result) => sendResponse(result))
      .catch((error) => sendResponse({ ok: false, error: error.message || 'Connection test failed.' }));
    return true;
  }

  if (message?.action === 'saveTemplate') {
    handleSaveTemplate(message)
      .then(async (result) => {
        if (result.ok) {
          await removeStorage(sessionStorageArea, [SESSION_KEYS.draft, SESSION_KEYS.pickResult]);
        }
        sendResponse(result);
      })
      .catch((error) => sendResponse({ ok: false, error: error.message || 'Save failed.' }));
    return true;
  }

  if (message?.action === 'selectorPicked') {
    writeStorage(sessionStorageArea, {
      [SESSION_KEYS.pickResult]: {
        fieldKey: message.fieldKey,
        selector: message.selector,
        pickedAt: Date.now(),
      },
      [SESSION_KEYS.picker]: {
        activeFieldKey: null,
        activeTabId: sender?.tab?.id ?? null,
      },
    })
      .catch(() => null);
    return false;
  }

  if (message?.action === 'pickingCancelled') {
    writeStorage(sessionStorageArea, {
      [SESSION_KEYS.picker]: {
        activeFieldKey: null,
        activeTabId: sender?.tab?.id ?? null,
      },
    })
      .catch(() => null);
    return false;
  }

  if (message?.action === 'persistBuilderDraft') {
    writeStorage(sessionStorageArea, {
      [SESSION_KEYS.draft]: message.draft,
    })
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: error.message || 'Failed to persist draft.' }));
    return true;
  }

  if (message?.action === 'savePickerState') {
    writeStorage(sessionStorageArea, {
      [SESSION_KEYS.picker]: {
        activeFieldKey: message.activeFieldKey ?? null,
        activeTabId: message.activeTabId ?? null,
      },
    })
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: error.message || 'Failed to store picker state.' }));
    return true;
  }

  if (message?.action === 'loadExtensionState') {
    readStorage(sessionStorageArea, [SESSION_KEYS.draft, SESSION_KEYS.picker, SESSION_KEYS.pickResult])
      .then(async (sessionValues) => {
        const localValues = await readStorage(chrome.storage.local, [LOCAL_KEYS.apiUrl, LOCAL_KEYS.apiKey]);
        sendResponse({
          ok: true,
          settings: {
            apiUrl: localValues[LOCAL_KEYS.apiUrl] || '',
            apiKey: localValues[LOCAL_KEYS.apiKey] || '',
          },
          draft: sessionValues[SESSION_KEYS.draft] || null,
          picker: sessionValues[SESSION_KEYS.picker] || null,
          pickResult: sessionValues[SESSION_KEYS.pickResult] || null,
        });
      })
      .catch((error) => sendResponse({ ok: false, error: error.message || 'Failed to load state.' }));
    return true;
  }

  if (message?.action === 'clearPickResult') {
    removeStorage(sessionStorageArea, [SESSION_KEYS.pickResult])
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: error.message || 'Failed to clear pick result.' }));
    return true;
  }

  return false;
});
