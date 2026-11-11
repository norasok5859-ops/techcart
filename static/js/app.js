// TechCart front-end: talks to the REST API (/api/...) for cart actions.
(function () {
  "use strict";

  const isLoggedIn = document.body.dataset.authenticated === "1";
  const loginUrl = document.body.dataset.loginUrl;

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  async function api(method, url, body) {
    const res = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    if (res.status !== 204) { try { data = await res.json(); } catch (e) { /* no body */ } }
    if (!res.ok) {
      const msg = (data && (data.detail || Object.values(data).flat().join(" "))) || "Something went wrong.";
      throw new Error(msg);
    }
    return data;
  }

  function toast(message, type) {
    const el = document.getElementById("tc-toast");
    document.getElementById("tc-toast-body").textContent = message;
    el.classList.remove("toast-success", "toast-error");
    el.classList.add(type === "error" ? "toast-error" : "toast-success");
    bootstrap.Toast.getOrCreateInstance(el, { delay: 2500 }).show();
  }

  function money(n) {
    return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function setBadge(count) {
    const badge = document.getElementById("cart-badge");
    if (!badge) return;
    badge.textContent = count;
    badge.classList.toggle("d-none", !count);
  }

  async function refreshCart() {
    const cart = await api("GET", "/api/cart/");
    setBadge(cart.count);
    const totalEl = document.getElementById("cart-total");
    if (totalEl) {
      totalEl.textContent = money(cart.total);
      document.getElementById("cart-count").textContent = cart.count;
      if (!cart.items.length) {
        document.getElementById("cart-content")?.remove();
        document.getElementById("cart-empty")?.classList.remove("d-none");
      }
    }
    return cart;
  }

  // ---- Add to cart buttons (product cards + detail page) ----
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".js-add-to-cart");
    if (!btn) return;
    e.preventDefault();
    if (!isLoggedIn) {
      window.location.href = loginUrl + "?next=" + encodeURIComponent(location.pathname);
      return;
    }
    const qtyInput = btn.dataset.qtyInput ? document.querySelector(btn.dataset.qtyInput) : null;
    const quantity = qtyInput ? Math.max(1, parseInt(qtyInput.value, 10) || 1) : 1;
    btn.disabled = true;
    const original = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    try {
      const item = await api("POST", "/api/cart/", { product_id: Number(btn.dataset.productId), quantity });
      await refreshCart();
      toast(`Added ${quantity} × ${item.product.name} to your cart`);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = original;
    }
  });

  // ---- Quantity +/- on product detail ----
  document.querySelectorAll(".js-qty-step").forEach((b) => b.addEventListener("click", () => {
    const input = b.parentElement.querySelector("input");
    const max = parseInt(input.max, 10) || 99;
    input.value = Math.min(max, Math.max(1, (parseInt(input.value, 10) || 1) + Number(b.dataset.step)));
  }));

  // ---- Cart page ----
  async function updateRow(row, quantity) {
    const id = row.dataset.itemId;
    const errorEl = row.querySelector(".js-row-error");
    errorEl.textContent = "";
    try {
      if (quantity < 1) {
        await api("DELETE", `/api/cart/${id}/`);
        row.remove();
        toast("Item removed from cart");
      } else {
        const item = await api("PATCH", `/api/cart/${id}/`, { quantity });
        row.querySelector(".js-cart-qty").value = item.quantity;
        row.querySelector(".js-row-subtotal").textContent = money(item.subtotal);
      }
      await refreshCart();
    } catch (err) {
      errorEl.textContent = err.message;
      const cart = await refreshCart();
      const current = cart.items.find((i) => String(i.id) === id);
      if (current) row.querySelector(".js-cart-qty").value = current.quantity;
    }
  }

  document.querySelectorAll(".js-cart-row").forEach((row) => {
    const input = row.querySelector(".js-cart-qty");
    row.querySelectorAll(".js-cart-step").forEach((b) => b.addEventListener("click", () => {
      updateRow(row, (parseInt(input.value, 10) || 1) + Number(b.dataset.step));
    }));
    input.addEventListener("change", () => updateRow(row, parseInt(input.value, 10) || 0));
    row.querySelector(".js-cart-remove").addEventListener("click", () => updateRow(row, 0));
  });
})();

// Clear a field's red error state as soon as the user edits it.
document.addEventListener("input", (e) => {
  if (e.target.classList && e.target.classList.contains("is-invalid")) {
    e.target.classList.remove("is-invalid");
    const fb = e.target.parentElement.querySelector(".invalid-feedback");
    if (fb) fb.remove();
  }
});
