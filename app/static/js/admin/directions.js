// Направление кабинета администратора: компетенции, дисциплины, учебный план, группы, банк
// вопросов и тесты у каждого направления свои. Выбранное в шапке направление запоминается
// в браузере.

import { api, fill, h } from "../core.js";

const KEY = "catalog-direction";

export const directionLabel = (d) => `${d.code} ${d.name}`;

export function currentDirection(directions) {
  let saved = null;
  try {
    saved = Number(localStorage.getItem(KEY));
  } catch {
    // хранилище браузера недоступно (приватный режим) – берём первое направление
  }
  return directions.find((d) => d.id === saved) || directions[0] || null;
}

// Запомнить направление (например, только что загруженное из учебного плана).
export function rememberDirection(id) {
  try {
    localStorage.setItem(KEY, String(id));
  } catch {
    // не запомнится – не страшно
  }
}

// «Направление: …» – выбор, если направлений несколько. onChange(direction) после выбора.
export function directionPicker(directions, current, onChange) {
  if (directions.length < 2) {
    return h("p", { class: "direction-bar" }, "Направление: ", h("strong", {}, directionLabel(current)));
  }
  const select = h("select", {
    "aria-label": "Направление",
    onchange: () => {
      const chosen = directions.find((d) => d.id === Number(select.value));
      rememberDirection(chosen.id);
      onChange(chosen);
    },
  }, directions.map((d) => h("option", { value: d.id }, directionLabel(d))));
  select.value = String(current.id);
  return h("div", { class: "direction-bar" }, h("label", {}, "Направление"), select);
}

// Направление выбирается один раз в шапке (панель ниже) и общее для всего кабинета.
let bar = null; // элемент шапки, куда рисуется выбор направления
let onSwitch = () => {};

export const NO_DIRECTION = "Сначала добавьте направление подготовки в «Система → Направления» или загрузите учебный план в «Подготовка → Загрузить документ»: компетенции, дисциплины, группы и тесты привязаны к направлению.";

export async function activeDirection() {
  return currentDirection(await api("/directions"));
}

// Панель выбора в шапке; onChange вызывается после смены направления.
export function mountDirectionBar(slot, onChange) {
  bar = slot;
  onSwitch = onChange;
  return refreshDirectionBar();
}

export function unmountDirectionBar() {
  if (bar) fill(bar);
  bar = null;
}

// Перерисовать панель: направление добавили, удалили или загрузили из учебного плана.
export async function refreshDirectionBar() {
  if (!bar) return;
  const directions = await api("/directions");
  const current = currentDirection(directions);
  fill(bar, current ? directionPicker(directions, current, onSwitch) : null);
}

// Экран направления: screen(render, direction); без направления – подсказка под заголовком.
export function withDirection(title, screen) {
  return async (render) => {
    const direction = await activeDirection();
    if (direction) return screen(render, direction);
    render(h("h1", {}, title), h("p", { class: "muted" }, NO_DIRECTION));
  };
}

// Вкладка направления: tab(direction) для выбранного в шапке направления.
export function directionTab(tab) {
  return async () => {
    const direction = await activeDirection();
    return direction ? tab(direction) : h("p", { class: "muted" }, NO_DIRECTION);
  };
}

// Тесты направления: те, что по его дисциплинам или назначены его группам.
export async function loadTests(direction) {
  const query = `?direction_id=${direction.id}`;
  const [tests, disciplines, groups] = await Promise.all([api("/tests"), api(`/disciplines${query}`), api(`/groups${query}`)]);
  const disciplineIds = new Set(disciplines.map((d) => d.id));
  const groupIds = new Set(groups.map((g) => g.id));
  return tests.filter((t) => t.discipline_ids.some((id) => disciplineIds.has(id)) || t.group_ids.some((id) => groupIds.has(id)));
}

// --- статус дисциплины в учебном плане ------------------------------------------------

export const DISCIPLINE_KINDS = {
  regular: "Обязательная",
  elective: "По выбору (ДВ)",
  optional: "Факультатив (ФТД)",
  practice: "Практика",
};

const KIND_BADGES = { elective: "по выбору", optional: "факультатив", practice: "практика" };

// Пометка у названия дисциплины; у обязательной – ничего.
export const kindBadge = (kind) => (KIND_BADGES[kind] ? h("span", { class: "badge kind" }, KIND_BADGES[kind]) : null);
