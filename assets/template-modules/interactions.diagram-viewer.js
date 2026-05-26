
(() => {
  const lightbox = document.querySelector('.lightbox[data-interaction="diagram-viewer"]');
  if (!lightbox) return;
  const body = lightbox.querySelector('.lightbox-body');
  const toolbar = lightbox.querySelector('.lightbox-toolbar');
  const closeButton = lightbox.querySelector('.lightbox-close');
  let sourceSvg = null;
  let cloneSvg = null;
  let zoom = 1;
  let panX = 0;
  let panY = 0;
  function fileBase(svg) {
    return svg.closest('[data-download-name]')?.getAttribute('data-download-name') || 'diagram';
  }
  function serialize(svg) {
    const clone = svg.cloneNode(true);
    if (!clone.getAttribute('xmlns')) clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    return new XMLSerializer().serializeToString(clone);
  }
  function downloadBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 250);
  }
  function downloadSvg(svg) {
    downloadBlob(new Blob([serialize(svg)], { type: 'image/svg+xml;charset=utf-8' }), `${fileBase(svg)}.svg`);
  }
  function downloadPng(svg) {
    const url = URL.createObjectURL(new Blob([serialize(svg)], { type: 'image/svg+xml;charset=utf-8' }));
    const img = new Image();
    img.onload = () => {
      const box = svg.viewBox && svg.viewBox.baseVal;
      const width = box && box.width ? box.width : 900;
      const height = box && box.height ? box.height : 520;
      const canvas = document.createElement('canvas');
      canvas.width = width * 2;
      canvas.height = height * 2;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.scale(2, 2);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      canvas.toBlob((blob) => blob && downloadBlob(blob, `${fileBase(svg)}.png`), 'image/png');
    };
    img.src = url;
  }
  function setTransform() {
    if (cloneSvg) cloneSvg.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
  }
  function makeButton(label, action) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.setAttribute('data-renderer-owned', 'true');
    button.addEventListener('click', action);
    return button;
  }
  function open(svg) {
    sourceSvg = svg;
    cloneSvg = svg.cloneNode(true);
    cloneSvg.removeAttribute('width');
    cloneSvg.removeAttribute('height');
    cloneSvg.style.transformOrigin = 'center';
    zoom = 1;
    panX = 0;
    panY = 0;
    body.replaceChildren(cloneSvg);
    toolbar.replaceChildren(
      makeButton('Zoom -', () => { zoom = Math.max(0.25, zoom * 0.8); setTransform(); }),
      makeButton('Zoom +', () => { zoom = Math.min(8, zoom * 1.25); setTransform(); }),
      makeButton('Reset', () => { zoom = 1; panX = 0; panY = 0; setTransform(); }),
      makeButton('SVG', () => downloadSvg(sourceSvg)),
      makeButton('PNG', () => downloadPng(sourceSvg))
    );
    lightbox.classList.add('open');
    setTransform();
  }
  function close() {
    lightbox.classList.remove('open');
    body.replaceChildren();
    toolbar.replaceChildren();
    sourceSvg = null;
    cloneSvg = null;
  }
  closeButton.addEventListener('click', close);
  lightbox.addEventListener('click', (event) => { if (event.target === lightbox) close(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') close(); });
  body.addEventListener('wheel', (event) => {
    if (!cloneSvg) return;
    event.preventDefault();
    zoom = Math.max(0.25, Math.min(8, zoom * Math.exp(-event.deltaY * 0.0015)));
    setTransform();
  }, { passive: false });
  let drag = null;
  body.addEventListener('mousedown', (event) => {
    if (!cloneSvg) return;
    drag = { x: event.clientX, y: event.clientY, panX, panY };
  });
  window.addEventListener('mousemove', (event) => {
    if (!drag) return;
    panX = drag.panX + event.clientX - drag.x;
    panY = drag.panY + event.clientY - drag.y;
    setTransform();
  });
  window.addEventListener('mouseup', () => { drag = null; });
  document.querySelectorAll('.diagram').forEach((figure) => {
    const svg = figure.querySelector('svg');
    if (!svg) return;
    const tools = document.createElement('div');
    tools.className = 'diagram-toolbar';
    tools.setAttribute('data-renderer-owned', 'true');
    tools.append(
      makeButton('Open', () => open(svg)),
      makeButton('SVG', () => downloadSvg(svg)),
      makeButton('PNG', () => downloadPng(svg))
    );
    figure.appendChild(tools);
  });
})();
