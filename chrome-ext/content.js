(function () {
  const ROOT_CLASS = 'filamentfinder-picking';
  const STYLE_ID = 'filamentfinder-picker-style';
  const OVERLAY_ID = 'filamentfinder-picker-overlay';
  const LABEL_ID = 'filamentfinder-picker-label';

  const state = {
    active: false,
    fieldKey: null,
    overlay: null,
    label: null,
    hoveredElement: null,
    boundMouseMove: null,
    boundClick: null,
    boundKeyDown: null,
    boundScroll: null,
  };

  function ensurePickerUi() {
    if (!document.getElementById(STYLE_ID)) {
      const style = document.createElement('style');
      style.id = STYLE_ID;
      style.textContent = `
        html.${ROOT_CLASS},
        html.${ROOT_CLASS} * {
          cursor: crosshair !important;
        }

        #${OVERLAY_ID} {
          position: fixed;
          z-index: 2147483646;
          pointer-events: none;
          border: 2px solid #7c3aed;
          box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.18);
          background: rgba(124, 58, 237, 0.08);
          border-radius: 4px;
          display: none;
        }

        #${LABEL_ID} {
          position: fixed;
          z-index: 2147483647;
          pointer-events: none;
          display: none;
          max-width: min(420px, calc(100vw - 16px));
          padding: 6px 8px;
          border-radius: 8px;
          border: 1px solid rgba(167, 139, 250, 0.55);
          background: rgba(15, 23, 42, 0.96);
          color: #e9d5ff;
          font: 12px/1.3 ui-monospace, SFMono-Regular, Consolas, monospace;
          box-shadow: 0 14px 32px rgba(2, 6, 23, 0.26);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
      `;
      document.documentElement.appendChild(style);
    }

    if (!state.overlay) {
      state.overlay = document.createElement('div');
      state.overlay.id = OVERLAY_ID;
      document.documentElement.appendChild(state.overlay);
    }

    if (!state.label) {
      state.label = document.createElement('div');
      state.label.id = LABEL_ID;
      document.documentElement.appendChild(state.label);
    }
  }

  function hidePickerUi() {
    if (state.overlay) {
      state.overlay.style.display = 'none';
    }
    if (state.label) {
      state.label.style.display = 'none';
    }
  }

  function describeElement(element, selectorPreview) {
    const tagName = element.tagName.toLowerCase();
    const idPart = element.id ? `#${element.id}` : '';
    const classes = Array.from(element.classList || []).slice(0, 2).join('.');
    const classPart = classes ? `.${classes}` : '';
    return `${tagName}${idPart}${classPart} -> ${selectorPreview}`;
  }

  function updateHighlight(element) {
    if (!state.active || !element || !state.overlay || !state.label) {
      return;
    }

    state.hoveredElement = element;
    const rect = element.getBoundingClientRect();
    const selectorPreview = buildSelector(element);

    state.overlay.style.display = 'block';
    state.overlay.style.top = `${Math.max(rect.top - 2, 0)}px`;
    state.overlay.style.left = `${Math.max(rect.left - 2, 0)}px`;
    state.overlay.style.width = `${Math.max(rect.width, 0)}px`;
    state.overlay.style.height = `${Math.max(rect.height, 0)}px`;

    state.label.textContent = describeElement(element, selectorPreview);
    state.label.style.display = 'block';
    state.label.style.top = `${Math.max(rect.top - 34, 8)}px`;
    state.label.style.left = `${Math.min(Math.max(rect.left, 8), window.innerWidth - 220)}px`;
  }

  function escapeCss(value) {
    if (window.CSS && typeof window.CSS.escape === 'function') {
      return window.CSS.escape(value);
    }
    return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  }

  function isUniqueSelector(selector) {
    if (!selector) {
      return false;
    }

    try {
      return document.querySelectorAll(selector).length === 1;
    } catch (error) {
      return false;
    }
  }

  function getClassSelector(element) {
    const classes = Array.from(element.classList || []).filter(Boolean);
    if (!classes.length) {
      return '';
    }

    const tag = element.tagName.toLowerCase();
    const uniqueCandidates = [];

    classes.forEach((className) => {
      const escaped = `.${escapeCss(className)}`;
      uniqueCandidates.push(escaped);
      uniqueCandidates.push(`${tag}${escaped}`);
    });

    const combo = classes.map((className) => `.${escapeCss(className)}`).join('');
    uniqueCandidates.push(combo);
    uniqueCandidates.push(`${tag}${combo}`);

    const sortedCandidates = uniqueCandidates
      .filter(Boolean)
      .filter((candidate, index, list) => list.indexOf(candidate) === index)
      .sort((left, right) => left.length - right.length);

    return sortedCandidates.find((candidate) => isUniqueSelector(candidate)) || '';
  }

  function getNthChildSelector(element) {
    const parent = element.parentElement;
    const tag = element.tagName.toLowerCase();
    if (!parent) {
      return tag;
    }

    const siblings = Array.from(parent.children);
    const index = siblings.indexOf(element);
    return `${tag}:nth-child(${index + 1})`;
  }

  function buildSelector(element) {
    if (!(element instanceof Element)) {
      return '';
    }

    if (element.id) {
      const idSelector = `#${escapeCss(element.id)}`;
      if (isUniqueSelector(idSelector)) {
        return idSelector;
      }
    }

    const classSelector = getClassSelector(element);
    if (classSelector) {
      return classSelector;
    }

    const path = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE && current.tagName.toLowerCase() !== 'body') {
      const classCandidate = getClassSelector(current);
      const segment = current.id
        ? `#${escapeCss(current.id)}`
        : classCandidate || getNthChildSelector(current);
      path.unshift(segment);

      const selector = path.join(' > ');
      if (isUniqueSelector(selector)) {
        return selector;
      }

      current = current.parentElement;
    }

    if (current && current.tagName && current.tagName.toLowerCase() === 'body') {
      path.unshift('body');
      const selector = path.join(' > ');
      if (isUniqueSelector(selector)) {
        return selector;
      }
    }

    return path.join(' > ');
  }

  function handleMouseMove(event) {
    const target = event.target instanceof Element ? event.target : null;
    if (!target || target.id === OVERLAY_ID || target.id === LABEL_ID) {
      return;
    }
    updateHighlight(target);
  }

  function stopPicking({ notify = false } = {}) {
    if (!state.active) {
      return;
    }

    document.documentElement.classList.remove(ROOT_CLASS);
    document.removeEventListener('mousemove', state.boundMouseMove, true);
    document.removeEventListener('click', state.boundClick, true);
    document.removeEventListener('keydown', state.boundKeyDown, true);
    window.removeEventListener('scroll', state.boundScroll, true);

    hidePickerUi();
    state.active = false;
    state.fieldKey = null;
    state.hoveredElement = null;

    if (notify) {
      chrome.runtime.sendMessage({ action: 'pickingCancelled' });
    }
  }

  function startPicking(fieldKey) {
    ensurePickerUi();
    stopPicking({ notify: false });

    state.active = true;
    state.fieldKey = fieldKey;
    document.documentElement.classList.add(ROOT_CLASS);

    state.boundMouseMove = handleMouseMove;
    state.boundScroll = () => {
      if (state.hoveredElement) {
        updateHighlight(state.hoveredElement);
      }
    };
    state.boundClick = (event) => {
      if (!state.active) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();

      const target = event.target instanceof Element ? event.target : null;
      const selector = target ? buildSelector(target) : '';

      stopPicking({ notify: false });
      chrome.runtime.sendMessage({
        action: 'selectorPicked',
        fieldKey,
        selector,
      });
    };
    state.boundKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        stopPicking({ notify: true });
      }
    };

    document.addEventListener('mousemove', state.boundMouseMove, true);
    document.addEventListener('click', state.boundClick, true);
    document.addEventListener('keydown', state.boundKeyDown, true);
    window.addEventListener('scroll', state.boundScroll, true);
  }

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.action === 'startPicking') {
      startPicking(message.fieldKey);
      sendResponse({ ok: true });
      return true;
    }

    if (message?.action === 'cancelPicking') {
      stopPicking({ notify: true });
      sendResponse({ ok: true });
      return true;
    }

    return false;
  });
})();
