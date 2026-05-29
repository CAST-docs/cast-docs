(() => {
  document.querySelectorAll('.toggle-view[data-view-group]').forEach((group) => {
    const buttons = Array.from(group.querySelectorAll('[data-view-target]'));
    const panels = Array.from(group.querySelectorAll('[data-view-panel]'));
    function activate(target) {
      buttons.forEach((button) => {
        button.setAttribute('aria-pressed', button.getAttribute('data-view-target') === target ? 'true' : 'false');
      });
      panels.forEach((panel) => {
        panel.setAttribute('data-view-active', panel.getAttribute('data-view-panel') === target ? 'true' : 'false');
      });
    }
    buttons.forEach((button) => {
      button.addEventListener('click', () => activate(button.getAttribute('data-view-target')));
    });
  });
})();
