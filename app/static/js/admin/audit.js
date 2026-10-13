// Журнал изменяющих действий: кто, когда и что сделал.

import { api, fill, h } from "../core.js";

const PAGE = 100;

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
        h("td", {}, `${e.method} ${e.path}`),
        h("td", {}, h("span", { class: `badge ${e.status_code < 400 ? "ok" : "bad"}` }, e.status_code)),
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
      h("div", { style: "margin-top:12px" }, more),
    ),
  );
  fill(rows);
  await load();
}
