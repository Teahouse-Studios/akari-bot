        window.akariFillCssPanel = function() {
            var root = document.querySelector('[data-akari-template-output]') ||
                document.querySelector('#akari-template-output');
            var panel = document.querySelector('.akari-css-properties');
            if (!root || !panel) return;
            var content = root.querySelector(':scope > .mw-parser-output') || root;
            function children(element) {
                return Array.from(element.children).filter(function(child) {
                    return !child.matches('style,link,script,meta,noscript,template') &&
                        getComputedStyle(child).display !== 'none';
                });
            }
            var candidates = children(content);
            // 消息正文可能与模板并列，优先选取顶层布局容器。
            var target = candidates.find(function(element) {
                var style = getComputedStyle(element);
                return style.cssFloat !== 'none' || /^(inline-)?(flex|grid|table)$/.test(style.display) ||
                    style.position === 'absolute' || style.position === 'fixed';
            }) || candidates.find(function(element) {
                return element.matches('div,section,aside,article,table,ul,ol,pre,blockquote,[style],[class]');
            }) || candidates[0] || content;
            while (getComputedStyle(target).display === 'contents' && children(target).length === 1) {
                target = children(target)[0];
            }
            var c = getComputedStyle(target);
            var isFlex = c.display === 'flex' || c.display === 'inline-flex';
            var isGrid = c.display === 'grid' || c.display === 'inline-grid';
            var properties = {
                element: target.localName + (target.id ? '#' + target.id : '') +
                    Array.from(target.classList).slice(0, 2).map(function(name) { return '.' + name; }).join(''),
                display: c.display, float: c.cssFloat, position: c.position,
                flex_direction: c.flexDirection, flex_wrap: c.flexWrap,
                grid_columns: c.gridTemplateColumns, grid_rows: c.gridTemplateRows, grid_auto_flow: c.gridAutoFlow,
                justify: c.justifyContent, align: c.alignItems, gap: c.rowGap + ' / ' + c.columnGap,
                background: c.backgroundColor, color: c.color, font: c.fontFamily,
                size: c.fontSize + ' / ' + c.lineHeight, border: c.border, radius: c.borderRadius,
                shadow: c.boxShadow, spacing: c.padding + ' / ' + c.margin
            };
            panel.querySelectorAll('[data-css-property]').forEach(function(row) {
                var key = row.dataset.cssProperty;
                var layout = row.dataset.cssLayout;
                row.hidden = layout === 'flex' ? !isFlex : layout === 'grid' ? !isGrid :
                    layout === 'container' ? !(isFlex || isGrid) : false;
                var val = properties[key] || '-';
                var value = row.querySelector('.akari-css-value');
                value.textContent = val;
                if (key === 'background' || key === 'color') {
                    var swatch = document.createElement('i');
                    swatch.className = 'akari-css-swatch';
                    swatch.style.background = val;
                    value.prepend(swatch);
                }
            });
        };
        (function waitForPreview(attempt) {
            if (window.akariPreviewReady || !window.mw || attempt >= 100) window.akariFillCssPanel();
            else setTimeout(function() { waitForPreview(attempt + 1); }, 50);
        })(0);
