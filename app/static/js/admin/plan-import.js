// Загрузка учебного плана из «Планов» (.plx.xlsx): направление, компетенции, дисциплины с
// семестрами и статусом, профстандарты, ОТФ, ТФ и их связи с компетенциями. Сначала
// предпросмотр, потом тот же файл отправляется на сохранение.

import { api, byCode, errorBox, fill, go, h } from "../core.js";
import { kindBadge, rememberDirection } from "./directions.js";

const STATUS = {
  new: ["новая", "ok"],
  update: ["изменится", "warn"],
  same: ["без изменений", ""],
};

const statusBadge = (status, newLabel = STATUS.new[0]) => {
  const [label, cls] = STATUS[status];
  return h("span", { class: `badge ${cls}` }, status === "new" ? newLabel : label);
};
const chips = (codes) => h("div", { class: "chips" }, [...codes].sort(byCode).map((c) => h("span", { class: "chip" }, c)));
const range = (d) => (d.first_semester === null ? "–" : d.first_semester === d.last_semester ? `${d.first_semester}` : `${d.first_semester}–${d.last_semester}`);
const count = (items, status) => items.filter((i) => i.status === status).length;

function summary(p) {
  const kinds = { regular: 0, elective: 0, optional: 0, practice: 0 };
  p.disciplines.forEach((d) => (kinds[d.kind] += 1));
  const functions = p.standards.flatMap((s) => s.general_functions.flatMap((g) => g.functions));
  return h("ul", {},
    h("li", {}, `Компетенций: ${p.competencies.length} (новых ${count(p.competencies, "new")}, с другой формулировкой ${count(p.competencies, "update")})`),
    h("li", {}, `Дисциплин: ${p.disciplines.length} (новых ${count(p.disciplines, "new")}, изменится ${count(p.disciplines, "update")}): `,
      `обязательных ${kinds.regular}, по выбору ${kinds.elective}, факультативов ${kinds.optional}, практик ${kinds.practice}`),
    h("li", {}, `Профстандартов: ${p.standards.length} (новых ${p.standards.filter((s) => !s.exists).length}), `,
      `ТФ: ${functions.length} (новых ${count(functions, "new")}, с новыми связями ${count(functions, "update")})`),
    p.skipped.length ? h("li", { class: "muted" }, `Не загружается: ${p.skipped.join(", ")} – по ГИА тесты не проводятся`) : null,
  );
}

function competencyTable(items) {
  return h("table", {},
    h("tr", {}, ["Код", "Статус", "Формулировка"].map((t) => h("th", {}, t))),
    items.map((c) => h("tr", {},
      h("td", {}, h("strong", {}, c.code)),
      h("td", {}, statusBadge(c.status)),
      h("td", { class: "wrap main" }, c.description || h("span", { class: "error" }, "нет формулировки – компетенция не загрузится"),
        c.status === "update" ? h("div", { class: "muted small" }, `Сейчас в базе: ${c.existing_description}`) : null),
    )));
}

function disciplineTable(items) {
  return h("table", {},
    h("tr", {}, ["Индекс", "Дисциплина", "Семестры", "Компетенции", "Статус"].map((t) => h("th", {}, t))),
    items.map((d) => h("tr", {},
      h("td", { class: "muted small" }, d.code),
      h("td", { class: "wrap main" }, d.name, " ", kindBadge(d.kind)),
      h("td", {}, range(d)),
      h("td", { class: "wrap" }, chips(d.competency_codes)),
      h("td", { class: "wrap" }, statusBadge(d.status), d.changes.length ? h("div", { class: "muted small" }, d.changes.join("; ")) : null),
    )));
}

function standardList(standards) {
  return h("ul", { class: "plan-tree" }, standards.map((s) =>
    h("li", {}, h("strong", {}, `${s.code} ${s.name}`), " ", s.exists ? null : statusBadge("new", "новый"),
      h("ul", {}, s.general_functions.map((g) =>
        h("li", {}, `ОТФ ${g.code} (уровень ${g.level}). ${g.name} `, g.exists ? null : statusBadge("new"),
          h("ul", {}, g.functions.map((f) =>
            h("li", {}, h("strong", {}, f.code), ` ${f.name} `, statusBadge(f.status), chips(f.competency_codes)))),
        ))),
    )));
}

function resultCard(result) {
  const open = (tab) => async () => {
    rememberDirection(result.direction_id);
    const { catalogsPage } = await import("./pages.js"); // pages.js подключает этот модуль сам
    go(catalogsPage.at(tab), catalogsPage);
  };
  return h("div", { class: "card" },
    h("h2", {}, "Учебный план загружен"),
    h("ul", {},
      result.created_direction ? h("li", {}, "Направление создано") : null,
      h("li", {}, `Компетенций: новых ${result.created_competencies}, обновлено формулировок ${result.updated_competencies}`),
      h("li", {}, `Дисциплин: новых ${result.created_disciplines}, изменено ${result.updated_disciplines}`),
      h("li", {}, `Профстандартов новых: ${result.created_standards}, ОТФ: ${result.created_general_functions}, ТФ: ${result.created_labor_functions}`),
      h("li", {}, `Новых связей ТФ ⇒ компетенции: ${result.linked_labor_functions}`),
    ),
    h("p", { class: "muted" }, "Дальше: добавьте группы направления с годом набора («Группы») и закрепите дисциплины за преподавателями («Учебный план»)."),
    h("div", { class: "row" },
      h("button", { onclick: open("Дисциплины") }, "Открыть дисциплины"),
      h("button", { onclick: open("Учебный план") }, "Открыть учебный план"),
      h("button", { onclick: open("ТФ ⇒ компетенции") }, "Открыть ТФ ⇒ компетенции"),
    ),
  );
}

export function planImportView() {
  const err = errorBox();
  const file = h("input", { type: "file", accept: ".xlsx", required: true, "aria-label": "Файл учебного плана" });
  const previewSlot = h("div");

  const formWith = (extra = {}) => {
    const form = new FormData();
    form.append("file", file.files[0]);
    Object.entries(extra).forEach(([k, v]) => form.append(k, v));
    return form;
  };

  function showPreview(p) {
    const applyErr = errorBox();
    const overwrite = h("input", { type: "checkbox" });
    const d = p.direction;
    fill(previewSlot, h("div", { class: "card" },
      h("h2", {}, `«${p.filename}»: учебный план ${d.code} ${d.name}`),
      h("p", { class: "muted" },
        [d.profile ? `Профиль: ${d.profile}. ` : "", d.year ? `Год начала подготовки: ${d.year}. ` : ""].join(""),
        d.id ? "Направление уже есть – план дополнит его справочники." : "Направления еще нет – оно будет создано."),
      summary(p),
      p.warnings.map((w) => h("p", { class: "error" }, w)),
      h("details", { class: "mt-s" }, h("summary", {}, `Компетенции (${p.competencies.length})`), h("div", { class: "table-wrap mt-s" }, competencyTable(p.competencies))),
      h("details", { class: "mt-s" }, h("summary", {}, `Дисциплины (${p.disciplines.length})`), h("div", { class: "table-wrap mt-s" }, disciplineTable(p.disciplines))),
      p.standards.length ? h("details", { class: "mt-s" }, h("summary", {}, `Профстандарты, ОТФ и ТФ (${p.standards.length})`), standardList(p.standards)) : null,
      count(p.competencies, "update")
        ? h("label", { class: "inline" }, overwrite, "Заменить формулировки компетенций, которые отличаются от плана")
        : null,
      h("div", { class: "row mt-l" },
        h("button", {
          class: "primary",
          onclick: async (event) => {
            applyErr.clear();
            event.target.disabled = true;
            try {
              const result = await api("/import/plan/apply", { method: "POST", multipart: formWith({ overwrite_descriptions: overwrite.checked }) });
              fill(previewSlot, resultCard(result));
            } catch (e) {
              applyErr.show(e);
              event.target.disabled = false;
            }
          },
        }, "Загрузить учебный план"),
      ),
      applyErr.el,
    ));
  }

  async function upload(event) {
    event.preventDefault();
    err.clear();
    fill(previewSlot);
    if (!file.files.length) return;
    try {
      showPreview(await api("/import/plan/preview", { method: "POST", multipart: formWith() }));
    } catch (e) {
      err.show(e);
    }
  }

  return [
    h("form", { class: "card", onsubmit: upload },
      h("p", { class: "muted mt-0" },
        "Загрузите учебный план – Excel-выгрузку из программы «Планы» (файл вида 09.03.01_2023_….plx.xlsx). ",
        "Из листов «Титул», «План» и «Компетенции» берутся направление, компетенции, дисциплины с семестрами ",
        "и статусом (по выбору, факультатив, практика), с листа профстандартов – ОТФ, ТФ и нужные для них компетенции. ",
        "Перед сохранением можно проверить, что будет загружено; ничего не удаляется, повторная загрузка ничего не меняет."),
      file,
      h("div", { class: "mt-m" }, h("button", { class: "primary" }, "Разобрать файл")),
      err.el,
    ),
    previewSlot,
  ];
}
