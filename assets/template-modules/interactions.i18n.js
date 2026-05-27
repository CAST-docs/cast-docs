(() => {
  const config = window.CAST_DOCS_I18N;
  if (!config || !Array.isArray(config.locales) || config.locales.length < 2) return;
  const root = document.documentElement;
  const stringsFor = (locale) => (config.strings && config.strings[locale]) || {};
  const label = (locale, key, fallback) => stringsFor(locale)[key] || stringsFor(config.activeLocale)[key] || fallback;
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
  document.querySelectorAll('[data-locale-target]').forEach((button) => {
    button.addEventListener('click', () => apply(button.getAttribute('data-locale-target')));
  });
  apply(config.activeLocale);
})();
