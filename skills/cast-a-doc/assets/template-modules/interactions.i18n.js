(() => {
  const config = window.CAST_DOCS_I18N;
  if (!config || !Array.isArray(config.locales) || config.locales.length < 2) return;
  const MEMORY_KEY = 'cast-docs:global-memory';
  const root = document.documentElement;
  const stringsFor = (locale) => (config.strings && config.strings[locale]) || {};
  const label = (locale, key, fallback) => stringsFor(locale)[key] || stringsFor(config.activeLocale)[key] || fallback;
  const displayName = (locale) => label(locale, 'chrome.languageName', locale);
  function readMemory() {
    try {
      const raw = window.localStorage && window.localStorage.getItem(MEMORY_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (_) {
      return {};
    }
  }
  function writeMemory(memory) {
    try {
      window.localStorage.setItem(MEMORY_KEY, JSON.stringify(memory));
      return true;
    } catch (_) {
      return false;
    }
  }
  function rememberDefaultLocale(locale) {
    if (!config.locales.includes(locale)) return false;
    const memory = readMemory();
    const preferences = memory.preferences && typeof memory.preferences === 'object' ? memory.preferences : {};
    memory.version = 1;
    memory.preferences = {
      ...preferences,
      defaultLocale: locale,
      defaultLocaleUpdatedAt: new Date().toISOString(),
    };
    return writeMemory(memory);
  }
  function defaultLocaleFromMemory() {
    const locale = readMemory().preferences?.defaultLocale;
    return config.locales.includes(locale) ? locale : null;
  }
  function apply(locale) {
    if (!config.locales.includes(locale)) return;
    root.lang = locale;
    root.setAttribute('data-active-locale', locale);
    config.activeLocale = locale;
    document.querySelectorAll('[data-locale]').forEach((node) => {
      const active = node.getAttribute('data-locale') === locale;
      node.setAttribute('data-locale-active', active ? 'true' : 'false');
    });
    document.querySelectorAll('[data-locale-target]').forEach((button) => {
      const active = button.getAttribute('data-locale-target') === locale;
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    document.querySelectorAll('[data-i18n-key]').forEach((node) => {
      const key = node.getAttribute('data-i18n-key');
      if (key) node.textContent = label(locale, key, node.textContent);
    });
  }
  function maybeSetDefaultLocale(locale) {
    if (!config.locales.includes(locale) || defaultLocaleFromMemory() === locale) return;
    const message = label(
      locale,
      'chrome.defaultLanguagePrompt',
      `Set ${displayName(locale)} as the default language for CAST Docs?`
    ).replace('{language}', displayName(locale));
    if (window.confirm(message)) {
      rememberDefaultLocale(locale);
    }
  }
  document.querySelectorAll('[data-locale-target]').forEach((button) => {
    button.addEventListener('click', () => {
      const locale = button.getAttribute('data-locale-target');
      if (!config.locales.includes(locale) || locale === config.activeLocale) return;
      apply(locale);
      maybeSetDefaultLocale(locale);
    });
  });
  apply(defaultLocaleFromMemory() || config.activeLocale);
})();
