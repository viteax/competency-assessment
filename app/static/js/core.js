// Общие помощники интерфейса: DOM, запросы к API, сессия, навигация.

const app = document.getElementById("app");
const nav = document.getElementById("nav");

// --- DOM ---------------------------------------------------------------------

// Создание DOM без innerHTML, чтобы данные из БД не исполнялись как разметка.
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (key === "class") el.className = value;
    else el.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}

// Заменяет содержимое элемента; вложенные массивы и пустые значения допустимы.
export function fill(el, ...nodes) {
  el.replaceChildren(
    ...nodes.flat(Infinity).filter((n) => n !== null && n !== undefined && n !== false),
  );
}

export function render(...nodes) {
  fill(app, ...nodes);
}

export function errorBox() {
  const box = h("div", { class: "error", role: "alert" });
  return {
    el: box,
    show(error) { box.textContent = error.message || String(error); },
    clear() { box.textContent = ""; },
  };
}

// Высота textarea по содержимому (элемент уже должен быть в документе).
export function autoHeight(el) {
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight + 2}px`;
}

export function masteryBadge(result) {
  return h(
    "span",
    { class: `badge ${result.mastered ? "ok" : "bad"}` },
    `${result.correct}/${result.total} · ${Math.round(result.ratio * 100)}%`,
  );
}

export const byId = (rows) => new Map(rows.map((r) => [r.id, r]));

export function downloadCsv(filename, rows) {
  const escape = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const text = "﻿" + rows.map((r) => r.map(escape).join(";")).join("\r\n");
  const link = h("a", { href: URL.createObjectURL(new Blob([text], { type: "text/csv" })), download: filename });
  document.body.append(link);
  link.click();
  link.remove();
}

// --- API -----------------------------------------------------------------------

// Сессия живёт в httpOnly-cookie, которую ставит сервер при входе: JavaScript её не видит,
// поэтому украсть токен через внедрённый скрипт нельзя. Заголовок X-Requested-With
// сервер требует для изменяющих запросов — чужой сайт выставить его не может.
let onUnauthorized = () => {};

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

export async function api(path, { method = "GET", body, form, multipart } = {}) {
  const headers = { "X-Requested-With": "fetch" };
  let payload;
  if (multipart) payload = multipart;
  else if (form) payload = new URLSearchParams(form);
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const response = await fetch(path, { method, headers, body: payload, credentials: "same-origin" });
  if (response.status === 401 && !path.startsWith("/auth/")) {
    onUnauthorized();
    throw new Error("сессия истекла, войдите снова");
  }
  const data = response.status === 204 ? null : await response.json();
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(
      Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || response.statusText,
    );
  }
  return data;
}

// --- навигация ----------------------------------------------------------------

// Экран — асинхронная функция, которая рисует себя через render(). Меню задаёт main.js;
// экраны переходят друг к другу через go() и ничего не знают о меню.
let menu = [];

export function setMenu(items) {
  menu = items;
}

export function go(view) {
  fill(nav, menu.map(([title, v]) =>
    h("button", { class: `link ${v === view ? "active" : ""}`, onclick: () => go(v) }, title)));
  return view();
}

// Страница с вкладками; открытая вкладка запоминается до следующего захода.
export function tabbedPage(title, tabs, initial = Object.keys(tabs)[0]) {
  let current = initial;
  return async function page() {
    const bar = h("div", { class: "subnav" });
    const body = h("div");
    async function open(name) {
      current = name;
      fill(bar, Object.keys(tabs).map((n) =>
        h("button", { class: `link ${n === name ? "active" : ""}`, onclick: () => open(n) }, n)));
      fill(body, await tabs[name]());
    }
    render(h("h1", {}, title), bar, body);
    await open(current);
  };
}
