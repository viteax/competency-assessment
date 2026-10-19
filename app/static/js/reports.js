// Отчёт «ПК → ОТФ», общий для администратора и студента.

import { h } from "./core.js";

export function laborFunctionsView(report) {
  if (!report.length) return h("p", { class: "muted" }, "Профстандарты не загружены");
  return report.map((g) =>
    h("div", { class: "card" },
      h("h2", {},
        `${g.standard_code} · ОТФ ${g.code}. ${g.name} `,
        h("span", { class: `badge ${g.covered ? "ok" : "bad"}` }, g.covered ? "закрыта" : "не закрыта"),
      ),
      h("div", { class: "table-wrap" },
        h("table", {},
          h("tr", {}, h("th", {}, "ТФ"), h("th", {}, "Название"), h("th", {}, "Компетенции"), h("th", {}, "")),
          g.functions.map((f) =>
            h("tr", {},
              h("td", {}, f.code),
              h("td", { class: "wrap-text" }, f.name),
              h("td", {}, f.competency_codes.join(", ")),
              h("td", {}, h("span", { class: `badge ${f.covered ? "ok" : "bad"}` }, f.covered ? "✓" : "✗")),
            ),
          ),
        ),
      ),
    ),
  );
}
