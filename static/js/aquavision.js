/**
 * ═══════════════════════════════════════════════════════════
 *  AquaVision v2 — "Abyssal Depth" Immersive Engine
 * ═══════════════════════════════════════════════════════════
 *
 * Features:
 *   1. WebGL Fluid Simulation Background (cursor-reactive)
 *   2. Magnetic Hover Effect (cards + buttons)
 *   3. Glow-Tracking Card Borders (--gx, --gy)
 *   4. SPA Page Transitions (View Transitions API + fallback)
 *   5. Nav Glassmorphism Scroll
 *   6. GSAP ScrollTrigger Reveal System
 *   7. Auto-Stagger System
 *   8. 3D Card Tilt
 *   9. Sonar Scanner Processing State
 *  10. GSAP Result Entrance Orchestration
 *  11. Image Fade-In
 *  12. Page Enter Animation
 *
 * Performance: Only transform, opacity, filter animated (GPU)
 * Accessibility: prefers-reduced-motion = ALL animations off
 */

    (function () {
        'use strict';

        var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        var IS_TOUCH = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
        var HAS_GSAP = (typeof gsap !== 'undefined');
        var HAS_ST = (typeof ScrollTrigger !== 'undefined');

        if (HAS_GSAP && HAS_ST) gsap.registerPlugin(ScrollTrigger);


        /* ══════════════════════════════════════════════════════════
           1. WebGL FLUID SIMULATION BACKGROUND
           Lightweight Navier-Stokes-inspired metaball fluid.
           Reacts to cursor movement. Glowing cyan/sapphire ripples.
           ══════════════════════════════════════════════════════════ */

        function initFluidBackground() {
            var canvas = document.getElementById('fluidBg');
            if (!canvas || REDUCED) return;

            var gl = canvas.getContext('webgl', { alpha: true, antialias: false, premultipliedAlpha: false });
            if (!gl) return;

            function resize() {
                var dpr = Math.min(window.devicePixelRatio, 1.5);
                canvas.width = canvas.clientWidth * dpr;
                canvas.height = canvas.clientHeight * dpr;
                gl.viewport(0, 0, canvas.width, canvas.height);
            }
            resize();
            window.addEventListener('resize', resize);

            var vertSrc = [
                'attribute vec2 a_pos;',
                'void main(){ gl_Position = vec4(a_pos, 0.0, 1.0); }'
            ].join('\n');

            var fragSrc = [
                'precision mediump float;',
                'uniform float u_time;',
                'uniform vec2 u_resolution;',
                'uniform vec2 u_mouse;',
                'uniform float u_mouseVel;',
                '',
                'float metaball(vec2 p, vec2 center, float radius) {',
                '    float d = length(p - center);',
                '    return radius * radius / (d * d + 0.001);',
                '}',
                '',
                'void main() {',
                '    vec2 uv = gl_FragCoord.xy / u_resolution;',
                '    vec2 p = uv * 2.0 - 1.0;',
                '    p.x *= u_resolution.x / u_resolution.y;',
                '',
                '    float field = 0.0;',
                '',
                '    // Ambient drifting orbs',
                '    for (int i = 0; i < 8; i++) {',
                '        float fi = float(i);',
                '        float phase = fi * 0.78;',
                '        vec2 center = vec2(',
                '            sin(u_time * (0.12 + fi * 0.02) + phase) * 0.8,',
                '            cos(u_time * (0.09 + fi * 0.015) + phase * 1.3) * 0.7',
                '        );',
                '        float r = 0.08 + 0.04 * sin(u_time * 0.3 + fi);',
                '        field += metaball(p, center, r);',
                '    }',
                '',
                '    // Mouse-reactive orb (stronger when moving fast)',
                '    vec2 mp = u_mouse * 2.0 - 1.0;',
                '    mp.x *= u_resolution.x / u_resolution.y;',
                '    float mouseR = 0.12 + u_mouseVel * 0.25;',
                '    field += metaball(p, mp, mouseR) * (1.0 + u_mouseVel * 3.0);',
                '',
                '    // Trail orbs following mouse with delay',
                '    for (int j = 0; j < 3; j++) {',
                '        float fj = float(j);',
                '        vec2 trail = mix(vec2(0.5), u_mouse, 0.3 + fj * 0.2);',
                '        trail = trail * 2.0 - 1.0;',
                '        trail.x *= u_resolution.x / u_resolution.y;',
                '        float tr = 0.06 + u_mouseVel * 0.12;',
                '        field += metaball(p, trail, tr) * u_mouseVel * 2.0;',
                '    }',
                '',
                '    // Color mapping: deep abyss → cyan → sapphire',
                '    float intensity = smoothstep(0.6, 2.5, field);',
                '    vec3 cyan    = vec3(0.024, 0.839, 0.941);',
                '    vec3 sapphire= vec3(0.506, 0.549, 0.973);',
                '    vec3 col = mix(cyan, sapphire, smoothstep(1.0, 3.0, field));',
                '',
                '    // Subtle edge glow',
                '    float edgeGlow = smoothstep(0.4, 0.7, field) - smoothstep(0.7, 2.0, field);',
                '    col += vec3(0.06, 0.85, 0.94) * edgeGlow * 0.3;',
                '',
                '    float alpha = intensity * 0.06;',
                '    gl_FragColor = vec4(col * alpha, alpha);',
                '}'
            ].join('\n');

            function compile(type, src) {
                var s = gl.createShader(type);
                gl.shaderSource(s, src);
                gl.compileShader(s);
                if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
                    console.warn('[Fluid] Shader error:', gl.getShaderInfoLog(s));
                    return null;
                }
                return s;
            }

            var vs = compile(gl.VERTEX_SHADER, vertSrc);
            var fs = compile(gl.FRAGMENT_SHADER, fragSrc);
            if (!vs || !fs) return;

            var prog = gl.createProgram();
            gl.attachShader(prog, vs);
            gl.attachShader(prog, fs);
            gl.linkProgram(prog);
            if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
            gl.useProgram(prog);

            // Fullscreen quad
            var buf = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, buf);
            gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
            var aPos = gl.getAttribLocation(prog, 'a_pos');
            gl.enableVertexAttribArray(aPos);
            gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

            var uTime = gl.getUniformLocation(prog, 'u_time');
            var uRes = gl.getUniformLocation(prog, 'u_resolution');
            var uMouse = gl.getUniformLocation(prog, 'u_mouse');
            var uVel = gl.getUniformLocation(prog, 'u_mouseVel');

            var mouse = { x: 0.5, y: 0.5, tx: 0.5, ty: 0.5, vel: 0 };

            document.addEventListener('mousemove', function (e) {
                mouse.tx = e.clientX / window.innerWidth;
                mouse.ty = 1.0 - (e.clientY / window.innerHeight);
            });

            gl.enable(gl.BLEND);
            gl.blendFunc(gl.SRC_ALPHA, gl.ONE);

            function render(t) {
                t *= 0.001;

                // Smoothly interpolate mouse position
                var dx = mouse.tx - mouse.x;
                var dy = mouse.ty - mouse.y;
                mouse.x += dx * 0.08;
                mouse.y += dy * 0.08;
                mouse.vel += (Math.sqrt(dx * dx + dy * dy) * 15 - mouse.vel) * 0.1;
                mouse.vel = Math.max(0, Math.min(mouse.vel, 1));

                gl.clearColor(0, 0, 0, 0);
                gl.clear(gl.COLOR_BUFFER_BIT);

                gl.uniform1f(uTime, t);
                gl.uniform2f(uRes, canvas.width, canvas.height);
                gl.uniform2f(uMouse, mouse.x, mouse.y);
                gl.uniform1f(uVel, mouse.vel);

                gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
                requestAnimationFrame(render);
            }
            requestAnimationFrame(render);
        }


        /* ══════════════════════════════════════════════════════════
           2. MAGNETIC HOVER EFFECT
           Cards and buttons subtly pull toward the cursor.
           ══════════════════════════════════════════════════════════ */

        function initMagnetic() {
            if (REDUCED || IS_TOUCH) return;

            document.querySelectorAll('.magnetic-btn, .bento-card, .btn-enhance, .btn-primary, .btn-ghost, .btn-submit').forEach(function (el) {
                var maxMove = el.classList.contains('bento-card') ? 6 : 10;

                el.addEventListener('mousemove', function (e) {
                    var r = el.getBoundingClientRect();
                    var cx = r.left + r.width / 2;
                    var cy = r.top + r.height / 2;
                    var dx = (e.clientX - cx) / (r.width / 2);
                    var dy = (e.clientY - cy) / (r.height / 2);

                    if (HAS_GSAP) {
                        gsap.to(el, { x: dx * maxMove, y: dy * maxMove, duration: 0.3, ease: 'power2.out' });
                    } else {
                        el.style.transform = 'translate(' + (dx * maxMove) + 'px,' + (dy * maxMove) + 'px)';
                    }
                });

                el.addEventListener('mouseleave', function () {
                    if (HAS_GSAP) {
                        gsap.to(el, { x: 0, y: 0, duration: 0.6, ease: 'elastic.out(1,0.4)' });
                    } else {
                        el.style.transform = '';
                    }
                });
            });
        }


        /* ══════════════════════════════════════════════════════════
           3. GLOW-TRACKING CARD BORDERS
           The card border "glows" relative to cursor position.
           Uses CSS custom properties --gx and --gy.
           ══════════════════════════════════════════════════════════ */

        function initGlowTrack() {
            if (REDUCED || IS_TOUCH) return;

            document.querySelectorAll('.bento-card, .pipeline-step, .deg-card, .stat-card, .metric-card, .info-card').forEach(function (card) {
                card.addEventListener('mousemove', function (e) {
                    var r = card.getBoundingClientRect();
                    card.style.setProperty('--gx', ((e.clientX - r.left) / r.width * 100) + '%');
                    card.style.setProperty('--gy', ((e.clientY - r.top) / r.height * 100) + '%');
                });
            });
        }


        /* ══════════════════════════════════════════════════════════
           4. SPA PAGE TRANSITIONS
           Intercept navigation links. Fade out current content,
           fetch new page, swap content, fade in.
           Uses View Transitions API where supported, else CSS fallback.
           The ocean-bg + fluid canvas stay permanently mounted.
           ══════════════════════════════════════════════════════════ */

        function initSPATransitions() {
            if (REDUCED) return;

            // Smooth fade-out before navigating to the next page.
            // The ocean-bg gradient + fluid canvas reload instantly so visually
            // the user experiences a seamless cross-fade between pages.
            document.addEventListener('click', function (e) {
                var link = e.target.closest('a[href]');
                if (!link) return;

                var href = link.getAttribute('href');

                // Skip: external, hash, download, logout, file links, same-page
                if (!href || href.startsWith('#') || href.startsWith('http') ||
                    href.startsWith('javascript') || link.hasAttribute('download') ||
                    href.includes('logout') || href.includes('/static/')) return;

                e.preventDefault();

                var pageEl = document.querySelector('.page, .hero, main, .auth-card');
                if (!pageEl) { window.location.href = href; return; }

                // Smooth fade-out via View Transitions API (if supported)
                if (document.startViewTransition) {
                    document.startViewTransition(function () {
                        window.location.href = href;
                    });
                } else {
                    // CSS fallback: fade out, then navigate
                    pageEl.style.transition = 'opacity 0.2s ease, transform 0.2s ease, filter 0.2s ease';
                    pageEl.style.opacity = '0';
                    pageEl.style.transform = 'translateY(12px)';
                    pageEl.style.filter = 'blur(4px)';

                    setTimeout(function () {
                        window.location.href = href;
                    }, 220);
                }
            });
        }


        /* ══════════════════════════════════════════════════════════
           5. NAV GLASSMORPHISM SCROLL
           ══════════════════════════════════════════════════════════ */

        function initNavScroll() {
            var nav = document.querySelector('nav');
            if (!nav) return;

            var onScroll = function () {
                if (window.scrollY > 50) {
                    nav.style.background = 'rgba(2,12,22,0.92)';
                    nav.style.backdropFilter = 'blur(32px) saturate(180%)';
                    nav.style.webkitBackdropFilter = 'blur(32px) saturate(180%)';
                    nav.style.borderBottomColor = 'rgba(6,214,240,0.22)';
                } else {
                    nav.style.background = '';
                    nav.style.backdropFilter = '';
                    nav.style.webkitBackdropFilter = '';
                    nav.style.borderBottomColor = '';
                }
            };
            window.addEventListener('scroll', onScroll, { passive: true });
            onScroll();
        }


        /* ══════════════════════════════════════════════════════════
           6. GSAP SCROLL-TRIGGER REVEALS
           ══════════════════════════════════════════════════════════ */

        function initReveals() {
            var revealEls = document.querySelectorAll('.reveal-blur');

            if (!REDUCED && HAS_GSAP && HAS_ST && revealEls.length > 0) {
                revealEls.forEach(function (el) {
                    gsap.fromTo(el,
                        { opacity: 0, y: 40, filter: 'blur(8px)' },
                        {
                            opacity: 1, y: 0, filter: 'blur(0px)',
                            duration: 0.8, ease: 'power2.out',
                            scrollTrigger: {
                                trigger: el, start: 'top 88%',
                                toggleActions: 'play none none none'
                            }
                        }
                    );
                });
            } else if (!REDUCED && revealEls.length > 0) {
                var obs = new IntersectionObserver(function (entries) {
                    entries.forEach(function (entry) {
                        if (entry.isIntersecting) {
                            entry.target.classList.add('revealed');
                            obs.unobserve(entry.target);
                        }
                    });
                }, { threshold: 0.08, rootMargin: '0px 0px -12% 0px' });
                revealEls.forEach(function (el) { obs.observe(el); });
            } else if (REDUCED) {
                revealEls.forEach(function (el) {
                    el.style.opacity = '1'; el.style.filter = 'none'; el.style.transform = 'none';
                });
            }
        }


        /* ══════════════════════════════════════════════════════════
           7. AUTO-STAGGER SYSTEM
           ══════════════════════════════════════════════════════════ */

        function initStagger() {
            if (REDUCED || !HAS_GSAP || !HAS_ST) return;
            document.querySelectorAll('[data-stagger]').forEach(function (parent) {
                var delay = parseFloat(parent.dataset.stagger) || 0.1;
                var kids = parent.children;
                if (kids.length === 0) return;

                gsap.fromTo(kids,
                    { opacity: 0, y: 30, filter: 'blur(6px)' },
                    {
                        opacity: 1, y: 0, filter: 'blur(0px)',
                        duration: 0.65, ease: 'power2.out',
                        stagger: delay,
                        scrollTrigger: {
                            trigger: parent, start: 'top 85%',
                            toggleActions: 'play none none none'
                        }
                    }
                );
            });
        }


        /* ══════════════════════════════════════════════════════════
           8. 3D CARD TILT
           ══════════════════════════════════════════════════════════ */

        function initTilt() {
            if (REDUCED || IS_TOUCH) return;
            document.querySelectorAll('[data-tilt]').forEach(function (card) {
                var max = parseFloat(card.dataset.tilt) || 8;
                card.addEventListener('mousemove', function (e) {
                    var r = card.getBoundingClientRect();
                    var x = (e.clientX - r.left) / r.width - 0.5;
                    var y = (e.clientY - r.top) / r.height - 0.5;
                    if (HAS_GSAP) gsap.to(card, { rotationY: x * max, rotationX: -y * max, z: 12, duration: 0.4, ease: 'power2.out', transformPerspective: 800 });
                    else card.style.transform = 'perspective(800px) rotateY(' + (x * max) + 'deg) rotateX(' + (-y * max) + 'deg) translateZ(12px)';
                });
                card.addEventListener('mouseleave', function () {
                    if (HAS_GSAP) gsap.to(card, { rotationY: 0, rotationX: 0, z: 0, duration: 0.6, ease: 'elastic.out(1,0.5)', transformPerspective: 800 });
                    else { card.style.transition = 'transform 0.5s'; card.style.transform = ''; setTimeout(function () { card.style.transition = ''; }, 500); }
                });
            });
        }


        /* ══════════════════════════════════════════════════════════
           9. SONAR SCANNER PROCESSING STATE
           When the enhance form is submitted, replaces the basic
           spinner with an edge-detection canvas + sonar line +
           rapidly-cycling terminal status text.
           ══════════════════════════════════════════════════════════ */

        function initSonarScanner() {
            var uploadForm = document.getElementById('uploadForm');
            var overlay = document.getElementById('processingOverlay');
            if (!uploadForm || !overlay) return;

            uploadForm.addEventListener('submit', function () {
                overlay.classList.add('active');

                var previewImg = document.getElementById('previewImg');
                var sonarCanvas = document.getElementById('sonarCanvas');
                var sonarLine = document.getElementById('sonarLine');
                var terminalText = document.getElementById('terminalText');

                // Build edge-detection from uploaded image preview
                if (previewImg && previewImg.src && sonarCanvas && previewImg.naturalWidth > 0) {
                    var ctx = sonarCanvas.getContext('2d');
                    var cw = 400, ch = 300;
                    sonarCanvas.width = cw;
                    sonarCanvas.height = ch;
                    sonarCanvas.style.display = 'block';

                    // Draw image to canvas
                    ctx.drawImage(previewImg, 0, 0, cw, ch);

                    // Apply Sobel edge detection
                    var imageData = ctx.getImageData(0, 0, cw, ch);
                    var data = imageData.data;
                    var grayscale = new Float32Array(cw * ch);

                    // Convert to grayscale
                    for (var i = 0; i < cw * ch; i++) {
                        var idx = i * 4;
                        grayscale[i] = data[idx] * 0.299 + data[idx + 1] * 0.587 + data[idx + 2] * 0.114;
                    }

                    // Sobel edge detection
                    var edges = new Float32Array(cw * ch);
                    for (var y = 1; y < ch - 1; y++) {
                        for (var x = 1; x < cw - 1; x++) {
                            var gx = -grayscale[(y - 1) * cw + (x - 1)] + grayscale[(y - 1) * cw + (x + 1)]
                                - 2 * grayscale[y * cw + (x - 1)] + 2 * grayscale[y * cw + (x + 1)]
                                - grayscale[(y + 1) * cw + (x - 1)] + grayscale[(y + 1) * cw + (x + 1)];
                            var gy = -grayscale[(y - 1) * cw + (x - 1)] - 2 * grayscale[(y - 1) * cw + x] - grayscale[(y - 1) * cw + (x + 1)]
                                + grayscale[(y + 1) * cw + (x - 1)] + 2 * grayscale[(y + 1) * cw + x] + grayscale[(y + 1) * cw + (x + 1)];
                            edges[y * cw + x] = Math.min(255, Math.sqrt(gx * gx + gy * gy));
                        }
                    }

                    // Render edges as cyan wireframe on dark background
                    var outData = ctx.createImageData(cw, ch);
                    for (var i = 0; i < cw * ch; i++) {
                        var idx = i * 4;
                        var e = edges[i] / 255;
                        outData.data[idx] = Math.round(6 * e);     // R
                        outData.data[idx + 1] = Math.round(214 * e);   // G
                        outData.data[idx + 2] = Math.round(240 * e);   // B
                        outData.data[idx + 3] = Math.round(200 * e + 15); // A
                    }
                    ctx.putImageData(outData, 0, 0);
                }

                // Animate sonar scanning line
                if (sonarLine) {
                    sonarLine.style.display = 'block';
                    var scanPos = 0;
                    var scanInterval = setInterval(function () {
                        scanPos = (scanPos + 0.8) % 100;
                        sonarLine.style.top = scanPos + '%';
                    }, 30);

                    // Store ref for cleanup
                    overlay._scanInterval = scanInterval;
                }

                // Cycle terminal text
                if (terminalText) {
                    var statuses = [
                        'Initializing MobileNetV2 classifier...',
                        'Loading pre-trained weights (best_model.pth)...',
                        'Analyzing spectral degradation pattern...',
                        'Computing dark channel prior...',
                        'Estimating atmospheric light vector...',
                        'Compensating red wavelength attenuation...',
                        'Applying Gray World white balance...',
                        'Running CLAHE on LAB L-channel (clip=2.0)...',
                        'Computing guided filter transmission map...',
                        'Executing multi-scale Laplacian fusion...',
                        'Proportional LAB colour correction...',
                        'Recovering saturation in HSV space...',
                        'Applying unsharp mask (σ=1.5)...',
                        'Auto-exposure normalization...',
                        'Post-denoise bilateral filter...',
                        'Computing UCIQE quality metric...',
                        'Computing UIQM (Panetta et al. 2016)...',
                        'Calculating Hasler-Süsstrunk colorfulness...',
                        'Measuring Laplacian variance sharpness...',
                        'Finalizing enhanced output...'
                    ];
                    var si = 0;
                    var textInterval = setInterval(function () {
                        terminalText.textContent = statuses[si % statuses.length];
                        si++;
                    }, 600);

                    overlay._textInterval = textInterval;
                }
            });
        }


        /* ══════════════════════════════════════════════════════════
           10. GSAP RESULT ENTRANCE ORCHESTRATION
           When the result section loads (server-rendered),
           orchestrate: image scale-in → confidence bar fill →
           metrics count-up → improvement badge bounce.
           ══════════════════════════════════════════════════════════ */

        function initResultOrchestration() {
            if (REDUCED || !HAS_GSAP) return;

            var resultSection = document.querySelector('.result-section');
            if (!resultSection) return;

            var tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

            // 1. Classification bar entrance
            var classBar = resultSection.querySelector('.class-bar');
            if (classBar) {
                tl.from(classBar, { opacity: 0, y: 30, filter: 'blur(6px)', duration: 0.6 });
            }

            // 2. Comparison images scale in
            var compPanels = resultSection.querySelectorAll('.comp-panel');
            if (compPanels.length) {
                tl.from(compPanels, {
                    opacity: 0, scale: 0.92, y: 20, filter: 'blur(4px)',
                    duration: 0.7, stagger: 0.15
                }, '-=0.3');
            }

            // 3. Confidence bar fill (already has data-width)
            var confFill = resultSection.querySelector('.conf-bar-fill');
            if (confFill) {
                var targetWidth = confFill.dataset.width || '0%';
                tl.to(confFill, { width: targetWidth, duration: 1.0, ease: 'power2.out' }, '-=0.5');
            }

            // 4. Metric cards stagger in
            var metricCards = resultSection.querySelectorAll('.metric-card');
            if (metricCards.length) {
                tl.from(metricCards, {
                    opacity: 0, y: 25, scale: 0.95,
                    duration: 0.5, stagger: 0.08
                }, '-=0.4');
            }

            // 5. Metric bar fills animate
            resultSection.querySelectorAll('.mbar-fill').forEach(function (el) {
                var targetW = el.dataset.width || '0%';
                tl.to(el, { width: targetW, duration: 0.8, ease: 'power2.out' }, '-=0.6');
            });

            // 6. Count-up animation for numeric values
            resultSection.querySelectorAll('.val.enh').forEach(function (el) {
                var finalVal = parseFloat(el.textContent);
                if (isNaN(finalVal)) return;

                var obj = { val: 0 };
                tl.to(obj, {
                    val: finalVal,
                    duration: 1.2,
                    ease: 'power2.out',
                    onUpdate: function () {
                        el.textContent = obj.val.toFixed(finalVal % 1 === 0 ? 0 : 2);
                    }
                }, '-=1.0');
            });

            // 7. Improvement badge bounce
            var badge = resultSection.querySelector('.imp-badge');
            if (badge) {
                tl.from(badge, {
                    opacity: 0, scale: 0.5, y: 10,
                    duration: 0.5, ease: 'back.out(2.5)'
                }, '-=0.6');
            }

            // 8. Pipeline card and actions
            var pipeCard = resultSection.querySelector('.pipeline-card');
            if (pipeCard) {
                tl.from(pipeCard, { opacity: 0, y: 20, duration: 0.5 }, '-=0.3');
            }

            var btnRow = resultSection.querySelector('.btn-row');
            if (btnRow) {
                tl.from(btnRow.children, {
                    opacity: 0, y: 15, stagger: 0.1, duration: 0.4
                }, '-=0.3');
            }
        }


        /* ══════════════════════════════════════════════════════════
           11. IMAGE FADE-IN
           ══════════════════════════════════════════════════════════ */

        function initImageFadeIn() {
            document.querySelectorAll('img').forEach(function (img) {
                if (img.complete && img.naturalWidth > 0) {
                    img.classList.add('loaded');
                } else {
                    img.addEventListener('load', function () { img.classList.add('loaded'); });
                    img.addEventListener('error', function () { img.style.opacity = '1'; });
                }
            });
        }


        /* ══════════════════════════════════════════════════════════
           12. PAGE ENTER ANIMATION
           ══════════════════════════════════════════════════════════ */

        function initPageEnter() {
            if (REDUCED) return;
            var p = document.querySelector('.page, .hero, main');
            if (p) p.classList.add('page-enter');
        }


        /* ══════════════════════════════════════════════════════════
           INIT
           ══════════════════════════════════════════════════════════ */

        document.addEventListener('DOMContentLoaded', function () {
            initFluidBackground();
            initNavScroll();
            initReveals();
            initStagger();
            initMagnetic();
            initGlowTrack();
            initTilt();
            initSPATransitions();
            initSonarScanner();
            initResultOrchestration();
            initImageFadeIn();
            initPageEnter();
        });

    })();
