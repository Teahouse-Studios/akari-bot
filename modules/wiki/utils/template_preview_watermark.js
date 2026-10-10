        window.akariUpdateWatermark = function() {
            var overlay = document.querySelector('#akari-preview-watermark');
            if (!overlay) return;
            if (overlay.parentElement.dataset.akariPreviewShell === 'true') {
                if (getComputedStyle(overlay.parentElement).position === 'static') {
                    overlay.parentElement.style.position = 'relative';
                }
            }
            var partial = overlay.dataset.previewPartial === 'true';
            var text = overlay.querySelector(partial ? '.akari-watermark-partial' : '.akari-watermark-normal');
            var tiles = overlay.querySelector('#akari-watermark-tiles');
            var width = Math.ceil(text.getComputedTextLength()) + 48;
            tiles.setAttribute('width', width);
            overlay.querySelectorAll('.akari-watermark-row').forEach(function(row) {
                var offset = 24 + Number(row.dataset.row) * 112;
                row.querySelectorAll('text').forEach(function(item, index) {
                    item.setAttribute('x', index % 2 === 0 ? offset : offset - width);
                });
            });
        };
        window.akariUpdateWatermark();
        document.fonts.ready.then(window.akariUpdateWatermark);
