// Импорт компетенций из ОПОП / РПД и студентов из выгрузки СДО.

import { api, autoHeight, downloadCsv, errorBox, fill, go, h } from "../core.js";

const IMPORT_STATUS = {
  new: ["новая", "ok"],
  update: ["есть отличия", "warn"],
  same: ["без изменений", ""],
};

// Разбор документа ОПОП / РПД из file на месте: компетенции сравниваются с компетенциями
// направления direction, предпросмотр рисуется в previewSlot. Ошибка сервера – исключение.
export async function previewCompetencies(direction, file, previewSlot) {
  function showPreview(p) {
    const applyErr = errorBox();
    const discipline = h("input", { type: "text", value: p.discipline_name || "", placeholder: "не привязывать к дисциплине" });
    const overwrite = h("input", { type: "checkbox" });
    // Для каждой компетенции: галочка «импортировать» и поле формулировки.
    const rows = p.competencies.map((c) => ({
      c,
      include: h("input", { type: "checkbox", checked: c.status !== "same" }),
      description: (() => {
        const el = h("textarea", { rows: 2, placeholder: "формулировка компетенции" });
        el.value = c.description;
        el.addEventListener("input", () => autoHeight(el));
        return el;
      })(),
    }));

    const table = h("table", {},
      h("tr", {}, ["", "Код", "Статус", "Формулировка из файла", "Индикаторы"].map((t) => h("th", {}, t))),
      rows.map(({ c, include, description }) => {
        const [label, cls] = IMPORT_STATUS[c.status];
        return h("tr", {},
          h("td", {}, include),
          h("td", {}, h("strong", {}, c.code)),
          h("td", {}, h("span", { class: `badge ${cls}` }, label)),
          h("td", { class: "wrap import-desc" },
            description,
            c.existing_description && c.existing_description !== c.description
              ? h("div", { class: "muted small" }, `Сейчас в базе: ${c.existing_description}`)
              : null,
          ),
          h("td", { class: "wrap" },
            c.indicators.length
              ? h("ul", { class: "indicators" },
                  c.indicators.map((i) =>
                    h("li", {},
                      h("strong", {}, i.code), " ", i.description || h("span", { class: "muted" }, "без формулировки"), " ",
                      !i.exists ? h("span", { class: "badge ok" }, "новый")
                        : i.changed ? h("span", { class: "badge warn" }, "другая формулировка") : null,
                    ),
                  ),
                )
              : h("span", { class: "muted" }, "–"),
          ),
        );
      }),
    );

    fill(previewSlot,
      h("div", { class: "card" },
        h("h2", {}, `«${p.filename}»: найдено компетенций – ${p.competencies.length}`),
        p.warnings.map((w) => h("p", { class: "error" }, w)),
        p.competencies.length ? [
          h("label", {}, "Дисциплина (компетенции будут к ней привязаны)"),
          discipline,
          p.discipline_name
            ? h("div", { class: "muted small" }, p.discipline_exists ? "Дисциплина уже есть – компетенции добавятся к ней" : "Дисциплина будет создана")
            : null,
          h("label", { class: "inline" }, overwrite, "Перезаписать формулировки существующих компетенций и индикаторов"),
          h("div", { class: "table-wrap mt-m" }, table),
          h("div", { class: "row mt-l" },
            h("button", {
              class: "primary",
              onclick: async () => {
                applyErr.clear();
                const selected = rows.filter((r) => r.include.checked);
                if (!selected.length) return applyErr.show(new Error("не выбрано ни одной компетенции"));
                try {
                  const result = await api("/import/apply", {
                    method: "POST",
                    body: {
                      direction_id: direction.id,
                      discipline_name: discipline.value.trim() || null,
                      overwrite_descriptions: overwrite.checked,
                      competencies: selected.map(({ c, description }) => ({
                        code: c.code,
                        description: description.value.trim(),
                        indicators: c.indicators.map((i) => ({ code: i.code, description: i.description })),
                      })),
                    },
                  });
                  fill(previewSlot, h("div", { class: "card" },
                    h("h2", {}, "Импорт выполнен"),
                    h("ul", {},
                      h("li", {}, `Новых компетенций: ${result.created_competencies}`),
                      h("li", {}, `Обновлено формулировок компетенций: ${result.updated_competencies}`),
                      h("li", {}, `Новых индикаторов: ${result.created_indicators}`),
                      h("li", {}, `Обновлено формулировок индикаторов: ${result.updated_indicators}`),
                      result.discipline
                        ? h("li", {}, `Дисциплина «${result.discipline.name}»${result.created_discipline ? " создана" : ""}, привязано компетенций: ${result.linked_competencies}`)
                        : null,
                    ),
                    h("button", {
                      // pages.js сам подключает этот модуль, поэтому импорт – по требованию.
                      onclick: async () => {
                        const { prepPage } = await import("./pages.js");
                        go(prepPage.at("Компетенции"), prepPage);
                      },
                    }, "Открыть компетенции"),
                  ));
                } catch (e) {
                  applyErr.show(e);
                }
              },
            }, "Импортировать выбранные"),
          ),
          applyErr.el,
        ] : null,
      ),
    );
    rows.forEach(({ description }) => autoHeight(description));
  }

  const form = new FormData();
  form.append("file", file.files[0]);
  form.append("direction_id", direction.id);
  showPreview(await api("/import/preview", { method: "POST", multipart: form }));
}

const STUDENT_FIELDS = [
  ["full_name", "ФИО целиком"],
  ["last_name", "Фамилия"],
  ["first_name", "Имя"],
  ["middle_name", "Отчество"],
  ["group", "Группа"],
  ["program", "Образовательная программа"],
  ["email", "E-mail"],
  ["external_id", "Идентификатор в СДО"],
  ["login", "Логин в СДО"],
  ["role", "Роль"],
];

export async function studentImportView() {
  const [groups, directions] = await Promise.all([api("/groups"), api("/directions")]);
  const err = errorBox();
  const file = h("input", { type: "file", accept: ".csv,.xlsx", required: true });
  const previewSlot = h("div");

  async function runPreview(mapping) {
    err.clear();
    if (!file.files.length) return;
    const form = new FormData();
    form.append("file", file.files[0]);
    if (mapping) form.append("mapping", JSON.stringify(mapping));
    try {
      showPreview(await api("/import/students/preview", { method: "POST", multipart: form }));
    } catch (e) {
      fill(previewSlot);
      err.show(e);
    }
  }

  function showPreview(p) {
    const applyErr = errorBox();
    const columnOptions = [["", "–"], ...p.headers.map((hd, i) => [String(i), `${i + 1}: ${hd || "(без заголовка)"}`])];
    const mappingSelects = STUDENT_FIELDS.map(([field, label]) => {
      const select = h("select", {}, columnOptions.map(([v, t]) => h("option", { value: v }, t)));
      select.value = p.mapping[field] === null || p.mapping[field] === undefined ? "" : String(p.mapping[field]);
      return [field, label, select];
    });

    const defaultGroup = h("select", {}, h("option", { value: "" }, "– не задана –"),
      groups.map((g) => h("option", { value: g.id }, g.name)));
    const direction = h("select", {}, h("option", { value: "" }, "– выберите –"),
      directions.map((d) => h("option", { value: d.id }, d.label)));
    const createAccounts = h("input", { type: "checkbox", checked: true });

    const rows = p.rows.map((r) => ({
      r,
      include: h("input", { type: "checkbox", checked: r.is_student && !r.problems.length, disabled: r.problems.length > 0 }),
    }));
    const STATUS = { new: ["новый", "ok"], update: ["обновится", "warn"], same: ["без изменений", ""] };

    fill(previewSlot,
      h("div", { class: "card" },
        h("h2", {}, `«${p.filename}»: строк – ${p.rows.length}`),
        // Если колонку с ФИО не узнали, сразу показываем сопоставление.
        h("details", { open: p.mapping.full_name === null && p.mapping.last_name === null },
          h("summary", {}, "Сопоставление колонок"),
          h("p", { class: "muted small" }, "Колонки определены по заголовкам. Если что-то не так – выберите нужные и нажмите «Применить»."),
          h("div", { class: "mapping-grid" },
            mappingSelects.map(([, label, select]) => h("div", {}, h("label", {}, label), select)),
          ),
          h("button", {
            type: "button",
            class: "mt-m",
            onclick: () => runPreview(Object.fromEntries(mappingSelects.map(([f, , s]) => [f, s.value === "" ? null : Number(s.value)]))),
          }, "Применить"),
        ),
        h("div", { class: "row mt-s" },
          h("div", {}, h("label", {}, "Группа для строк без группы"), defaultGroup),
          p.missing_groups.length
            ? h("div", {}, h("label", {}, `Учебный план для новых групп: ${p.missing_groups.join(", ")}`), direction)
            : null,
        ),
        h("label", { class: "inline" }, createAccounts, "Создать учётные записи новым студентам (логины и пароли покажу один раз)"),
        h("div", { class: "table-wrap mt-m" },
          h("table", {},
            h("tr", {}, ["", "Стр.", "ФИО", "Группа", "E-mail", "ID в СДО", "Роль", "Статус"].map((t) => h("th", {}, t))),
            rows.map(({ r, include }) => {
              const [label, cls] = STATUS[r.status];
              return h("tr", { class: r.is_student ? "" : "muted" },
                h("td", {}, include),
                h("td", {}, r.row),
                h("td", { class: "wrap" }, r.full_name || "–", r.problems.map((pr) => h("div", { class: "error small m-0" }, pr))),
                h("td", {}, r.existing_group && r.group && r.existing_group !== r.group ? `${r.existing_group} → ${r.group}` : (r.group || r.existing_group || "–")),
                h("td", {}, r.email || "–"),
                h("td", {}, r.external_id || "–"),
                h("td", {}, r.role || "–"),
                h("td", {}, h("span", { class: `badge ${cls}` }, label)),
              );
            }),
          ),
        ),
        h("div", { class: "row mt-l" },
          h("button", {
            class: "primary",
            onclick: async () => {
              applyErr.clear();
              const students = rows.filter((x) => x.include.checked).map(({ r }) => ({
                full_name: r.full_name, email: r.email, external_id: r.external_id, login: r.login, group: r.group, program: r.program,
              }));
              if (!students.length) return applyErr.show(new Error("не выбрано ни одного студента"));
              try {
                const result = await api("/import/students/apply", {
                  method: "POST",
                  body: {
                    students,
                    default_group_id: defaultGroup.value ? Number(defaultGroup.value) : null,
                    direction_id: direction.value ? Number(direction.value) : null,
                    create_accounts: createAccounts.checked,
                  },
                });
                showResult(result);
              } catch (e) {
                applyErr.show(e);
              }
            },
          }, "Импортировать выбранных"),
        ),
        applyErr.el,
      ),
    );
  }

  function showResult(result) {
    const accountRows = result.accounts.map((a) => [a.full_name, a.group, a.username, a.password]);
    fill(previewSlot,
      h("div", { class: "card" },
        h("h2", {}, "Импорт выполнен"),
        h("ul", {},
          h("li", {}, `Новых студентов: ${result.created}`),
          h("li", {}, `Обновлено: ${result.updated}`),
          h("li", {}, `Без изменений: ${result.unchanged}`),
          result.created_groups.length ? h("li", {}, `Созданы группы: ${result.created_groups.join(", ")}`) : null,
        ),
        result.accounts.length
          ? [
              h("p", { class: "error" }, "Пароли показываются только сейчас – скачайте список и передайте студентам."),
              h("button", {
                class: "primary",
                onclick: () => downloadCsv("logins.csv", [["ФИО", "Группа", "Логин", "Пароль"], ...accountRows]),
              }, "Скачать логины и пароли (CSV)"),
              h("div", { class: "table-wrap mt-m" },
                h("table", {},
                  h("tr", {}, ["ФИО", "Группа", "Логин", "Пароль"].map((t) => h("th", {}, t))),
                  accountRows.map((r) => h("tr", {}, r.map((v) => h("td", {}, v)))),
                ),
              ),
            ]
          : null,
      ),
    );
  }

  return [
    h("form", { class: "card", onsubmit: (event) => { event.preventDefault(); runPreview(null); } },
      h("p", { class: "muted mt-0" },
        "Загрузите список студентов в CSV или Excel: выгрузку участников курса или журнала оценок из СДО, ",
        "список из деканата и т.п. Нужны как минимум ФИО и группа; e-mail или идентификатор СДО помогают узнавать ",
        "студентов при повторной загрузке. Ничего не удаляется."),
      file,
      h("div", { class: "mt-m" }, h("button", { class: "primary" }, "Разобрать файл")),
      err.el,
    ),
    previewSlot,
  ];
}
