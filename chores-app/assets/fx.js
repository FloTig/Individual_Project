/* Chores: motion and the internet layer.
 *
 * Done/Skip buttons carry data-act, data-chore and data-due. A tap plays the card's exit
 * animation first, then sends the action to Dash through the "pending" store, so the
 * server re-render never cuts an animation short. Taps that overlap are sent as one batch.
 * Confetti, the cat GIF reward and toasts live in a layer outside React, so re-renders
 * don't touch them.
 */
(function () {
  "use strict";

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var saveData = !!(navigator.connection && navigator.connection.saveData);
  var CAT_GIF = "https://cataas.com/cat/gif?width=320";
  var CATS = "/assets/cats/"; // meme cat stickers; see the README to swap them

  var CAPTIONS = [
    ["Chore", "Obliterated"],
    ["You did a thing", "The cat is proud"],
    ["+{p} points", "Very domestic"],
    ["I can has", "Clean house"],
    ["Productivity", "Maxxed"],
    ["Household", "Stability achieved"],
    ["Absolute", "Legend behaviour"],
    ["Not all heroes", "Wear capes"],
    ["That's", "So done"],
    ["Certified", "Clean™"],
  ];
  var MEOWS = ["mrrp", "meow", "prrr", ":3", "feed me", "nya~", "mew?", "hiss (affectionate)", "do ur chores"];
  var CONFETTI_EMOJI = ["🐟", "🐾", "✨", "⭐", "🧶"];
  var CONFETTI_COLORS = ["#8fc1a9", "#b9a7f0", "#f6c1a8", "#a9cbea", "#f2d68e", "#ffffff"];

  function catImg(file) {
    var img = document.createElement("img");
    img.className = "cat";
    img.alt = "";
    img.src = CATS + file;
    return img;
  }

  function pick(list) { return list[Math.floor(Math.random() * list.length)]; }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  /* ---------- Overlay ---------- */
  var layer, canvas, ctx;
  function ensureLayer() {
    if (layer) return;
    canvas = document.createElement("canvas");
    canvas.className = "fx-canvas";
    layer = document.createElement("div");
    layer.className = "fx-layer";
    layer.setAttribute("aria-live", "polite");
    document.body.append(canvas, layer);
    ctx = canvas.getContext("2d");
    sizeCanvas();
    window.addEventListener("resize", sizeCanvas);
  }
  function sizeCanvas() {
    var d = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = innerWidth * d;
    canvas.height = innerHeight * d;
    ctx.setTransform(d, 0, 0, d, 0, 0);
  }

  /* ---------- Cat GIFs: keep two preloaded, since the cat API fails now and then ---------- */
  var cats = [];
  var loading = 0;
  function loadCat(attempt) {
    return new Promise(function (resolve) {
      var img = new Image();
      img.decoding = "async";
      img.onload = function () { resolve(img); };
      img.onerror = function () { attempt < 2 ? loadCat(attempt + 1).then(resolve) : resolve(null); };
      img.src = CAT_GIF + "&n=" + Date.now() + attempt;
    });
  }
  function topUpCats() {
    if (saveData) return;
    while (cats.length + loading < 2) {
      loading++;
      loadCat(0).then(function (img) { loading--; if (img) cats.push(img); });
    }
  }

  /* ---------- Confetti (fish, paws, sparkles) ---------- */
  var parts = [];
  var raf = 0;
  var last = 0;
  function confetti(x, y) {
    if (reduce.matches) return;
    ensureLayer();
    for (var i = 0; i < 36; i++) {
      var angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 0.95;
      var speed = 0.45 + Math.random() * 0.55; // px per ms
      var emoji = i % 3 === 0 ? CONFETTI_EMOJI[i % CONFETTI_EMOJI.length] : null;
      parts.push({
        x: x, y: y,
        vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
        rot: Math.random() * 6.3, vrot: (Math.random() - 0.5) * 0.02,
        age: 0, ttl: 1100 + Math.random() * 700,
        emoji: emoji,
        size: emoji ? 18 + Math.random() * 12 : 7 + Math.random() * 6,
        color: CONFETTI_COLORS[i % CONFETTI_COLORS.length],
      });
    }
    if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); }
  }
  function frame(now) {
    var dt = Math.min(now - last, 40); // time-based, so 120 Hz phones don't double the speed
    last = now;
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    parts = parts.filter(function (p) { return p.age < p.ttl; });
    parts.forEach(function (p) {
      p.age += dt;
      p.vy += 0.0016 * dt;
      p.vx *= Math.pow(0.998, dt);
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.rot += p.vrot * dt;
      var fade = Math.min(1, (p.ttl - p.age) / (p.ttl * 0.3));
      ctx.save();
      ctx.globalAlpha = Math.max(0, fade);
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      if (p.emoji) {
        ctx.font = p.size + "px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(p.emoji, 0, 0);
      } else {
        ctx.fillStyle = p.color;
        ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2);
      }
      ctx.restore();
    });
    raf = parts.length ? requestAnimationFrame(frame) : 0;
  }

  /* ---------- The reward: a cat GIF with a meme caption over a spinning sunburst ---------- */
  var reward = null;
  function showReward(points) {
    ensureLayer();
    if (reward) reward.dismiss(true);
    var caption = pick(CAPTIONS).map(function (s) { return s.replace("{p}", points); });

    var el = document.createElement("div");
    el.className = "reward";
    el.innerHTML = '<div class="reward__rays"></div><figure class="reward__frame"></figure><span class="burst"></span>';
    var frameEl = el.querySelector("figure");
    var img = cats.shift();
    if (img) {
      img.className = "reward__img";
      img.alt = "";
      frameEl.append(img);
    } else {
      var stub = document.createElement("div");
      stub.className = "reward__img reward__img--fallback";
      frameEl.append(stub);
    }
    caption.forEach(function (text, i) {
      var m = document.createElement("span");
      m.className = "meme " + (i ? "meme--bottom" : "meme--top");
      m.textContent = text;
      frameEl.append(m);
    });
    el.querySelector(".burst").textContent = "+" + points;
    el.append(catImg("dance.webp"));
    layer.append(el);
    topUpCats();

    var center = "translate(-50%, -50%) ";
    if (!reduce.matches) {
      el.animate([
        { transform: center + "scale(0.2) rotate(-28deg)", opacity: 0 },
        { transform: center + "scale(1.07) rotate(4deg)", opacity: 1, offset: 0.6 },
        { transform: center + "scale(1) rotate(0deg)", opacity: 1 },
      ], { duration: 650, easing: "cubic-bezier(.2,.9,.3,1.1)" });
    }
    var gone = false;
    function dismiss(fast) {
      if (gone) return;
      gone = true;
      clearTimeout(timer);
      document.removeEventListener("pointerdown", onTap, true);
      if (reward === handle) reward = null;
      if (fast || reduce.matches) { el.remove(); return; }
      el.animate([
        { transform: center + "scale(1) rotate(0deg)", opacity: 1 },
        { transform: center + "translateY(40px) scale(0.6) rotate(12deg)", opacity: 0 },
      ], { duration: 320, easing: "cubic-bezier(.5,0,.75,0)", fill: "forwards" }).finished.then(function () { el.remove(); });
    }
    function onTap() { dismiss(false); }
    var handle = { dismiss: dismiss };
    var timer = setTimeout(dismiss, 2600);
    // Any tap clears it, and the tap still goes through to whatever is underneath.
    setTimeout(function () { if (!gone) document.addEventListener("pointerdown", onTap, true); }, 250);
    reward = handle;
  }

  /* ---------- Toast (Skip) ---------- */
  function toast(catFile, text) {
    ensureLayer();
    var el = document.createElement("div");
    el.className = "toast";
    el.setAttribute("role", "status");
    var s = catImg(catFile);
    el.append(s, document.createTextNode(text));
    layer.append(el);
    var base = "translateX(-50%) ";
    if (reduce.matches) { setTimeout(function () { el.remove(); }, 1800); return; }
    el.animate([
      { transform: base + "translateY(40px) scale(0.8)", opacity: 0 },
      { transform: base + "translateY(0) scale(1)", opacity: 1 },
    ], { duration: 450, easing: "cubic-bezier(.34,1.56,.64,1)" });
    s.animate([
      { transform: "rotate(0deg)" }, { transform: "rotate(-18deg)" }, { transform: "rotate(14deg)" }, { transform: "rotate(0deg)" },
    ], { duration: 600, delay: 200 });
    setTimeout(function () {
      el.animate([
        { transform: base + "translateY(0)", opacity: 1 },
        { transform: base + "translateY(30px)", opacity: 0 },
      ], { duration: 260, easing: "ease-in", fill: "forwards" }).finished.then(function () { el.remove(); });
    }, 1800);
  }

  /* ---------- Card exit: pop, fly off, collapse the gap ---------- */
  function exitCard(card, dir) {
    var h = card.offsetHeight;
    var cs = getComputedStyle(card);
    var anims = [];
    card.classList.add("is-leaving");
    if (reduce.matches) {
      anims.push(card.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 150, fill: "forwards" }));
    } else {
      anims.push(card.animate([
        { transform: "none", opacity: 1, easing: "cubic-bezier(.2,.8,.3,1.4)" },
        { transform: "scale(1.04)", opacity: 1, offset: 0.28, easing: "cubic-bezier(.55,0,.8,.2)" },
        { transform: "translateX(" + dir * 120 + "%) rotate(" + dir * 10 + "deg) scale(.92)", opacity: 0 },
      ], { duration: 560, fill: "forwards" }));
    }
    anims.push(card.animate([
      { height: h + "px", paddingTop: cs.paddingTop, paddingBottom: cs.paddingBottom, marginBottom: cs.marginBottom },
      { height: "0px", paddingTop: "0px", paddingBottom: "0px", marginBottom: "0px" },
    ], { duration: reduce.matches ? 1 : 320, delay: reduce.matches ? 150 : 380, easing: "cubic-bezier(.4,0,.2,1)", fill: "forwards" }));

    // Normally the re-render removes this card. If it doesn't (the action failed), put it back.
    setTimeout(function () {
      if (!card.isConnected) return;
      anims.forEach(function (a) { a.cancel(); });
      card.classList.remove("is-leaving");
      card.querySelectorAll(".is-done").forEach(function (b) { b.classList.remove("is-done"); });
    }, 6000);

    var end = anims[anims.length - 1].finished.catch(function () {});
    return Promise.race([end, wait(reduce.matches ? 400 : 900)]);
  }

  /* ---------- Done / Skip ---------- */
  var inflight = 0;
  var outbox = [];
  function flush() {
    if (inflight || !outbox.length) return;
    var dc = window.dash_clientside;
    if (!dc || !dc.set_props) return;
    dc.set_props("pending", { data: { actions: outbox.splice(0), at: Date.now() } });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("button[data-act]");
    if (!btn) return;
    var card = btn.closest(".chore");
    if (!card || card.classList.contains("is-leaving")) return;
    var done = btn.dataset.act === "done";
    var action = { act: btn.dataset.act, chore: btn.dataset.chore, due: btn.dataset.due };

    if (done) {
      var r = btn.getBoundingClientRect();
      btn.classList.add("is-done");
      confetti(r.left + r.width / 2, r.top + r.height / 2);
      showReward(parseInt(card.dataset.points, 10) || 1);
    } else {
      toast("thumbs.png", "Skipped. It's fine.");
    }
    inflight++;
    exitCard(card, done ? 1 : -1).then(function () {
      inflight--;
      outbox.push(action);
      flush();
    });
  });

  /* ---------- Copy buttons in the settings sheet (widget script, backup link) ---------- */
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) { // plain http (testing on wifi): the old way
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.cssText = "position:fixed;top:0;opacity:0";
      document.body.append(ta);
      ta.select();
      ta.setSelectionRange(0, text.length);
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (err) { /* reject below */ }
      ta.remove();
      ok ? resolve() : reject();
    });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest && e.target.closest("[data-copy]");
    if (!btn) return;
    // The server doesn't know which address you opened the app on; the page does.
    var text = btn.getAttribute("data-copy").split("__ORIGIN__").join(location.origin);
    copyText(text).then(
      function () { toast("hearts.png", btn.getAttribute("data-copied") || "Copied"); },
      function () { toast("thumbs.png", "Couldn't copy. Try again from the installed app."); }
    );
  });

  /* ---------- The mood cat in the header talks back ---------- */
  document.addEventListener("click", function (e) {
    var cat = e.target.closest && e.target.closest("#mood");
    if (!cat) return;
    ensureLayer();
    if (!reduce.matches) {
      cat.animate([
        { transform: "rotate(8deg) scale(1)" }, { transform: "rotate(-16deg) scale(1.25)" },
        { transform: "rotate(18deg) scale(1.1)" }, { transform: "rotate(8deg) scale(1)" },
      ], { duration: 520, easing: "cubic-bezier(.34,1.56,.64,1)" });
    }
    var r = cat.getBoundingClientRect();
    var b = document.createElement("div");
    b.className = "bubble";
    b.textContent = pick(MEOWS);
    b.style.left = r.left + r.width * 0.6 + "px";
    b.style.top = r.bottom + 4 + "px";
    layer.append(b);
    b.animate([
      { transform: "translateY(8px) scale(.6)", opacity: 0 },
      { transform: "translateY(0) scale(1)", opacity: 1, offset: 0.2 },
      { transform: "translateY(0) scale(1)", opacity: 1, offset: 0.8 },
      { transform: "translateY(-10px) scale(.95)", opacity: 0 },
    ], { duration: 1400, easing: "ease-out", fill: "forwards" }).finished.then(function () { b.remove(); });
  });

  /* ---------- Cat of the day: retry a failed GIF, then fall back to a sticker ---------- */
  document.addEventListener("error", function (e) {
    var img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    var frameEl = img.closest(".catframe");
    if (!frameEl) return;
    var tries = +(img.dataset.tries || 0);
    if (tries < 2) {
      img.dataset.tries = tries + 1;
      img.src = img.src.replace(/&n=\d+$/, "") + "&n=" + Date.now();
    } else {
      frameEl.classList.add("is-broken");
    }
  }, true);

  /* ---------- Bump the Today headline when its count changes ---------- */
  var lastHeadline = null;
  var checkQueued = false;
  new MutationObserver(function () {
    if (checkQueued) return;
    checkQueued = true;
    requestAnimationFrame(function () {
      checkQueued = false;
      var h = document.querySelector("#today-hero .headline");
      if (!h) return;
      var text = h.textContent;
      if (lastHeadline !== null && text !== lastHeadline && !reduce.matches) {
        h.animate([
          { transform: "scale(1)" }, { transform: "scale(1.06) rotate(-1deg)" }, { transform: "scale(1)" },
        ], { duration: 480, easing: "cubic-bezier(.34,1.56,.64,1)" });
      }
      lastHeadline = text;
    });
  }).observe(document.documentElement, { subtree: true, childList: true, characterData: true });

  // Start fetching reward cats once the page has settled.
  window.addEventListener("load", function () { setTimeout(topUpCats, 1200); });
})();
