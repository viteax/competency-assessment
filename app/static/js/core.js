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

// Номер текущего экрана: растёт при каждом переходе (go) и при показе экранов вне меню.
let screen = 0;

// Экран вне меню (вход, смена пароля).
export function render(...nodes) {
  leaving();
  leaving = () => {};
  screen += 1;
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

// Порядок кодов как в ФГОС: УК, ОПК, ПК, номера по числу (ОПК-2 раньше ОПК-10).
// Тот же порядок, что у code_key на сервере.
const CODE_GROUPS = ["УК", "ОПК", "ПК"];
const codeGroup = (code) => {
  const i = CODE_GROUPS.indexOf((code.match(/^\p{L}*/u)[0] || "").toUpperCase());
  return i === -1 ? CODE_GROUPS.length : i;
};
export const byCode = (a, b) =>
  codeGroup(a) - codeGroup(b) || a.localeCompare(b, "ru", { numeric: true });

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
// сервер требует для изменяющих запросов – чужой сайт выставить его не может.
let onUnauthorized = () => {};

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

// keepalive – запрос доживёт до конца, даже если страницу закрывают (не больше 64 КБ).
export async function api(path, { method = "GET", body, form, multipart, keepalive = false } = {}) {
  const headers = { "X-Requested-With": "fetch" };
  let payload;
  if (multipart) payload = multipart;
  else if (form) payload = new URLSearchParams(form);
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const response = await fetch(path, { method, headers, body: payload, credentials: "same-origin", keepalive });
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

// Экран – асинхронная функция, которая рисует себя через переданный ей render. Меню задаёт
// main.js; экраны переходят друг к другу через go() и ничего не знают о меню.
//
// Адрес экрана – в хэше: #/раздел, #/раздел/вкладка, #/раздел/параметр. Поэтому работают
// «Назад», обновление страницы и ссылки на экран. Адрес – свойство path экрана: у пунктов
// меню его задаёт setMenu, у вкладок – tabbedPage, у экранов с параметром – screenAt.
let menu = []; // [название, экран, адрес]
let routes = {}; // адрес → (параметр) => экран, для экранов вне меню

export function setMenu(items, paramRoutes = {}) {
  menu = items;
  routes = paramRoutes;
  for (const [, view, path] of items) view.path = path;
}

// Экран со своим адресом; menuItem – какой пункт меню при нём подсвечен.
export function screenAt(path, view, menuItem) {
  return Object.assign(view, { path, menu: menuItem });
}

// Записывает адрес в историю браузера; replace – заменить текущую запись, а не добавить.
export function setAddress(path, replace = false) {
  if (path === undefined || currentAddress() === path) return;
  history[replace ? "replaceState" : "pushState"](null, "", `#/${path}`);
}

function currentAddress() {
  try {
    return decodeURIComponent(location.hash.slice(2));
  } catch {
    return "";
  }
}

export function clearAddress() {
  history.replaceState(null, "", location.pathname);
}

// Открывает экран по адресу из строки браузера; неизвестный адрес – первый пункт меню.
export function openAddress() {
  const [name, ...rest] = currentAddress().split("/");
  const param = rest.join("/");
  const item = menu.find(([, , path]) => path === name);
  const view = item
    ? (param && item[1].tab?.(param)) || item[1]
    : (param && routes[name]?.(param)) || menu[0][1];
  return go(view, undefined, { replace: true });
}

window.addEventListener("popstate", () => {
  if (menu.length) openAddress();
});

// Что сделать при уходе с текущего экрана (например, сохранить несохранённое).
let leaving = () => {};

export function onLeave(handler) {
  leaving = handler;
}

// menuItem – какой пункт меню подсветить, если экран открыт не из меню.
export function go(view, menuItem = view.menu ?? view, { replace = false } = {}) {
  leaving();
  leaving = () => {};
  setAddress(view.path, replace);
  fill(nav, menu.map(([title, v]) =>
    h("button", { class: `link ${v === menuItem ? "active" : ""}`, onclick: () => go(v) }, title)));
  const current = (screen += 1);
  // Пока экран ждал ответа сервера, пользователь мог уйти на другой – тогда запоздавшая
  // отрисовка не должна закрыть новый экран.
  return view((...nodes) => {
    if (current === screen) fill(app, ...nodes);
  });
}

// Часть адреса для вкладки: «Учебный план» → «учебный-план».
const slug = (name) => name.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "-").replace(/^-|-$/g, "");

// Страница с вкладками; открытая вкладка запоминается до следующего захода.
// page.at(name) – та же страница, открытая на нужной вкладке (для ссылок с других экранов).
export function tabbedPage(title, tabs, initial = Object.keys(tabs)[0]) {
  let current = initial;
  let loads = 0; // номер последней загрузки вкладки: показывается только она
  page.at = (name) =>
    screenAt(page.path && `${page.path}/${slug(name)}`, (render) => {
      current = name;
      return page(render);
    }, page);
  // Вкладка по части адреса; неизвестная – undefined.
  page.tab = (part) => {
    const name = Object.keys(tabs).find((n) => slug(n) === part);
    return name && page.at(name);
  };
  return page;
  async function page(render) {
    const bar = h("div", { class: "subnav" });
    const body = h("div");
    let shown = null; // какая вкладка уже показана на этой странице
    async function open(name, clicked = false) {
      // Клик по уже открытой вкладке ничего не делает: иначе введённое в форму пропало бы.
      if (name === shown && name === current) return;
      current = name;
      if (page.path) setAddress(`${page.path}/${slug(name)}`, !clicked);
      const ticket = ++loads;
      fill(bar, Object.keys(tabs).map((n) =>
        h("button", { class: `link ${n === name ? "active" : ""}`, onclick: () => open(n, true) }, n)));
      const content = await tabs[name]();
      // Пока вкладка загружалась, могли открыть другую или эту же ещё раз (повторный клик,
      // переход по меню): опоздавшая загрузка не должна заменить уже показанную.
      if (ticket === loads) {
        fill(body, content);
        shown = name;
      }
    }
    render(h("h1", {}, title), bar, body);
    await open(current);
  }
}

// Отдельный экран как вкладка страницы: его заголовок h1 не нужен – он есть у страницы.
export function screenTab(screen) {
  return async () => {
    const box = h("div");
    await screen((...nodes) => fill(box, nodes.flat(Infinity).filter((n) => !(n instanceof Element && n.tagName === "H1"))));
    return box;
  };
}

// --- типы заданий ----------------------------------------------------------------

export const QUESTION_KINDS = {
  matching: "На установление соответствия",
  sequence: "На установление последовательности",
  open: "Открытого типа",
};
export const DIFFICULTIES = { basic: "Базовый (1–3 мин)", advanced: "Повышенный (3–5 мин)" };

// --- учётные записи ------------------------------------------------------------

// Временный пароль для новой учётки: без похожих символов, владелец сменит его при входе.
export function temporaryPassword(length = 10) {
  const alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = crypto.getRandomValues(new Uint32Array(length));
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join("");
}

// Плашка с выданным паролем – показывается один раз.
export function passwordNotice(fullName, username, password) {
  return h("div", { class: "notice" },
    h("strong", {}, fullName), ": логин ", h("code", {}, username), ", временный пароль ",
    h("code", {}, password),
    h("div", { class: "muted small" }, "Пароль показывается один раз; при первом входе нужно задать свой."),
  );
}
