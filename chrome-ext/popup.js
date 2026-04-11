const SELECTOR_FIELDS = [
  { key: 'product_name', label: 'Product Name' },
  { key: 'price', label: 'Price' },
  { key: 'currency', label: 'Currency' },
  { key: 'image', label: 'Image' },
  { key: 'brand', label: 'Brand' },
  { key: 'sku', label: 'SKU' },
  { key: 'in_stock', label: 'In Stock' },
  { key: 'product_links', label: 'Product Links' },
];

const LOCAL_KEYS = {
  apiUrl: 'ff_api_url',
  apiKey: 'ff_api_key',
};

const state = {
  activeTab: 'settings',
  siteHostname: '',
  activeTabId: null,
  activePickerField: null,
  settings: {
    apiUrl: '',
    apiKey: '',
  },
  builder: {
    name: '',
    parser: 'Custom selector preset',
    description: '',
    selectors: {},
    crawlRules: {
      maxPages: 100,
      maxDepth: 3,
      sameDomainOnly: true,
      respectRobotsTxt: true,
      urlPatterns: '',
      excludePatterns: '',
    },
  },
};

const elements = {};

function normalizeApiUrl(apiUrl) {
  return (apiUrl || '').trim().replace(/\/+$/, '');
}

function splitLines(value) {
  return String(value || '')
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function sendRuntimeMessage(message) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(message, (response) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve(response);
    });
  });
}

function queryActiveTab() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve(tabs[0] || null);
    });
  });
}

function sendMessageToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        reject(new Error(runtimeError.message));
        return;
      }
      resolve(response);
    });
  });
}

function showBanner({ tone, title, message, note }) {
  elements.statusBanner.hidden = false;
  elements.statusBanner.dataset.tone = tone;
  elements.statusBanner.replaceChildren();

  const titleElement = document.createElement('p');
  titleElement.className = 'status-title';
  titleElement.textContent = title;
  elements.statusBanner.appendChild(titleElement);

  if (message) {
    const messageElement = document.createElement('p');
    messageElement.className = 'status-copy';
    messageElement.textContent = message;
    elements.statusBanner.appendChild(messageElement);
  }

  if (note) {
    const noteElement = document.createElement('p');
    noteElement.className = 'status-note';
    noteElement.textContent = note;
    elements.statusBanner.appendChild(noteElement);
  }
}

function hideBanner() {
  elements.statusBanner.hidden = true;
  elements.statusBanner.innerHTML = '';
  delete elements.statusBanner.dataset.tone;
}

function setActiveTab(tabName) {
  state.activeTab = tabName;
  document.querySelectorAll('[data-tab-target]').forEach((button) => {
    button.classList.toggle('is-active', button.dataset.tabTarget === tabName);
  });
  document.querySelectorAll('[data-tab-panel]').forEach((panel) => {
    panel.classList.toggle('is-active', panel.dataset.tabPanel === tabName);
  });
}

function renderSiteHostname() {
  elements.siteHostname.textContent = state.siteHostname || 'Unavailable';
  elements.siteHostname.title = state.siteHostname || 'No active site detected';
}

function renderSettings() {
  elements.apiUrlInput.value = state.settings.apiUrl;
  elements.apiKeyInput.value = state.settings.apiKey;
}

function renderBuilder() {
  elements.templateNameInput.value = state.builder.name;
  elements.parserInput.value = state.builder.parser;
  elements.descriptionInput.value = state.builder.description;
  elements.maxPagesInput.value = String(state.builder.crawlRules.maxPages);
  elements.maxDepthInput.value = String(state.builder.crawlRules.maxDepth);
  elements.sameDomainOnlyInput.checked = state.builder.crawlRules.sameDomainOnly;
  elements.respectRobotsInput.checked = state.builder.crawlRules.respectRobotsTxt;
  elements.urlPatternsInput.value = state.builder.crawlRules.urlPatterns;
  elements.excludePatternsInput.value = state.builder.crawlRules.excludePatterns;

  SELECTOR_FIELDS.forEach(({ key }) => {
    const selectorInput = elements.selectorInputs[key];
    const pickButton = elements.pickButtons[key];
    selectorInput.value = state.builder.selectors[key] || '';
    pickButton.textContent = state.activePickerField === key ? 'Picking...' : 'Pick';
    pickButton.classList.toggle('is-picking', state.activePickerField === key);
  });
}

function persistDraft() {
  return sendRuntimeMessage({
    action: 'persistBuilderDraft',
    draft: state.builder,
  }).catch(() => null);
}

function persistPickerState() {
  return sendRuntimeMessage({
    action: 'savePickerState',
    activeFieldKey: state.activePickerField,
    activeTabId: state.activeTabId,
  }).catch(() => null);
}

function updateBuilderState(partial) {
  state.builder = {
    ...state.builder,
    ...partial,
  };
  renderBuilder();
  persistDraft();
}

function updateBuilderSelector(fieldKey, selector) {
  state.builder = {
    ...state.builder,
    selectors: {
      ...state.builder.selectors,
      [fieldKey]: selector,
    },
  };
  state.activePickerField = null;
  renderBuilder();
  persistDraft();
  persistPickerState();
}

function clearBuilderSelector(fieldKey) {
  const nextSelectors = { ...state.builder.selectors };
  delete nextSelectors[fieldKey];
  state.builder.selectors = nextSelectors;
  renderBuilder();
  persistDraft();
}

function buildTemplatePayload() {
  const selectorOverrides = {};
  SELECTOR_FIELDS.forEach(({ key }) => {
    const value = (state.builder.selectors[key] || '').trim();
    if (value) {
      selectorOverrides[key] = value;
    }
  });

  return {
    name: state.builder.name.trim(),
    parser: state.builder.parser.trim(),
    description: state.builder.description.trim(),
    detection_signals: [],
    strengths: [],
    coverage: [],
    crawl_rules: {
      max_pages: Number(state.builder.crawlRules.maxPages) || 100,
      max_depth: Number(state.builder.crawlRules.maxDepth) || 3,
      same_domain_only: Boolean(state.builder.crawlRules.sameDomainOnly),
      url_patterns: splitLines(state.builder.crawlRules.urlPatterns),
      exclude_patterns: splitLines(state.builder.crawlRules.excludePatterns),
      respect_robots_txt: Boolean(state.builder.crawlRules.respectRobotsTxt),
    },
    selector_overrides: Object.keys(selectorOverrides).length ? selectorOverrides : null,
  };
}

function applyPickResult(result) {
  if (!result?.fieldKey || typeof result.selector !== 'string') {
    return;
  }

  updateBuilderSelector(result.fieldKey, result.selector);
  showBanner({
    tone: 'success',
    title: 'Selector captured',
    message: `${SELECTOR_FIELDS.find((field) => field.key === result.fieldKey)?.label || result.fieldKey} set to ${result.selector}`,
  });
  sendRuntimeMessage({ action: 'clearPickResult' }).catch(() => null);
}

function bindSettingsInputs() {
  elements.apiUrlInput.addEventListener('input', () => {
    state.settings.apiUrl = elements.apiUrlInput.value;
    elements.apiUrlInput.classList.remove('is-highlighted');
  });

  elements.apiKeyInput.addEventListener('input', () => {
    state.settings.apiKey = elements.apiKeyInput.value;
  });

  elements.saveSettingsButton.addEventListener('click', async () => {
    hideBanner();
    const payload = {
      [LOCAL_KEYS.apiUrl]: normalizeApiUrl(elements.apiUrlInput.value),
      [LOCAL_KEYS.apiKey]: elements.apiKeyInput.value.trim(),
    };

    chrome.storage.local.set(payload, () => {
      const runtimeError = chrome.runtime.lastError;
      if (runtimeError) {
        showBanner({
          tone: 'error',
          title: 'Settings not saved',
          message: runtimeError.message,
        });
        return;
      }

      state.settings.apiUrl = payload[LOCAL_KEYS.apiUrl];
      state.settings.apiKey = payload[LOCAL_KEYS.apiKey];
      showBanner({
        tone: 'success',
        title: 'Saved',
        message: 'Settings updated for this browser profile.',
      });
    });
  });

  elements.testConnectionButton.addEventListener('click', async () => {
    hideBanner();
    const apiUrl = normalizeApiUrl(elements.apiUrlInput.value);
    const apiKey = elements.apiKeyInput.value.trim();

    if (!apiUrl) {
      elements.apiUrlInput.classList.add('is-highlighted');
      showBanner({
        tone: 'error',
        title: 'API Base URL is required',
        message: 'Enter your FilamentFinder API base URL before testing the connection.',
      });
      return;
    }

    elements.testConnectionButton.disabled = true;
    elements.testConnectionButton.textContent = 'Testing...';

    try {
      const result = await sendRuntimeMessage({ action: 'testConnection', apiUrl, apiKey });
      if (!result?.ok) {
        throw new Error(result?.error || 'Connection test failed.');
      }

      showBanner({
        tone: 'success',
        title: 'Connection verified',
        message: `Connected - ${result.count} templates found.`,
      });
    } catch (error) {
      showBanner({
        tone: 'error',
        title: 'Connection failed',
        message: error.message,
      });
    } finally {
      elements.testConnectionButton.disabled = false;
      elements.testConnectionButton.textContent = 'Test Connection';
    }
  });
}

function bindBuilderInputs() {
  elements.templateNameInput.addEventListener('input', () => updateBuilderState({ name: elements.templateNameInput.value }));
  elements.parserInput.addEventListener('input', () => updateBuilderState({ parser: elements.parserInput.value }));
  elements.descriptionInput.addEventListener('input', () => updateBuilderState({ description: elements.descriptionInput.value }));
  elements.maxPagesInput.addEventListener('input', () => updateBuilderState({
    crawlRules: {
      ...state.builder.crawlRules,
      maxPages: Number(elements.maxPagesInput.value) || 100,
    },
  }));
  elements.maxDepthInput.addEventListener('input', () => updateBuilderState({
    crawlRules: {
      ...state.builder.crawlRules,
      maxDepth: Number(elements.maxDepthInput.value) || 3,
    },
  }));
  elements.sameDomainOnlyInput.addEventListener('change', () => updateBuilderState({
    crawlRules: {
      ...state.builder.crawlRules,
      sameDomainOnly: elements.sameDomainOnlyInput.checked,
    },
  }));
  elements.respectRobotsInput.addEventListener('change', () => updateBuilderState({
    crawlRules: {
      ...state.builder.crawlRules,
      respectRobotsTxt: elements.respectRobotsInput.checked,
    },
  }));
  elements.urlPatternsInput.addEventListener('input', () => updateBuilderState({
    crawlRules: {
      ...state.builder.crawlRules,
      urlPatterns: elements.urlPatternsInput.value,
    },
  }));
  elements.excludePatternsInput.addEventListener('input', () => updateBuilderState({
    crawlRules: {
      ...state.builder.crawlRules,
      excludePatterns: elements.excludePatternsInput.value,
    },
  }));

  elements.crawlRulesToggle.addEventListener('click', () => {
    const isExpanded = elements.crawlRulesToggle.getAttribute('aria-expanded') === 'true';
    elements.crawlRulesToggle.setAttribute('aria-expanded', String(!isExpanded));
    elements.crawlRulesPanel.hidden = isExpanded;
    elements.crawlRulesChevron.textContent = isExpanded ? '+' : '-';
  });

  elements.saveTemplateButton.addEventListener('click', async () => {
    hideBanner();
    const apiUrl = normalizeApiUrl(state.settings.apiUrl || elements.apiUrlInput.value);
    const apiKey = (state.settings.apiKey || elements.apiKeyInput.value || '').trim();

    if (!apiUrl) {
      setActiveTab('settings');
      elements.apiUrlInput.classList.add('is-highlighted');
      showBanner({
        tone: 'error',
        title: 'API Base URL is required',
        message: 'Configure your FilamentFinder URL before saving a template.',
      });
      return;
    }

    if (!state.builder.name.trim() || !state.builder.parser.trim()) {
      setActiveTab('builder');
      showBanner({
        tone: 'error',
        title: 'Missing required fields',
        message: 'Template name and parser label are required.',
      });
      return;
    }

    elements.saveTemplateButton.disabled = true;
    elements.saveTemplateButton.textContent = 'Saving...';

    try {
      const payload = buildTemplatePayload();
      const result = await sendRuntimeMessage({
        action: 'saveTemplate',
        apiUrl,
        apiKey,
        payload,
      });

      if (!result?.ok) {
        throw new Error(result?.error || 'Save failed.');
      }

      showBanner({
        tone: 'success',
        title: 'Template saved',
        message: `${result.data?.name || payload.name} was saved to FilamentFinder.`,
        note: 'View on FilamentFinder',
      });
    } catch (error) {
      showBanner({
        tone: 'error',
        title: 'Template save failed',
        message: error.message,
      });
    } finally {
      elements.saveTemplateButton.disabled = false;
      elements.saveTemplateButton.textContent = 'Save Template';
    }
  });
}

async function startPicking(fieldKey) {
  hideBanner();
  setActiveTab('builder');

  const tab = await queryActiveTab();
  if (!tab?.id || !tab.url || tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://')) {
    showBanner({
      tone: 'error',
      title: 'Picker unavailable',
      message: 'Open an e-commerce page in the active tab before starting the picker.',
    });
    return;
  }

  if (state.activePickerField && state.activePickerField !== fieldKey) {
    try {
      await sendMessageToTab(tab.id, { action: 'cancelPicking' });
    } catch (error) {
      const ignored = error;
      void ignored;
    }
  }

  state.activePickerField = fieldKey;
  state.activeTabId = tab.id;
  renderBuilder();
  await persistDraft();
  await persistPickerState();

  try {
    await sendMessageToTab(tab.id, { action: 'startPicking', fieldKey });
    window.close();
  } catch (error) {
    state.activePickerField = null;
    renderBuilder();
    persistPickerState();
    showBanner({
      tone: 'error',
      title: 'Picker failed to start',
      message: error.message,
    });
  }
}

function buildSelectorRows() {
  const fragment = document.createDocumentFragment();
  const template = document.getElementById('selectorRowTemplate');

  elements.selectorInputs = {};
  elements.pickButtons = {};

  SELECTOR_FIELDS.forEach((field) => {
    const row = template.content.firstElementChild.cloneNode(true);
    const label = row.querySelector('.selector-label');
    const input = row.querySelector('.selector-input');
    const pickButton = row.querySelector('.selector-pick-button');
    const clearButton = row.querySelector('.selector-clear-button');

    label.textContent = field.label;
    input.placeholder = '.selector';
    pickButton.addEventListener('click', () => startPicking(field.key));
    clearButton.addEventListener('click', () => clearBuilderSelector(field.key));

    elements.selectorInputs[field.key] = input;
    elements.pickButtons[field.key] = pickButton;
    fragment.appendChild(row);
  });

  elements.selectorRows.appendChild(fragment);
}

function handleRuntimeMessage(message) {
  if (message?.action === 'selectorPicked') {
    applyPickResult(message);
    return;
  }

  if (message?.action === 'pickingCancelled') {
    state.activePickerField = null;
    renderBuilder();
    showBanner({
      tone: 'info',
      title: 'Picking cancelled',
      message: 'Press Pick again when you are ready to capture a selector.',
    });
  }
}

function bindTabs() {
  document.querySelectorAll('[data-tab-target]').forEach((button) => {
    button.addEventListener('click', () => setActiveTab(button.dataset.tabTarget));
  });
}

async function restoreState() {
  const response = await sendRuntimeMessage({ action: 'loadExtensionState' });
  if (!response?.ok) {
    throw new Error(response?.error || 'Failed to load extension state.');
  }

  state.settings.apiUrl = response.settings?.apiUrl || '';
  state.settings.apiKey = response.settings?.apiKey || '';

  if (response.draft) {
    state.builder = {
      ...state.builder,
      ...response.draft,
      selectors: {
        ...state.builder.selectors,
        ...(response.draft.selectors || {}),
      },
      crawlRules: {
        ...state.builder.crawlRules,
        ...(response.draft.crawlRules || {}),
      },
    };
    state.activeTab = 'builder';
  }

  state.activePickerField = response.picker?.activeFieldKey || null;
  if (response.pickResult) {
    applyPickResult(response.pickResult);
    state.activeTab = 'builder';
  }
}

async function resolveActiveSite() {
  try {
    const tab = await queryActiveTab();
    state.activeTabId = tab?.id ?? null;
    if (tab?.url) {
      const url = new URL(tab.url);
      state.siteHostname = url.hostname;
    }
  } catch (error) {
    state.siteHostname = '';
  }
}

function collectElements() {
  elements.statusBanner = document.getElementById('statusBanner');
  elements.apiUrlInput = document.getElementById('apiUrlInput');
  elements.apiKeyInput = document.getElementById('apiKeyInput');
  elements.saveSettingsButton = document.getElementById('saveSettingsButton');
  elements.testConnectionButton = document.getElementById('testConnectionButton');
  elements.siteHostname = document.getElementById('siteHostname');
  elements.templateNameInput = document.getElementById('templateNameInput');
  elements.parserInput = document.getElementById('parserInput');
  elements.descriptionInput = document.getElementById('descriptionInput');
  elements.selectorRows = document.getElementById('selectorRows');
  elements.maxPagesInput = document.getElementById('maxPagesInput');
  elements.maxDepthInput = document.getElementById('maxDepthInput');
  elements.sameDomainOnlyInput = document.getElementById('sameDomainOnlyInput');
  elements.respectRobotsInput = document.getElementById('respectRobotsInput');
  elements.urlPatternsInput = document.getElementById('urlPatternsInput');
  elements.excludePatternsInput = document.getElementById('excludePatternsInput');
  elements.crawlRulesToggle = document.getElementById('crawlRulesToggle');
  elements.crawlRulesPanel = document.getElementById('crawlRulesPanel');
  elements.crawlRulesChevron = document.getElementById('crawlRulesChevron');
  elements.saveTemplateButton = document.getElementById('saveTemplateButton');
}

async function init() {
  collectElements();
  buildSelectorRows();
  bindTabs();
  bindSettingsInputs();
  bindBuilderInputs();
  chrome.runtime.onMessage.addListener((message) => handleRuntimeMessage(message));

  await Promise.allSettled([restoreState(), resolveActiveSite()]);
  renderSettings();
  renderSiteHostname();
  renderBuilder();
  setActiveTab(state.activeTab);
}

document.addEventListener('DOMContentLoaded', () => {
  init().catch((error) => {
    showBanner({
      tone: 'error',
      title: 'Extension failed to initialize',
      message: error.message,
    });
  });
});
