(function () {
  "use strict";

  function setPos(root, value) {
    var v = Math.max(0, Math.min(100, Number(value)));
    root.style.setProperty("--pos", v + "%");
    var range = root.querySelector(".compare-range");
    if (range && range.value !== String(Math.round(v))) range.value = String(Math.round(v));
  }

  function posFromEvent(root, ev) {
    var rect = root.getBoundingClientRect();
    var x = (ev.touches && ev.touches[0] ? ev.touches[0].clientX : ev.clientX) - rect.left;
    return (x / rect.width) * 100;
  }

  function bind(root) {
    if (root.dataset.bound) return;
    root.dataset.bound = "1";
    var range = root.querySelector(".compare-range");
    if (range) {
      setPos(root, range.value || 50);
      range.addEventListener("input", function () { setPos(root, range.value); });
    } else {
      setPos(root, 50);
    }

    var dragging = false;
    function start(ev) {
      if (ev.target && ev.target.classList && ev.target.classList.contains("compare-range")) return;
      dragging = true;
      root.classList.add("is-dragging");
      setPos(root, posFromEvent(root, ev));
    }
    function move(ev) {
      if (!dragging) return;
      ev.preventDefault();
      setPos(root, posFromEvent(root, ev));
    }
    function end() {
      dragging = false;
      root.classList.remove("is-dragging");
    }

    root.addEventListener("pointerdown", start);
    window.addEventListener("pointermove", move, { passive: false });
    window.addEventListener("pointerup", end);
    root.addEventListener("touchstart", start, { passive: true });
    window.addEventListener("touchmove", move, { passive: false });
    window.addEventListener("touchend", end);
  }

  function init() {
    document.querySelectorAll("[data-compare]").forEach(bind);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
