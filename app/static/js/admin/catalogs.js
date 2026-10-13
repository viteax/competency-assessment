// Справочники: универсальная таблица с формой и описания всех справочников.

import { api, byId, errorBox, fill, h, tabbedPage } from "../core.js";

// Поле формы → элемент ввода. Значение читается через readField.
function fieldInput(field, value) {
  if (field.type === "textarea") {
    const el = h("textarea", { rows: 3, required: field.required !== false });
    el.value = value ?? "";
    return el;
  }
  if (field.type === "select") {
    const el = h(
      "select",
      { required: field.required !== false },
      field.required === false ? h("option", { value: "" }, field.empty || "—") : null,
      field.options.map(([v, label]) => h("option", { value: v }, label)),
    );
    if (value !== null && value !== undefined) el.value = String(value);
    return el;
  }
  if (field.type === "checkboxes") {
    const selected = new Set(value || []);
    return h(
      "div",
      { class: "check-list check-grid" },
      field.options.map(([v, label]) =>
        h("label", {}, h("input", { type: "checkbox", value: v, checked: selected.has(v) }), label),
      ),
    );
  }
  return h("input", {
    type: field.type || "text",
    value: value ?? "",
    required: field.required !== false,
    min: field.min,
  });
}

function readField(field, el) {
  if (field.type === "checkboxes") {
    return [...el.querySelectorAll("input:checked")].map((box) => Number(box.value));
  }
  if (field.type === "select") {
    if (el.value === "") return null;
    return field.raw ? el.value : Number(el.value);
  }
  if (field.type === "number") return Number(el.value);
  return el.value.trim();
}

// Таблица записей с формой добавления/редактирования и удалением.
async function crudSection(cfg) {
  const err = errorBox();
  const formSlot = h("div");
  const tableSlot = h("div", { class: "table-wrap" });

  function closeForm() {
    fill(formSlot);
  }

  function openForm(row) {
    err.clear();
    const values = row ? cfg.toForm(row) : {};
    const inputs = cfg.fields.map((f) => [f, fieldInput(f, values[f.name])]);
    const formErr = errorBox();
    fill(formSlot,
      h(
        "form",
        {
          class: "card edit-form",
          onsubmit: async (event) => {
            event.preventDefault();
            const data = Object.fromEntries(inputs.map(([f, el]) => [f.name, readField(f, el)]));
            try {
              if (row) await cfg.update(row, data);
              else await cfg.create(data);
              closeForm();
              await refresh();
            } catch (e) {
              formErr.show(e);
            }
          },
        },
        h("h2", { style: "margin-top:0" }, row ? "Изменить" : "Добавить"),
        inputs.map(([f, el]) => [h("label", {}, f.label), el]),
        h("div", { class: "row", style: "margin-top:16px" },
          h("button", { class: "primary" }, "Сохранить"),
          h("button", { type: "button", onclick: closeForm }, "Отмена"),
        ),
        formErr.el,
      ),
    );
    formSlot.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function refresh() {
    const rows = await cfg.load();
    fill(tableSlot,
      rows.length
        ? h("table", {},
            h("tr", {}, cfg.columns.map(([title]) => h("th", {}, title)), h("th", {}, "")),
            rows.map((row) =>
              h("tr", {},
                cfg.columns.map(([, cell]) => h("td", { class: "wrap" }, cell(row))),
                h("td", { class: "actions" },
                  h("button", { class: "link", onclick: () => openForm(row) }, "Изменить"),
                  h("button", {
                    class: "link danger",
                    onclick: async () => {
                      if (!confirm(`Удалить «${cfg.label(row)}»?`)) return;
                      err.clear();
                      try {
                        await cfg.remove(row);
                        closeForm();
                        await refresh();
                      } catch (e) {
                        err.show(e);
                      }
                    },
                  }, "Удалить"),
                ),
              ),
            ),
          )
        : h("p", { class: "muted" }, "Записей пока нет"),
    );
  }

  await refresh();
  return h("div", {},
    cfg.hint ? h("p", { class: "muted" }, cfg.hint) : null,
    h("div", { class: "card" },
      h("button", { class: "primary", onclick: () => openForm(null) }, "Добавить"),
      err.el,
      h("div", { style: "margin-top:12px" }, tableSlot),
    ),
    formSlot,
  );
}

const codes = (ids, map) => ids.map((id) => map.get(id)?.code).filter(Boolean).sort().join(", ") || "—";
const competencyOptions = (list) => list.map((c) => [c.id, `${c.code} — ${c.description}`]);

const CATALOGS = {
  async "Направления"() {
    return crudSection({
      load: () => api("/directions"),
      label: (r) => `${r.code} ${r.name}`,
      columns: [["Код", (r) => r.code], ["Название", (r) => r.name]],
      fields: [{ name: "code", label: "Код" }, { name: "name", label: "Название" }],
      toForm: (r) => r,
      create: (d) => api("/directions", { method: "POST", body: d }),
      update: (r, d) => api(`/directions/${r.id}`, { method: "PUT", body: d }),
      remove: (r) => api(`/directions/${r.id}`, { method: "DELETE" }),
    });
  },

  async "Группы"() {
    const directions = await api("/directions");
    const dirs = byId(directions);
    return crudSection({
      load: () => api("/groups"),
      label: (r) => r.name,
      columns: [
        ["Группа", (r) => r.name],
        ["Направление", (r) => { const d = dirs.get(r.direction_id); return d ? `${d.code} ${d.name}` : "—"; }],
      ],
      fields: [
        { name: "name", label: "Название" },
        { name: "direction_id", label: "Направление", type: "select", options: directions.map((d) => [d.id, `${d.code} ${d.name}`]) },
      ],
      toForm: (r) => r,
      create: (d) => api("/groups", { method: "POST", body: d }),
      update: (r, d) => api(`/groups/${r.id}`, { method: "PUT", body: d }),
      remove: (r) => api(`/groups/${r.id}`, { method: "DELETE" }),
    });
  },

  async "Компетенции"() {
    return crudSection({
      load: () => api("/competencies"),
      label: (r) => r.code,
      columns: [
        ["Код", (r) => r.code],
        ["Вид", (r) => r.kind],
        ["Формулировка", (r) => r.description],
        ["Индикаторы", (r) => r.indicators.map((i) => i.code).join(", ") || "—"],
      ],
      fields: [
        { name: "code", label: "Код, например ОПК-5" },
        { name: "kind", label: "Вид", type: "select", raw: true, options: ["УК", "ОПК", "ПК"].map((k) => [k, k]) },
        { name: "description", label: "Формулировка", type: "textarea" },
      ],
      toForm: (r) => r,
      create: (d) => api("/competencies", { method: "POST", body: d }),
      update: (r, d) => api(`/competencies/${r.id}`, { method: "PUT", body: d }),
      remove: (r) => api(`/competencies/${r.id}`, { method: "DELETE" }),
    });
  },

  async "Индикаторы"() {
    const competencies = await api("/competencies");
    const comps = byId(competencies);
    return crudSection({
      hint: "Индикаторы достижения компетенций (например, ОПК-5.1). Вопросы распределяются по ним равномерно.",
      load: () => api("/indicators"),
      label: (r) => r.code,
      columns: [
        ["Код", (r) => r.code],
        ["Компетенция", (r) => comps.get(r.competency_id)?.code || "—"],
        ["Формулировка", (r) => r.description],
      ],
      fields: [
        { name: "competency_id", label: "Компетенция", type: "select", options: competencyOptions(competencies) },
        { name: "code", label: "Код" },
        { name: "description", label: "Формулировка", type: "textarea" },
      ],
      toForm: (r) => r,
      create: (d) => api("/indicators", { method: "POST", body: d }),
      // Компетенцию у существующего индикатора не меняем: к нему могут быть привязаны вопросы.
      update: (r, d) => api(`/indicators/${r.id}`, { method: "PUT", body: { code: d.code, description: d.description } }),
      remove: (r) => api(`/indicators/${r.id}`, { method: "DELETE" }),
    });
  },

  async "Дисциплины"() {
    const competencies = await api("/competencies");
    const comps = byId(competencies);
    return crudSection({
      hint: "Какие компетенции формирует дисциплина учебного плана.",
      load: () => api("/disciplines"),
      label: (r) => r.name,
      columns: [["Дисциплина", (r) => r.name], ["Компетенции", (r) => codes(r.competency_ids, comps)]],
      fields: [
        { name: "name", label: "Название" },
        { name: "competency_ids", label: "Компетенции", type: "checkboxes", options: competencies.map((c) => [c.id, c.code]) },
      ],
      toForm: (r) => r,
      create: (d) => api("/disciplines", { method: "POST", body: d }),
      update: (r, d) => api(`/disciplines/${r.id}`, { method: "PUT", body: d }),
      remove: (r) => api(`/disciplines/${r.id}`, { method: "DELETE" }),
    });
  },

  async "Профстандарты"() {
    return crudSection({
      hint: "Удаление профстандарта удаляет и все его ОТФ и ТФ.",
      load: () => api("/standards"),
      label: (r) => `${r.code} ${r.name}`,
      columns: [
        ["Код", (r) => r.code],
        ["Название", (r) => r.name],
        ["ОТФ", (r) => r.general_functions.map((g) => g.code).join(", ") || "—"],
      ],
      fields: [{ name: "code", label: "Код, например 06.001" }, { name: "name", label: "Название" }],
      toForm: (r) => r,
      create: (d) => api("/standards", { method: "POST", body: d }),
      update: (r, d) => api(`/standards/${r.id}`, { method: "PUT", body: d }),
      remove: (r) => api(`/standards/${r.id}`, { method: "DELETE" }),
    });
  },

  async "ОТФ"() {
    const standards = await api("/standards");
    const stds = byId(standards);
    return crudSection({
      hint: "Обобщённые трудовые функции. Удаление ОТФ удаляет и её ТФ.",
      load: () => api("/general-functions"),
      label: (r) => `ОТФ ${r.code}`,
      columns: [
        ["Профстандарт", (r) => stds.get(r.standard_id)?.code || "—"],
        ["Код", (r) => r.code],
        ["Название", (r) => r.name],
        ["Уровень", (r) => r.qualification_level],
      ],
      fields: [
        { name: "standard_id", label: "Профстандарт", type: "select", options: standards.map((s) => [s.id, `${s.code} ${s.name}`]) },
        { name: "code", label: "Код, например A" },
        { name: "name", label: "Название", type: "textarea" },
        { name: "qualification_level", label: "Уровень квалификации", type: "number", min: 1 },
      ],
      toForm: (r) => r,
      create: (d) => api("/general-functions", { method: "POST", body: d }),
      update: (r, d) => api(`/general-functions/${r.id}`, { method: "PUT", body: d }),
      remove: (r) => api(`/general-functions/${r.id}`, { method: "DELETE" }),
    });
  },

  async "ТФ ⇒ компетенции"() {
    const [standards, competencies] = await Promise.all([api("/standards"), api("/competencies")]);
    const comps = byId(competencies);
    const generals = standards.flatMap((s) => s.general_functions.map((g) => ({ ...g, standard: s })));
    const gens = byId(generals);
    return crudSection({
      hint: "Трудовые функции и компетенции, которые для них нужны. ТФ считается закрытой студентом, если сформированы все отмеченные компетенции.",
      load: () => api("/labor-functions"),
      label: (r) => r.code,
      columns: [
        ["ОТФ", (r) => { const g = gens.get(r.general_function_id); return g ? `${g.standard.code} · ${g.code}` : "—"; }],
        ["Код", (r) => r.code],
        ["Название", (r) => r.name],
        ["Компетенции", (r) => codes(r.competency_ids, comps)],
      ],
      fields: [
        { name: "general_function_id", label: "ОТФ", type: "select", options: generals.map((g) => [g.id, `${g.standard.code} · ОТФ ${g.code}. ${g.name}`]) },
        { name: "code", label: "Код, например A/01.3" },
        { name: "name", label: "Название", type: "textarea" },
        { name: "competency_ids", label: "Нужные компетенции", type: "checkboxes", options: competencies.map((c) => [c.id, c.code]) },
      ],
      toForm: (r) => r,
      create: (d) => api("/labor-functions", { method: "POST", body: d }),
      update: (r, d) => api(`/labor-functions/${r.id}`, { method: "PUT", body: { code: d.code, name: d.name, competency_ids: d.competency_ids } }),
      remove: (r) => api(`/labor-functions/${r.id}`, { method: "DELETE" }),
    });
  },

  async "Настройки"() {
    const current = await api("/settings");
    const err = errorBox();
    const ok = h("div", { class: "success" });
    const percent = h("input", {
      type: "number", min: 1, max: 100, step: 1, required: true,
      value: Math.round(current.mastery_threshold * 100),
    });
    return h("form", {
      class: "card",
      onsubmit: async (event) => {
        event.preventDefault();
        err.clear();
        ok.textContent = "";
        try {
          const saved = await api("/settings", {
            method: "PUT",
            body: { mastery_threshold: Number(percent.value) / 100 },
          });
          ok.textContent = `Сохранено: компетенция сформирована от ${Math.round(saved.mastery_threshold * 100)}% верных ответов`;
        } catch (e) {
          err.show(e);
        }
      },
    },
      h("label", {}, "Компетенция сформирована, если верных ответов не меньше, %"),
      percent,
      h("p", { class: "muted small" }, "Порог действует на все отчёты сразу, включая уже пройденные тесты, и на связь с трудовыми функциями профстандарта."),
      h("button", { class: "primary" }, "Сохранить"),
      err.el,
      ok,
    );
  },
};

export const adminCatalogs = tabbedPage("Справочники", CATALOGS, "Компетенции");
