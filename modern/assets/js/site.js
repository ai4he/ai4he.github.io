/* Human-AI Empowerment Lab — site interactions (no dependencies) */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var root = document.documentElement;

  /* ---------- Theme ---------- */
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  var toggle = $(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var current = root.getAttribute("data-theme");
      if (!current) current = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      var next = current === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      store("haie-theme", next);
    });
  }

  /* ---------- Mobile nav ---------- */
  var navBtn = $(".nav-toggle");
  if (navBtn) {
    navBtn.addEventListener("click", function () {
      var open = document.body.classList.toggle("nav-open");
      navBtn.setAttribute("aria-expanded", String(open));
    });
    $$("#main-nav a").forEach(function (a) { a.addEventListener("click", function () { document.body.classList.remove("nav-open"); }); });
  }

  /* ---------- Hero tiles (echo of the HAIE logo) ---------- */
  var tiles = $("#hero-tiles");
  if (tiles) {
    var colors = ["#2CCBF9", "#F2B30C", "#6119F9", "#F9604F", "#0A6BF9", "#E2323F", "#6119F9", "#2CCBF9"];
    var n = 12 * 10, spans = [];
    for (var i = 0; i < n; i++) {
      var s = document.createElement("span");
      s.style.setProperty("--tc", colors[i % colors.length]);
      tiles.appendChild(s);
      spans.push(s);
    }
    var cx = 7.2, cy = 4.2;
    function paint(t) {
      spans.forEach(function (sp, k) {
        var x = k % 12, y = Math.floor(k / 12);
        var d = Math.hypot((x - cx) / 1.25, y - cy);
        var wave = 0.5 + 0.5 * Math.sin(t / 1600 + x * 0.55 + y * 0.35);
        var p = Math.max(0, 1 - d / 7.4);
        var keep = ((k * 7919) % 13) / 13 < p * 1.05;
        sp.style.setProperty("--s", keep ? (0.28 + 0.62 * p * (0.75 + 0.25 * wave)).toFixed(3) : "0.08");
        sp.style.setProperty("--o", keep ? (0.25 + 0.75 * p).toFixed(3) : "0.06");
      });
    }
    paint(0);
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduce) setInterval(function () { paint(Date.now()); }, 2400);
  }

  /* ---------- Expand/collapse panels ---------- */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-toggle]");
    if (btn) {
      var panel = document.getElementById(btn.getAttribute("data-toggle"));
      if (panel) {
        var open = btn.getAttribute("aria-expanded") === "true";
        btn.setAttribute("aria-expanded", String(!open));
        panel.hidden = open;
      }
      return;
    }
    var copy = e.target.closest("[data-copy], [data-copy-text]");
    if (copy) {
      var text = copy.hasAttribute("data-copy-text") ? copy.getAttribute("data-copy-text")
        : ($(copy.getAttribute("data-copy")) || {}).textContent || "";
      copyText(text.trim(), copy);
      return;
    }
    if (e.target.closest("[data-print]")) { window.print(); return; }
    var node = e.target.closest(".net-node[data-href]");
    if (node) { window.location.href = rootPath() + node.getAttribute("data-href"); }
  });

  function rootPath() {
    var css = $('link[rel="stylesheet"][href*="assets/css/site.css"]');
    return css ? css.getAttribute("href").split("assets/css/site.css")[0] : "";
  }

  function copyText(text, btn) {
    var done = function () {
      var old = btn.innerHTML;
      btn.classList.add("is-copied");
      btn.innerHTML = btn.innerHTML.replace(/Copy( BibTeX| citation| profile link)?/, "Copied");
      setTimeout(function () { btn.innerHTML = old; btn.classList.remove("is-copied"); }, 1500);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done, function () {});
    } else {
      var ta = document.createElement("textarea");
      ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
      document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); done(); } catch (err) {}
      ta.remove();
    }
  }

  /* ---------- Tooltip for [data-tip] (charts, map, network) ---------- */
  var tip = $("#tooltip");
  function showTip(el, x, y) {
    if (!tip) return;
    tip.textContent = el.getAttribute("data-tip");
    tip.hidden = false;
    var w = tip.offsetWidth, h = tip.offsetHeight;
    var left = Math.min(window.innerWidth - w - 10, Math.max(10, x - w / 2));
    var top = y - h - 14;
    if (top < 8) top = y + 18;
    tip.style.left = left + "px"; tip.style.top = top + "px";
  }
  function hideTip() { if (tip) tip.hidden = true; }
  document.addEventListener("mousemove", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (el) showTip(el, e.clientX, e.clientY); else hideTip();
  });
  document.addEventListener("focusin", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip]");
    if (el) { var r = el.getBoundingClientRect(); showTip(el, r.left + r.width / 2, r.top); }
  });
  document.addEventListener("focusout", hideTip);
  window.addEventListener("scroll", hideTip, { passive: true });

  /* ---------- Co-authorship network highlight ---------- */
  var net = $(".coauthor-net");
  if (net) {
    var lines = $$(".net-edges line", net);
    var nodes = $$(".net-node", net);
    var byId = {};
    nodes.forEach(function (nd) { byId[nd.getAttribute("data-id")] = nd; });
    function focus(id) {
      net.classList.add("is-focus");
      var on = {}; on[id] = true;
      lines.forEach(function (l) {
        var a = l.getAttribute("data-a"), b = l.getAttribute("data-b");
        var hit = a === id || b === id;
        l.classList.toggle("is-on", hit);
        if (hit) { on[a] = true; on[b] = true; }
      });
      nodes.forEach(function (nd) { nd.classList.toggle("is-on", !!on[nd.getAttribute("data-id")]); });
    }
    function clear() { net.classList.remove("is-focus"); lines.forEach(function (l) { l.classList.remove("is-on"); }); nodes.forEach(function (nd) { nd.classList.remove("is-on"); }); }
    nodes.forEach(function (nd) {
      nd.addEventListener("mouseenter", function () { focus(nd.getAttribute("data-id")); });
      nd.addEventListener("focus", function () { focus(nd.getAttribute("data-id")); });
      nd.addEventListener("mouseleave", clear);
      nd.addEventListener("blur", clear);
      nd.addEventListener("keydown", function (e) { if (e.key === "Enter" && nd.getAttribute("data-href")) window.location.href = rootPath() + nd.getAttribute("data-href"); });
    });
  }

  /* ---------- Publications filtering ---------- */
  var list = $("#pub-list");
  if (list) {
    var q = $("#pub-search"), fy = $("#pub-year"), ft = $("#pub-type"), fa = $("#pub-area"), fp = $("#pub-person");
    var items = $$(".pub", list), groups = $$(".year-group", list);
    var count = $("#pub-count"), empty = $("#pub-empty");
    var params = new URLSearchParams(window.location.search);
    if (params.get("area")) fa.value = params.get("area");
    if (params.get("type")) ft.value = params.get("type");
    if (params.get("year")) fy.value = params.get("year");
    if (params.get("person")) fp.value = params.get("person");
    if (params.get("q")) q.value = params.get("q");
    function apply() {
      var term = (q.value || "").trim().toLowerCase().split(/\s+/).filter(Boolean);
      var shown = 0;
      items.forEach(function (it) {
        var ok = (!fy.value || it.dataset.year === fy.value) &&
          (!ft.value || it.dataset.type === ft.value) &&
          (!fa.value || (" " + it.dataset.areas + " ").indexOf(" " + fa.value + " ") > -1) &&
          (!fp.value || (" " + it.dataset.people).indexOf(" " + fp.value + " ") > -1) &&
          term.every(function (t) { return it.dataset.search.indexOf(t) > -1; });
        it.hidden = !ok;
        if (ok) shown++;
      });
      groups.forEach(function (g) { g.hidden = !$$(".pub", g).some(function (it) { return !it.hidden; }); });
      var filtered = term.length || fy.value || ft.value || fa.value || fp.value;
      count.textContent = filtered ? ("Showing " + shown + " of " + items.length + " publications") : ("Showing all " + items.length + " publications");
      empty.hidden = shown > 0;
      var p = new URLSearchParams();
      if (q.value) p.set("q", q.value);
      if (fy.value) p.set("year", fy.value);
      if (ft.value) p.set("type", ft.value);
      if (fa.value) p.set("area", fa.value);
      if (fp.value) p.set("person", fp.value);
      var qs = p.toString();
      history.replaceState(null, "", window.location.pathname + (qs ? "?" + qs : "") + window.location.hash);
    }
    [fy, ft, fa, fp].forEach(function (s) { s.addEventListener("change", apply); });
    var timer;
    q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(apply, 120); });
    $$("[data-set-type]").forEach(function (b) {
      b.addEventListener("click", function () {
        ft.value = ft.value === b.dataset.setType ? "" : b.dataset.setType;
        apply();
        $("#search").scrollIntoView({ behavior: "smooth" });
      });
    });
    if (window.location.hash === "#search") setTimeout(function () { q.focus(); }, 300);
    apply();
  }

  /* ---------- Simple chip filters ---------- */
  function chipFilter(attr, itemsSel, test) {
    var chips = $$("[" + attr + "]");
    if (!chips.length) return;
    chips.forEach(function (c) {
      c.addEventListener("click", function () {
        chips.forEach(function (x) { x.classList.toggle("is-active", x === c); });
        var v = c.getAttribute(attr);
        $$(itemsSel).forEach(function (it) { it.hidden = !(v === "all" || test(it, v)); });
        if (attr === "data-filter-news") {
          $$(".timeline-year").forEach(function (y) {
            var el = y.nextElementSibling, any = false;
            while (el && !el.classList.contains("timeline-year")) { if (!el.hidden) any = true; el = el.nextElementSibling; }
            y.hidden = !any;
          });
        }
      });
    });
  }
  chipFilter("data-filter-alumni", "#alumni-grid .alum", function (it, v) { return it.dataset.group === v; });
  chipFilter("data-filter-news", "#news-list .timeline-item", function (it, v) { return it.dataset.kind === v; });
  chipFilter("data-filter-projects", "#project-grid .project-wrap", function (it, v) {
    if (v === "funded") return it.dataset.funded === "yes";
    return it.dataset.status === v;
  });

  /* ---------- Reveal on scroll ---------- */
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    var targets = $$(".thrust-card, .card, .person-tile, .grant-card, .soft-card, .course-card, .inst-card, .milestones li, .approach, .mvv-item, .join-card, .explore-card");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { if (en.isIntersecting) { en.target.classList.add("is-in"); io.unobserve(en.target); } });
    }, { rootMargin: "0px 0px -40px 0px" });
    targets.forEach(function (t, k) {
      var r = t.getBoundingClientRect();
      if (r.top > window.innerHeight) { t.classList.add("reveal"); t.style.transitionDelay = (k % 4) * 60 + "ms"; io.observe(t); }
    });
  }
})();
