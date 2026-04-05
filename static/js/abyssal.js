/**
 * ╔═══════════════════════════════════════════════════════════════╗
 * ║   AquaVision — ABYSSAL ENGINE v3.0                          ║
 * ║   Global interactions for every page                        ║
 * ╚═══════════════════════════════════════════════════════════════╝
 */
(function () {
  'use strict';

  var REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var IS_TOUCH = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
  var HAS_GSAP = (typeof gsap !== 'undefined');
  var HAS_ST   = (typeof ScrollTrigger !== 'undefined');
  if (HAS_GSAP && HAS_ST) gsap.registerPlugin(ScrollTrigger);

  /* ── 1. Spotlight on body — CSS custom property updated on mousemove ── */
  (function initSpotlight() {
    if (IS_TOUCH || REDUCED) return;
    document.addEventListener('mousemove', function(e) {
      document.documentElement.style.setProperty('--mx', e.clientX + 'px');
      document.documentElement.style.setProperty('--my', e.clientY + 'px');
    }, { passive: true });
  })();

  /* ── 3. Nav scroll tint ──────────────────────────────── */
  function initNav() {
    var nav = document.querySelector('.nav-abyssal');
    if (!nav) return;
    window.addEventListener('scroll', function() {
      nav.classList.toggle('scrolled', window.scrollY > 40);
    }, { passive: true });
  }

  /* ── 4. Reveal System ─────────────────────────────────── */
  function initReveals() {
    var els = document.querySelectorAll('.reveal, .reveal-left, .reveal-scale');
    if (!els.length) return;

    if (!REDUCED && HAS_GSAP && HAS_ST) {
      els.forEach(function(el) {
        var fromY = el.classList.contains('reveal') ? 30 : 0;
        var fromX = el.classList.contains('reveal-left') ? -24 : 0;
        var fromS = el.classList.contains('reveal-scale') ? 0.93 : 1;
        gsap.fromTo(el,
          { opacity: 0, y: fromY, x: fromX, scale: fromS, filter: 'blur(4px)' },
          { opacity: 1, y: 0, x: 0, scale: 1, filter: 'blur(0)',
            duration: 0.75, ease: 'power3.out',
            scrollTrigger: { trigger: el, start: 'top 90%', toggleActions: 'play none none none' }
          }
        );
      });
    } else {
      var obs = new IntersectionObserver(function(entries) {
        entries.forEach(function(e) {
          if (e.isIntersecting) { e.target.classList.add('revealed'); obs.unobserve(e.target); }
        });
      }, { threshold: 0.06 });
      els.forEach(function(el) { obs.observe(el); });
    }
  }

  /* ── 5. Stagger children ─────────────────────────────── */
  function initStagger() {
    if (REDUCED || !HAS_GSAP || !HAS_ST) return;
    document.querySelectorAll('[data-stagger]').forEach(function(parent) {
      var delay = parseFloat(parent.dataset.stagger) || 0.08;
      var kids = Array.from(parent.children);
      if (!kids.length) return;
      gsap.fromTo(kids,
        { opacity: 0, y: 24, filter: 'blur(4px)' },
        { opacity: 1, y: 0, filter: 'blur(0)',
          duration: 0.6, ease: 'power2.out', stagger: delay,
          scrollTrigger: { trigger: parent, start: 'top 88%', toggleActions: 'play none none none' }
        }
      );
    });
  }

  /* ── 6. Count-up numbers ─────────────────────────────── */
  function initCountUp() {
    document.querySelectorAll('[data-countup]').forEach(function(el) {
      var target = parseFloat(el.dataset.countup);
      var suffix = el.dataset.suffix || '';
      var decimals = el.dataset.decimals ? parseInt(el.dataset.decimals) : (target % 1 !== 0 ? 2 : 0);
      var started = false;

      var obs = new IntersectionObserver(function(entries) {
        if (!entries[0].isIntersecting || started) return;
        started = true;
        obs.disconnect();

        if (REDUCED) { el.textContent = target.toFixed(decimals) + suffix; return; }

        var from = 0;
        var duration = 1400;
        var start = null;

        function step(ts) {
          if (!start) start = ts;
          var progress = Math.min((ts - start) / duration, 1);
          var ease = 1 - Math.pow(1 - progress, 3); // ease-out cubic
          var val = from + (target - from) * ease;
          el.textContent = val.toFixed(decimals) + suffix;
          if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      }, { threshold: 0.4 });
      obs.observe(el);
    });
  }

  /* ── 7. Glow-tracking borders ─────────────────────────── */
  function initGlowTrack() {
    if (REDUCED || IS_TOUCH) return;
    document.querySelectorAll('[data-glow]').forEach(function(el) {
      el.addEventListener('mousemove', function(e) {
        var r = el.getBoundingClientRect();
        el.style.setProperty('--gx', ((e.clientX - r.left) / r.width * 100) + '%');
        el.style.setProperty('--gy', ((e.clientY - r.top) / r.height * 100) + '%');
      });
    });
  }

  /* ── 8. SPA transitions ───────────────────────────────── */
  function initSPA() {
    if (REDUCED) return;
    document.addEventListener('click', function(e) {
      var link = e.target.closest('a[href]');
      if (!link) return;
      var href = link.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('http') ||
          href.startsWith('javascript') || link.hasAttribute('download') ||
          href.includes('logout') || href.includes('/static/')) return;

      e.preventDefault();
      var pageEl = document.querySelector('.page-content, .page, .hero, main, .auth-card');
      if (!pageEl) { window.location.href = href; return; }

      if (document.startViewTransition) {
        document.startViewTransition(function() { window.location.href = href; });
      } else {
        pageEl.style.transition = 'opacity 0.18s ease, filter 0.18s ease';
        pageEl.style.opacity = '0';
        pageEl.style.filter = 'blur(4px)';
        setTimeout(function() { window.location.href = href; }, 200);
      }
    });
  }

  /* ── 9. Image lazy fade-in ─────────────────────────────── */
  function initImgFade() {
    document.querySelectorAll('img[data-src]').forEach(function(img) {
      var obs = new IntersectionObserver(function(entries) {
        if (!entries[0].isIntersecting) return;
        obs.disconnect();
        img.src = img.dataset.src;
        img.onload = function() { img.style.opacity = '1'; };
      });
      obs.observe(img);
    });

    document.querySelectorAll('img').forEach(function(img) {
      img.style.transition = 'opacity 0.4s ease';
      if (img.complete && img.naturalWidth > 0) {
        img.style.opacity = '1';
      } else {
        img.style.opacity = '0';
        img.addEventListener('load', function() { img.style.opacity = '1'; });
        img.addEventListener('error', function() { img.style.opacity = '0.3'; });
      }
    });
  }

  /* ── 10. Sonar Scanner (prediction page) ─────────────── */
  function initSonarScanner() {
    var uploadForm = document.getElementById('uploadForm');
    var overlay = document.getElementById('processingOverlay');
    if (!uploadForm || !overlay) return;

    uploadForm.addEventListener('submit', function() {
      overlay.classList.add('active');

      var previewImg = document.getElementById('previewImg');
      var sonarCanvas = document.getElementById('sonarCanvas');
      var sonarLine = document.getElementById('sonarLine');
      var terminalText = document.getElementById('terminalText');

      if (previewImg && previewImg.src && sonarCanvas && previewImg.naturalWidth > 0) {
        var ctx = sonarCanvas.getContext('2d');
        var cw = 400, ch = 300;
        sonarCanvas.width = cw; sonarCanvas.height = ch;
        sonarCanvas.style.display = 'block';
        ctx.drawImage(previewImg, 0, 0, cw, ch);

        var imageData = ctx.getImageData(0, 0, cw, ch);
        var data = imageData.data;
        var gray = new Float32Array(cw * ch);
        for (var i = 0; i < cw * ch; i++) {
          var idx = i * 4;
          gray[i] = data[idx]*0.299 + data[idx+1]*0.587 + data[idx+2]*0.114;
        }
        var edges = new Float32Array(cw * ch);
        for (var y = 1; y < ch-1; y++) {
          for (var x = 1; x < cw-1; x++) {
            var gx = -gray[(y-1)*cw+(x-1)] + gray[(y-1)*cw+(x+1)] - 2*gray[y*cw+(x-1)] + 2*gray[y*cw+(x+1)] - gray[(y+1)*cw+(x-1)] + gray[(y+1)*cw+(x+1)];
            var gy = -gray[(y-1)*cw+(x-1)] - 2*gray[(y-1)*cw+x] - gray[(y-1)*cw+(x+1)] + gray[(y+1)*cw+(x-1)] + 2*gray[(y+1)*cw+x] + gray[(y+1)*cw+(x+1)];
            edges[y*cw+x] = Math.min(255, Math.sqrt(gx*gx + gy*gy));
          }
        }
        var outData = ctx.createImageData(cw, ch);
        for (var i = 0; i < cw*ch; i++) {
          var idx = i*4;
          var e = edges[i]/255;
          outData.data[idx]   = Math.round(6*e);
          outData.data[idx+1] = Math.round(214*e);
          outData.data[idx+2] = Math.round(240*e);
          outData.data[idx+3] = Math.round(220*e + 10);
        }
        ctx.putImageData(outData, 0, 0);
      }

      if (sonarLine) {
        sonarLine.style.display = 'block';
        var pos = 0;
        overlay._scanInterval = setInterval(function() {
          pos = (pos + 0.8) % 100;
          sonarLine.style.top = pos + '%';
        }, 30);
      }

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
          'Applying unsharp mask (\u03c3=1.5)...',
          'Auto-exposure normalization...',
          'Post-denoise bilateral filter...',
          'Computing UCIQE quality metric...',
          'Computing UIQM (Panetta et al. 2016)...',
          'Finalizing enhanced output...'
        ];
        var si = 0;
        overlay._textInterval = setInterval(function() {
          terminalText.textContent = statuses[si % statuses.length];
          si++;
        }, 600);
      }
    });
  }

  /* ── 11. Result Orchestration ──────────────────────────── */
  function initResultOrchestration() {
    if (REDUCED || !HAS_GSAP) return;
    var resultSection = document.querySelector('.result-section');
    if (!resultSection) return;

    var tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

    var classBar = resultSection.querySelector('.class-bar');
    if (classBar) tl.from(classBar, { opacity: 0, y: 24, filter: 'blur(6px)', duration: 0.6 });

    var compPanels = resultSection.querySelectorAll('.comp-panel');
    if (compPanels.length) {
      tl.from(compPanels, { opacity: 0, scale: 0.94, y: 18, duration: 0.65, stagger: 0.1 }, '-=0.3');
    }

    var confFill = resultSection.querySelector('.conf-bar-fill');
    if (confFill) {
      tl.to(confFill, { width: confFill.dataset.width || '0%', duration: 1, ease: 'power2.out' }, '-=0.4');
    }

    var metricCards = resultSection.querySelectorAll('.metric-card');
    if (metricCards.length) {
      tl.from(metricCards, { opacity: 0, y: 20, scale: 0.96, duration: 0.45, stagger: 0.06 }, '-=0.4');
    }

    resultSection.querySelectorAll('.mbar-fill').forEach(function(el) {
      tl.to(el, { width: el.dataset.width || '0%', duration: 0.8, ease: 'power2.out' }, '-=0.6');
    });

    resultSection.querySelectorAll('.val.enh').forEach(function(el) {
      var finalVal = parseFloat(el.textContent);
      if (isNaN(finalVal)) return;
      var obj = { val: 0 };
      tl.to(obj, {
        val: finalVal, duration: 1.1, ease: 'power2.out',
        onUpdate: function() {
          el.textContent = obj.val.toFixed(finalVal % 1 === 0 ? 0 : 2);
        }
      }, '-=1.0');
    });
  }

  /* ── 12. Page Enter ──────────────────────────────────── */
  function initPageEnter() {
    if (REDUCED) return;
    var p = document.querySelector('.page-content, .page, main, .auth-card');
    if (p) p.classList.add('page-enter');
  }

  /* ── INIT ────────────────────────────────────────────── */
  document.addEventListener('DOMContentLoaded', function() {
    initNav();
    initReveals();
    initStagger();
    initCountUp();
    initGlowTrack();
    initSPA();
    initImgFade();
    initSonarScanner();
    initResultOrchestration();
    initPageEnter();
  });

})();
