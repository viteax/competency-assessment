// База: универсальная таблица с формой и описания всех разделов базы.

import { api, byId, errorBox, fill, h, passwordNotice, temporaryPassword } from "../core.js";

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
      field.required === false ? h("option", { value: "" }, field.empty || "–") : null,
      field.options.map(([v, label]) => h("option", { value: v }, label)),
    );
    if (value !== null && value !== undefined) el.value = String(value);
    return el;
  }
  if (field.type === "quotas") {
    // Поля «сколько вопросов» для компетенций дисциплины; рисует cfg.onForm.
    const el = h("div", { class: "quota-grid" });
    el.initial = new Map((value || []).map((q) => [q.competency_id, q.questions]));
    return el;
  }
  if (field.type === "checkboxes") {
    // Пустой список без пояснения выглядит как ошибка: говорим, откуда взять варианты.
    if (!field.options.length) return h("div", { class: "muted small" }, field.empty || "Выбрать пока не из чего.");
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
    max: field.max,
    placeholder: field.placeholder,
  });
}

function readField(field, el) {
  if (field.type === "quotas") {
    return [...el.querySelectorAll("input[data-competency]")]
      .filter((input) => Number(input.value) > 0)
      .map((input) => ({ competency_id: Number(input.dataset.competency), questions: Number(input.value) }));
  }
  if (field.type === "checkboxes") {
    return [...el.querySelectorAll("input:checked")].map((box) => Number(box.value));
  }
  if (field.type === "select") {
    if (el.value === "") return null;
    return field.raw ? el.value : Number(el.value);
  }
  if (field.type === "number") return el.value === "" ? null : Number(el.value);
  return el.value.trim();
}

// Таблица записей с формой добавления/редактирования и удалением.
// Классы колонок таблицы по содержимому: самая «текстовая» колонка забирает свободное место
// (main), длинные переносятся (wrap), короткие (коды, числа) – в одну строку.
function columnClasses(cells) {
  const text = (v) => (v instanceof Node ? v.textContent : String(v ?? "")).length;
  const count = cells[0]?.length ?? 0;
  const avg = Array.from({ length: count }, (_, i) => cells.reduce((sum, row) => sum + text(row[i]), 0) / (cells.length || 1));
  const main = avg.indexOf(Math.max(...avg));
  return avg.map((a, i) => (i === main && a > 12 ? "wrap main" : a > 24 ? "wrap" : ""));
}

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
    cfg.onForm?.(Object.fromEntries(inputs.map(([f, el]) => [f.name, el])));
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
        h("h2", {}, row ? "Изменить" : "Добавить"),
        inputs.map(([f, el]) => [h("label", {}, f.label), el]),
        h("div", { class: "row mt-l" },
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
    const classes = columnClasses(rows.map((row) => cfg.columns.map(([, cell]) => cell(row))));
    fill(tableSlot,
      rows.length
        ? h("table", {},
            h("tr", {}, cfg.columns.map(([title]) => h("th", {}, title)), h("th", {}, "")),
            rows.map((row) =>
              h("tr", {},
                cfg.columns.map(([, cell], i) => h("td", { class: classes[i] }, cell(row))),
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
      h("div", { class: "mt-m" }, tableSlot),
    ),
    formSlot,
  );
}

const codes = (ids, map) => ids.map((id) => map.get(id)?.code).filter(Boolean).sort().join(", ") || "–";

export const CATALOGS = {
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
      hint: "По году набора система сама считает текущий семестр группы – от него зависит, какие дисциплины попадут в тест на остаточные знания.",
      columns: [
        ["Группа", (r) => r.name],
        ["Направление", (r) => { const d = dirs.get(r.direction_id); return d ? `${d.code} ${d.name}` : "–"; }],
        ["Год набора", (r) => r.start_year ?? "–"],
        ["Семестр сейчас", (r) => r.current_semester ?? "–"],
      ],
      fields: [
        { name: "name", label: "Название" },
        { name: "direction_id", label: "Направление", type: "select", options: directions.map((d) => [d.id, `${d.code} ${d.name}`]) },
        { name: "start_year", label: "Год набора (необязательно)", type: "number", min: 2000, max: 2100, required: false, placeholder: "например, 2024" },
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

  async "Дисциплины"() {
    const competencies = await api("/competencies");
    const comps = byId(competencies);
    return crudSection({
      load: () => api("/disciplines"),
      label: (r) => r.name,
      columns: [["Дисциплина", (r) => r.name], ["Компетенции", (r) => codes(r.competency_ids, comps)]],
      fields: [
        { name: "name", label: "Название" },
        {
          name: "competency_ids", label: "Компетенции", type: "checkboxes", options: competencies.map((c) => [c.id, c.code]),
          empty: "Компетенций пока нет: загрузите их на вкладке «Загрузка из ОПОП / РПД» или добавьте на вкладке «Компетенции». Дисциплину можно сохранить и без них, а компетенции отметить позже.",
        },
      ],
      toForm: (r) => r,
      create: (d) => api("/disciplines", { method: "POST", body: d }),
      update: (r, d) => api(`/disciplines/${r.id}`, { method: "PUT", body: d }),
      remove: (r) => api(`/disciplines/${r.id}`, { method: "DELETE" }),
    });
  },

  async "Преподаватели"() {
    const notice = h("div");
    const err = errorBox();
    const list = h("div", { class: "table-wrap" });
    const fullName = h("input", { type: "text", required: true, "aria-label": "ФИО преподавателя" });
    const username = h("input", { type: "text", required: true, minlength: 3, pattern: "[A-Za-z0-9._\\-]+", title: "латиница, цифры, точка, дефис", "aria-label": "Логин преподавателя" });

    async function draw() {
      const [users, curriculum, disciplines] = await Promise.all([api("/users"), api("/curriculum"), api("/disciplines")]);
      const discs = byId(disciplines);
      const teachers = users.filter((u) => u.role === "teacher");
      const assigned = (t) => curriculum.filter((e) => e.teacher_id === t.id).map((e) => discs.get(e.discipline_id)?.name).join(", ");
      fill(list, teachers.length
        ? h("table", {},
            h("tr", {}, ["ФИО", "Логин", "Дисциплины", ""].map((x) => h("th", {}, x))),
            teachers.map((t) => h("tr", {},
              h("td", {}, t.full_name || "–", t.must_change_password ? [" ", h("span", { class: "badge warn" }, "временный пароль")] : null),
              h("td", {}, t.username),
              h("td", { class: "wrap" }, assigned(t) || h("span", { class: "muted" }, "не закреплены")),
              h("td", { class: "actions" },
                h("button", {
                  class: "link",
                  onclick: async () => {
                    err.clear();
                    try {
                      const reset = await api(`/users/${t.id}/reset-password`, { method: "POST" });
                      fill(notice, passwordNotice(t.full_name || t.username, reset.username, reset.password));
                      await draw();
                    } catch (e) {
                      err.show(e);
                    }
                  },
                }, "Сбросить пароль"),
                h("button", {
                  class: "link danger",
                  onclick: async () => {
                    if (!confirm(`Удалить учётную запись «${t.full_name || t.username}»? Закреплённые дисциплины освободятся.`)) return;
                    err.clear();
                    try {
                      await api(`/users/${t.id}`, { method: "DELETE" });
                      await draw();
                    } catch (e) {
                      err.show(e);
                    }
                  },
                }, "Удалить"),
              ),
            )))
        : h("p", { class: "muted" }, "Преподавателей пока нет"));
    }
    await draw();
    return h("div", {},
      h("p", { class: "muted" }, "Преподаватели (ППС и сотрудники кафедры) входят под своим логином и составляют тестовые вопросы по закреплённым за ними дисциплинам. Дисциплины закрепляются в «Учебном плане»."),
      h("div", { class: "card" }, notice, err.el, list),
      h("form", {
        class: "card",
        onsubmit: async (event) => {
          event.preventDefault();
          err.clear();
          const password = temporaryPassword();
          try {
            await api("/users", { method: "POST", body: { username: username.value, password, role: "teacher", full_name: fullName.value.trim() } });
            fill(notice, passwordNotice(fullName.value.trim(), username.value, password));
            fullName.value = username.value = "";
            await draw();
          } catch (e) {
            err.show(e);
          }
        },
      },
        h("h2", {}, "Добавить преподавателя"),
        h("label", {}, "ФИО"), fullName,
        h("label", {}, "Логин"), username,
        h("div", { class: "mt-l" }, h("button", { class: "primary" }, "Добавить")),
      ),
    );
  },

  async "Учебный план"() {
    const [directions, disciplines, competencies, users] = await Promise.all([
      api("/directions"), api("/disciplines"), api("/competencies"), api("/users"),
    ]);
    const dirs = byId(directions);
    const discs = byId(disciplines);
    const comps = byId(competencies);
    const teachers = users.filter((u) => u.role === "teacher");
    const teacherNames = new Map(teachers.map((t) => [t.id, t.full_name || t.username]));
    const semesters = (r) => (r.first_semester === r.last_semester ? `${r.first_semester}` : `${r.first_semester}–${r.last_semester}`);
    return crudSection({
      hint: "В каких семестрах изучается дисциплина. В тест на остаточные знания попадают только дисциплины, завершённые до текущего семестра группы: во 2-м семестре нельзя проверять математику, которая идёт в 1–2 семестрах.",
      load: () => api("/curriculum"),
      label: (r) => discs.get(r.discipline_id)?.name || "запись",
      columns: [
        ["Направление", (r) => dirs.get(r.direction_id)?.code || "–"],
        ["Дисциплина", (r) => discs.get(r.discipline_id)?.name || "–"],
        ["Семестры", semesters],
        ["Преподаватель", (r) => teacherNames.get(r.teacher_id) || "–"],
        ["Вопросов по компетенциям", (r) => r.quotas
          .map((q) => [comps.get(q.competency_id)?.code || "?", q.questions])
          .sort(([a], [b]) => a.localeCompare(b, "ru"))
          .map(([code, n]) => `${code}: ${n}`).join(", ") || "–"],
      ],
      fields: [
        { name: "direction_id", label: "Направление", type: "select", options: directions.map((d) => [d.id, `${d.code} ${d.name}`]) },
        { name: "discipline_id", label: "Дисциплина", type: "select", options: disciplines.map((d) => [d.id, d.name]) },
        { name: "first_semester", label: "Первый семестр", type: "number", min: 1, max: 12 },
        { name: "last_semester", label: "Последний семестр", type: "number", min: 1, max: 12 },
        { name: "teacher_id", label: "Преподаватель – разрабатывает тестовые вопросы", type: "select", required: false, empty: "– не закреплена –", options: teachers.map((t) => [t.id, t.full_name || t.username]) },
        { name: "quotas", label: "Сколько тестовых вопросов разработать по каждой компетенции", type: "quotas" },
      ],
      onForm(inputs) {
        const box = inputs.quotas;
        function draw() {
          const d = discs.get(Number(inputs.discipline_id.value));
          const current = new Map([...box.querySelectorAll("input[data-competency]")].map((i) => [Number(i.dataset.competency), i.value]));
          fill(box, !d?.competency_ids.length
            ? h("p", { class: "muted small" }, "У дисциплины нет компетенций – укажите их в «Дисциплинах».")
            : d.competency_ids.map((id) => {
                const c = comps.get(id);
                const value = current.get(id) ?? box.initial.get(id) ?? "";
                return h("label", { class: "quota-row" },
                  h("span", {}, h("strong", {}, c.code), ` – ${c.description}`),
                  h("input", { type: "number", min: 0, max: 200, value, "data-competency": id, "aria-label": `Вопросов по ${c.code}`, placeholder: "0" }));
              }));
        }
        inputs.discipline_id.addEventListener("change", draw);
        draw();
      },
      toForm: (r) => r,
      create: (d) => api("/curriculum", { method: "POST", body: d }),
      update: (r, d) => api(`/curriculum/${r.id}`, { method: "PUT", body: d }),
      remove: (r) => api(`/curriculum/${r.id}`, { method: "DELETE" }),
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
        ["ОТФ", (r) => r.general_functions.map((g) => g.code).join(", ") || "–"],
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
        ["Профстандарт", (r) => stds.get(r.standard_id)?.code || "–"],
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
        ["ОТФ", (r) => { const g = gens.get(r.general_function_id); return g ? `${g.standard.code} · ${g.code}` : "–"; }],
        ["Код", (r) => r.code],
        ["Название", (r) => r.name],
        ["Компетенции", (r) => codes(r.competency_ids, comps)],
      ],
      fields: [
        { name: "general_function_id", label: "ОТФ", type: "select", options: generals.map((g) => [g.id, `${g.standard.code} · ОТФ ${g.code}. ${g.name}`]) },
        { name: "code", label: "Код, например A/01.3" },
        { name: "name", label: "Название", type: "textarea" },
        { name: "competency_ids", label: "Нужные компетенции", type: "checkboxes", options: competencies.map((c) => [c.id, c.code]), empty: "Компетенций пока нет: загрузите их на вкладке «Загрузка из ОПОП / РПД» или добавьте на вкладке «Компетенции»." },
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
