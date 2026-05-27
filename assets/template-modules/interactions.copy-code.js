(() => {
  function label(key, fallback) {
    const config = window.CAST_DOCS_I18N || {};
    const locale = config.activeLocale || document.documentElement.lang || 'en';
    const strings = (config.strings && config.strings[locale]) || {};
    const fallbackStrings = (config.strings && config.strings.en) || {};
    return strings[key] || fallbackStrings[key] || fallback;
  }
  function textFrom(code) {
    const activeLocale = code.querySelector('[data-locale-active="true"]');
    const scope = activeLocale || code;
    return Array.from(scope.querySelectorAll('.code-line-content')).map((node) => node.textContent || '').join('\n');
  }
  async function copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.setAttribute('aria-hidden', 'true');
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    textarea.remove();
  }
  document.querySelectorAll('[data-copy-target]').forEach((button) => {
    button.addEventListener('click', async () => {
      const id = button.getAttribute('data-copy-target');
      const code = id ? document.getElementById(id) : null;
      if (!code) return;
      await copy(textFrom(code));
      const previous = button.textContent;
      button.textContent = label('code.copied', 'Copied');
      setTimeout(() => {
        button.textContent = label('code.copy', previous || 'Copy');
      }, 1200);
    });
  });
})();
