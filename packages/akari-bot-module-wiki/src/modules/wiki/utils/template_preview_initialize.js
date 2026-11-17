async ({config, modules, partial}) => {
    const content = document.querySelector('#mw-content-text');
    content.dataset.akariPreviewShell = 'true';
    if (getComputedStyle(content).position === 'static') content.style.position = 'relative';
    if (window.mw && typeof mw.loader.using === 'function') {
        mw.config.set(config);
        try {
            await Promise.race([
                mw.loader.using(modules).then(() => {
                    mw.hook('wikipage.content').fire(jQuery(content));
                }),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Module timeout')), 5000))
            ]);
        } catch (_) {
            partial = true;
        }
    } else {
        partial = true;
    }
    window.akariPreviewReady = true;
    await document.fonts.ready;
    await Promise.all(Array.from(content.querySelectorAll('img'), image =>
        image.decode().catch(() => {partial = true;})
    ));
    if (partial) document.querySelector('#akari-preview-watermark').dataset.previewPartial = 'true';
    if (window.akariFillCssPanel) window.akariFillCssPanel();
    const overlay = document.querySelector('#akari-preview-watermark');
    overlay.style.width = Math.max(content.offsetWidth, content.scrollWidth) + 'px';
    overlay.style.height = Math.max(content.offsetHeight, content.scrollHeight) + 'px';
    if (window.akariUpdateWatermark) window.akariUpdateWatermark();
    await new Promise(requestAnimationFrame);
    await new Promise(requestAnimationFrame);
}
