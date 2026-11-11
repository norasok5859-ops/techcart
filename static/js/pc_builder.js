// PC builder page: the server (/api/pc-builder/check/) decides compatibility; this script
// shows the result, marks parts that clash with the current picks, and adds the build to the cart.
(function () {
  "use strict";

  const STORAGE_KEY = "techcart-pc-build";
  const slots = [...document.querySelectorAll(".tc-slot")].map((el) => el.dataset.slot);
  const addBtn = document.getElementById("build-add");
  const isLoggedIn = document.body.dataset.authenticated === "1";
  let lastReport = null;
  let pending = null;

  // Quick-start presets: matched by product name so they survive re-seeding.
  const PRESETS = {
    budget: {
      cpu: "Intel Core i5-14400F", motherboard: "Gigabyte B760M DS3H DDR4",
      ram: "Corsair Vengeance LPX 16GB (2×8GB) DDR4-3200", gpu: "ASUS Dual GeForce RTX 4060 OC 8GB",
      storage: "Crucial P3 Plus 1TB NVMe SSD", psu: "Cooler Master MWE 650 Bronze V2",
      case: "Cooler Master MasterBox Q300L",
    },
    highend: {
      cpu: "AMD Ryzen 7 7800X3D", motherboard: "ASUS TUF Gaming B650-PLUS WiFi",
      ram: "G.Skill Trident Z5 RGB 64GB (2×32GB) DDR5-6400", gpu: "Gigabyte GeForce RTX 4080 SUPER Gaming OC 16GB",
      storage: "WD_BLACK SN850X 2TB NVMe SSD", psu: "Seasonic Focus GX-850 850W 80+ Gold",
      case: "Lian Li LANCOOL 216",
    },
  };

  const money = (n) => "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const escapeHtml = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function getCookie(name) {
    const m = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[2]) : null;
  }

  function selected(slot) {
    return document.querySelector(`input[name="slot-${slot}"]:checked`);
  }

  function currentParts() {
    const parts = {};
    slots.forEach((slot) => {
      const input = selected(slot);
      if (input && input.value) parts[slot] = Number(input.value);
    });
    return parts;
  }

  function save() {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(currentParts())); } catch (e) { /* storage unavailable */ }
  }

  function restore() {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch (e) { saved = null; }
    if (!saved) return;
    Object.entries(saved).forEach(([slot, id]) => {
      const input = document.querySelector(`input[name="slot-${slot}"][value="${id}"]`);
      if (input && !input.disabled) input.checked = true;
    });
  }

  // Mark options that clash with the other picks (quick visual hint; the server check is authoritative).
  function markConflicts() {
    const pick = (slot) => selected(slot) && selected(slot).value ? selected(slot).dataset : null;
    const cpu = pick("cpu"), mb = pick("motherboard"), ram = pick("ram"), cs = pick("case");
    document.querySelectorAll(".tc-slot input.btn-check").forEach((input) => {
      const d = input.dataset;
      const slot = input.name.replace("slot-", "");
      let reason = "";
      if (slot === "cpu" && mb && d.socket && d.socket !== mb.socket) reason = `Needs a ${d.socket} motherboard`;
      if (slot === "motherboard") {
        if (cpu && d.socket !== cpu.socket) reason = `Socket ${d.socket}, your CPU is ${cpu.socket}`;
        else if (ram && d.memory !== ram.memory) reason = `Takes ${d.memory}, your memory is ${ram.memory}`;
        else if (cs && cs.forms && !cs.forms.split(",").includes(d.form)) reason = `${d.form} won't fit your case`;
      }
      if (slot === "ram" && mb && d.memory && d.memory !== mb.memory) reason = `Board needs ${mb.memory}`;
      if (slot === "case" && mb && d.forms && !d.forms.split(",").includes(mb.form)) reason = `Too small for ${mb.form}`;
      const label = document.querySelector(`label[for="${input.id}"]`);
      if (!label) return;
      label.classList.toggle("is-conflict", !!reason);
      const flag = label.querySelector(".tc-part-flag span");
      if (flag) flag.textContent = reason;
    });
  }

  function renderSummary(report) {
    slots.forEach((slot) => {
      const input = selected(slot);
      const li = document.querySelector(`[data-summary="${slot}"]`);
      const choice = document.querySelector(`#slot-${slot} .js-slot-choice`);
      const has = input && input.value;
      li.querySelector(".tc-build-part").textContent = has ? input.dataset.name : "—";
      li.querySelector(".tc-build-price").textContent = has ? money(input.dataset.price) : "";
      li.classList.toggle("is-set", !!has);
      choice.textContent = has ? `${input.dataset.name} · ${money(input.dataset.price)}` : (input && input.value === "" ? "No graphics card" : "Not chosen yet");
      document.getElementById(`slot-${slot}`).classList.toggle("is-done", !!has || (input && input.value === ""));
    });
    if (!report) return;

    document.getElementById("build-total").textContent = money(report.total);
    const psuInput = selected("psu");
    const psuW = psuInput && psuInput.value ? parseInt(psuInput.dataset.watts || "0", 10) : 0;
    document.getElementById("build-watts").textContent = `~${report.estimated_watts}W`;
    const bar = document.getElementById("build-power-bar");
    const note = document.getElementById("build-power-note");
    if (psuW) {
      const pct = Math.min(100, Math.round((report.estimated_watts / psuW) * 100));
      bar.style.width = pct + "%";
      bar.className = "progress-bar " + (pct > 100 || report.estimated_watts > psuW ? "bg-danger" : pct > 72 ? "bg-warning" : "bg-success");
      note.textContent = `${pct}% of your ${psuW}W power supply · ${report.recommended_psu_watts}W+ recommended`;
    } else {
      bar.style.width = "0%";
      note.textContent = `We recommend a ${report.recommended_psu_watts}W or bigger power supply.`;
    }

    const box = document.getElementById("build-issues");
    const items = report.issues.map((i) =>
      `<div class="tc-issue tc-issue-${i.level}"><i class="bi bi-${i.level === "error" ? "x-octagon-fill" : "exclamation-triangle-fill"}"></i><span>${escapeHtml(i.message)}</span></div>`);
    if (!report.issues.length && report.complete) {
      items.push('<div class="tc-issue tc-issue-ok"><i class="bi bi-check-circle-fill"></i><span>All parts are compatible. Ready to order!</span></div>');
    } else if (!report.issues.length) {
      items.push('<div class="tc-issue tc-issue-ok"><i class="bi bi-check-circle-fill"></i><span>No problems so far.</span></div>');
    }
    box.innerHTML = items.join("");

    addBtn.disabled = !report.ready;
    document.getElementById("build-hint").textContent = report.ready
      ? (isLoggedIn ? "Adds one of each part to your cart." : "You'll be asked to log in first.")
      : (report.missing.length ? "Still to choose: " + report.missing.join(", ") : "Fix the problems above to continue.");
  }

  async function check() {
    save();
    markConflicts();
    renderSummary(lastReport);
    const body = JSON.stringify({ parts: currentParts() });
    pending = body;
    try {
      const res = await fetch("/api/pc-builder/check/", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
        body,
      });
      const data = await res.json();
      if (pending !== body) return; // a newer check is on its way
      if (!res.ok) throw new Error(data.detail || "Could not check the build.");
      lastReport = data;
      renderSummary(data);
    } catch (err) {
      document.getElementById("build-issues").innerHTML =
        `<div class="tc-issue tc-issue-error"><i class="bi bi-wifi-off"></i><span>${escapeHtml(err.message)}</span></div>`;
    }
  }

  document.querySelectorAll(".tc-slot input.btn-check").forEach((i) => i.addEventListener("change", check));

  function applyPreset(key) {
    const preset = PRESETS[key];
    if (!preset) return false;
    slots.forEach((slot) => {
      const name = preset[slot];
      const input = [...document.querySelectorAll(`input[name="slot-${slot}"]`)].find((i) => i.dataset.name === name);
      if (input && !input.disabled) input.checked = true;
    });
    return true;
  }

  document.querySelectorAll(".js-preset").forEach((btn) => btn.addEventListener("click", () => {
    applyPreset(btn.dataset.preset);
    check();
    document.getElementById("build-summary").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }));

  document.getElementById("build-reset").addEventListener("click", () => {
    document.querySelectorAll(".tc-slot input.btn-check").forEach((i) => { i.checked = i.value === "" ; });
    lastReport = null;
    document.getElementById("build-total").textContent = "$0.00";
    check();
  });

  addBtn.addEventListener("click", async () => {
    if (!isLoggedIn) {
      save();
      window.location.href = document.body.dataset.loginUrl + "?next=" + encodeURIComponent(location.pathname);
      return;
    }
    addBtn.disabled = true;
    const original = addBtn.innerHTML;
    addBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Adding…';
    try {
      const res = await fetch("/api/pc-builder/add-to-cart/", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
        body: JSON.stringify({ parts: currentParts() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Could not add the build to your cart.");
      const badge = document.getElementById("cart-badge");
      if (badge) { badge.textContent = data.cart_count; badge.classList.remove("d-none"); }
      addBtn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Added to cart';
      document.getElementById("build-hint").innerHTML = 'Your build is in the cart. <a href="/cart/" class="fw-semibold">Go to checkout →</a>';
      setTimeout(() => { addBtn.innerHTML = original; addBtn.disabled = false; }, 2500);
    } catch (err) {
      document.getElementById("build-issues").insertAdjacentHTML("afterbegin",
        `<div class="tc-issue tc-issue-error"><i class="bi bi-x-octagon-fill"></i><span>${escapeHtml(err.message)}</span></div>`);
      addBtn.innerHTML = original;
      addBtn.disabled = false;
    }
  });

  // /build-pc/?preset=budget opens a ready-made build; otherwise continue the visitor's last build.
  if (!applyPreset(new URLSearchParams(location.search).get("preset"))) restore();
  check();
})();
