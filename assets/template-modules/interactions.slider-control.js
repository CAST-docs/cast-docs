(() => {
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

  document.querySelectorAll('.slider-range[data-slider-target]').forEach((slider) => {
    const id = slider.getAttribute('data-slider-target');
    const output = document.querySelector(`.slider-value[data-slider-output="${id}"]`);
    const targets = document.querySelectorAll(`.slider-target[data-slider-demo="${id}"]`);
    const unit = slider.getAttribute('data-slider-unit') || '';
    const min = Number(slider.min || 0);
    const max = Number(slider.max || 100);

    const update = () => {
      const value = Number(slider.value);
      const ratio = max === min ? 1 : clamp((value - min) / (max - min), 0, 1);
      if (output) output.textContent = `${slider.value}${unit}`;
      targets.forEach((target) => {
        target.style.opacity = String(clamp(ratio, 0.25, 1));
      });
    };

    slider.addEventListener('input', update);
    update();
  });
})();
