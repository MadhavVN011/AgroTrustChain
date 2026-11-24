// AgroTrustChain UI behaviour: mobile sidebar, table search, copy buttons, confirmations.
(function () {
  "use strict";

  // Mobile sidebar
  document.addEventListener("click", function (event) {
    if (event.target.closest("[data-sidebar-toggle]")) {
      document.body.classList.toggle("sidebar-open");
    } else if (event.target.closest(".scrim")) {
      document.body.classList.remove("sidebar-open");
    }
  });

  // Table search: <input data-table-filter="tableId">
  document.querySelectorAll("[data-table-filter]").forEach(function (input) {
    var table = document.getElementById(input.getAttribute("data-table-filter"));
    if (!table) return;
    var rows = Array.prototype.slice.call(table.tBodies[0].rows).filter(function (r) { return !r.hasAttribute("data-empty"); });
    var counter = document.querySelector("[data-count-for='" + table.id + "']");
    var noMatch = table.querySelector("[data-no-match]");
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      var shown = 0;
      rows.forEach(function (row) {
        var hit = !q || row.textContent.toLowerCase().indexOf(q) !== -1;
        row.hidden = !hit;
        if (hit) shown++;
      });
      if (noMatch) noMatch.hidden = shown !== 0;
      if (counter) counter.textContent = shown === rows.length ? rows.length + " total" : shown + " of " + rows.length;
    });
  });

  // Copy to clipboard: <button data-copy="text">
  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-copy]");
    if (!button) return;
    event.preventDefault();
    var text = button.getAttribute("data-copy");
    var done = function () {
      button.classList.add("copied");
      button.setAttribute("title", "Copied");
      setTimeout(function () { button.classList.remove("copied"); button.setAttribute("title", "Copy"); }, 1400);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done);
    } else {
      var area = document.createElement("textarea");
      area.value = text; document.body.appendChild(area); area.select();
      try { document.execCommand("copy"); done(); } finally { document.body.removeChild(area); }
    }
  });

  // Theme: light / dark. The choice is stored; until then the system setting is followed.
  var root = document.documentElement;
  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function storedTheme() {
    try { return localStorage.getItem("theme"); } catch (e) { return null; }
  }
  function applyTheme(theme) {
    root.setAttribute("data-theme", theme);
    document.querySelectorAll("[data-theme-toggle]").forEach(function (button) {
      var label = theme === "dark" ? "Switch to light theme" : "Switch to dark theme";
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
      button.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    });
  }
  applyTheme(root.getAttribute("data-theme") || (media && media.matches ? "dark" : "light"));
  if (media && media.addEventListener) {
    media.addEventListener("change", function (e) { if (!storedTheme()) applyTheme(e.matches ? "dark" : "light"); });
  }

  document.addEventListener("click", function (event) {
    var button = event.target.closest("[data-theme-toggle]");
    if (!button) return;
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    var commit = function () {
      applyTheme(next);
      try { localStorage.setItem("theme", next); } catch (e) { /* private mode */ }
    };

    if (reduceMotion) { commit(); return; }

    if (document.startViewTransition) {
      // Circular reveal from the centre of the toggle to the farthest corner.
      var rect = button.getBoundingClientRect();
      var x = rect.left + rect.width / 2;
      var y = rect.top + rect.height / 2;
      var radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
      var transition = document.startViewTransition(commit);
      transition.ready.then(function () {
        root.animate(
          { clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + radius + "px at " + x + "px " + y + "px)"] },
          { duration: 560, easing: "cubic-bezier(.4, 0, .2, 1)", pseudoElement: "::view-transition-new(root)" }
        );
      });
      return;
    }

    // Fallback: cross-fade colours.
    root.classList.add("theme-fade");
    commit();
    setTimeout(function () { root.classList.remove("theme-fade"); }, 400);
  });

  // Confirmation before submitting: <form data-confirm="message">
  document.addEventListener("submit", function (event) {
    var message = event.target.getAttribute && event.target.getAttribute("data-confirm");
    if (message && !window.confirm(message)) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);
})();
