// Справочники направления: компетенции, дисциплины, учебный план и связи ТФ ⇒ компетенции
// у каждого направления свои. Выбранное направление общее для вкладок справочников и банка
// вопросов и запоминается в браузере.

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

function remember(direction) {
  try {
    localStorage.setItem(KEY, String(direction.id));
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
      remember(chosen);
      onChange(chosen);
    },
  }, directions.map((d) => h("option", { value: d.id }, directionLabel(d))));
  select.value = String(current.id);
  return h("div", { class: "direction-bar" }, h("label", {}, "Направление"), select);
}

// Вкладка справочника направления: сверху выбор направления, ниже tab(direction).
export function directionTab(tab) {
  return async () => {
    const directions = await api("/directions");
    if (!directions.length) {
      return h("p", { class: "muted" }, "Сначала добавьте направление подготовки на вкладке «Направления»: компетенции, дисциплины и учебный план у каждого направления свои.");
    }
    let current = currentDirection(directions);
    const slot = h("div");
    const draw = async () => fill(slot, await tab(current));
    const picker = directionPicker(directions, current, async (chosen) => {
      current = chosen;
      await draw();
    });
    await draw();
    return h("div", {}, picker, slot);
  };
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
