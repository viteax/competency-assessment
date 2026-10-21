// Журнал изменяющих действий: кто, когда и что сделал.

import { api, fill, h } from "../core.js";

const PAGE = 100;

const RESOURCES = {
  competencies: "компетенция", curriculum: "строка учебного плана", directions: "направление",
  disciplines: "дисциплина", "general-functions": "ОТФ", groups: "группа", indicators: "индикатор",
  "labor-functions": "трудовая функция", questions: "вопрос", standards: "профстандарт",
  students: "студент", tests: "тест", users: "учётная запись",
};
const SPECIAL = [
  [/^POST \/users\/\d+\/reset-password$/, "Сброс пароля"],
  [/^POST \/import\/apply$/, "Импорт компетенций"],
  [/^POST \/import\/students\/apply$/, "Импорт студентов"],
  [/^POST \/me\/password$/, "Смена своего пароля"],
  [/^POST \/auth\/register$/, "Регистрация студента"],
  [/^PUT \/settings$/, "Изменение настроек"],
  [/^POST \/assignments$/, "Назначение теста группе"],
  [/^DELETE \/assignments\/\d+$/, "Отмена назначения теста"],
];
const VERBS = { POST: "Создание", PUT: "Изменение", DELETE: "Удаление" };

// «POST /questions» → «Создание: вопрос»; неизвестное действие показывается как есть.
function describe(method, path) {
  const key = `${method} ${path}`;
  const special = SPECIAL.find(([re]) => re.test(key));
  if (special) return special[1];
  const resource = RESOURCES[path.split("/")[1]];
  return resource && VERBS[method] ? `${VERBS[method]}: ${resource}` : key;
}

export async function adminAudit(render) {
  const rows = h("tbody");
  const more = h("button", { type: "button" }, "Показать ещё");
  let offset = 0;

  async function load() {
    const entries = await api(`/audit?limit=${PAGE}&offset=${offset}`);
    offset += entries.length;
    rows.append(...entries.map((e) =>
      h("tr", { class: e.status_code >= 400 ? "muted" : "" },
        h("td", {}, new Date(e.created_at).toLocaleString("ru-RU")),
        h("td", {}, e.username),
        h("td", {}, describe(e.method, e.path), h("div", { class: "muted small" }, `${e.method} ${e.path}`)),
        h("td", {}, e.status_code < 400
          ? h("span", { class: "badge ok" }, "успешно")
          : h("span", { class: "badge bad", title: `код ответа ${e.status_code}` }, `ошибка ${e.status_code}`)),
        h("td", {}, e.ip),
      )));
    more.hidden = entries.length < PAGE;
  }
  more.addEventListener("click", load);

  render(
    h("h1", {}, "Журнал действий"),
    h("p", { class: "muted" }, "Все изменения данных: создание, правка, удаление, импорт, сброс паролей. Ответы с ошибкой показаны серым."),
    h("div", { class: "card table-wrap" },
      h("table", {},
        h("thead", {}, h("tr", {}, ["Когда", "Кто", "Действие", "Результат", "IP"].map((t) => h("th", {}, t)))),
        rows,
      ),
      h("div", { class: "mt-m" }, more),
    ),
  );
  fill(rows);
  await load();
}
