// Простой клиент без сборки: работает поверх JSON API того же сервера.
"use strict";

const app = document.getElementById("app");
const nav = document.getElementById("nav");
const who = document.getElementById("who");

let token = null;
try { token = localStorage.getItem("token"); } catch { /* приватный режим */ }
let me = null;

// --- утилиты ---------------------------------------------------------------

// Создание DOM без innerHTML, чтобы данные из БД не исполнялись как разметка.
function h(tag, attrs = {}, ...children) {
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
function fill(el, ...nodes) {
  el.replaceChildren(
    ...nodes.flat(Infinity).filter((n) => n !== null && n !== undefined && n !== false),
  );
}

function render(...nodes) {
  fill(app, ...nodes);
}

async function api(path, { method = "GET", body, form, multipart } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (multipart) payload = multipart;
  else if (form) payload = new URLSearchParams(form);
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const response = await fetch(path, { method, headers, body: payload });
  if (response.status === 401 && path !== "/auth/token") {
    logout();
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

function errorBox() {
  const box = h("div", { class: "error", role: "alert" });
  return {
    el: box,
    show(error) { box.textContent = error.message || String(error); },
    clear() { box.textContent = ""; },
  };
}

// Высота textarea по содержимому (элемент уже должен быть в документе).
function autoHeight(el) {
  el.style.height = "auto";
  el.style.height = `${el.scrollHeight + 2}px`;
}

function percent(ratio) {
  return `${Math.round(ratio * 100)}%`;
}

function masteryBadge(result) {
  return h(
    "span",
    { class: `badge ${result.mastered ? "ok" : "bad"}` },
    `${result.correct}/${result.total} · ${percent(result.ratio)}`,
  );
}

function setNav(items, active) {
  fill(nav,
    ...items.map(([title, view]) =>
      h("button", { class: `link ${view === active ? "active" : ""}`, onclick: () => view() }, title),
    ),
  );
}

function logout() {
  token = null;
  me = null;
  try { localStorage.removeItem("token"); } catch { /* ignore */ }
  showLogin();
}

// --- вход ------------------------------------------------------------------

function showLogin() {
  fill(nav);
  fill(who);
  const err = errorBox();
  const username = h("input", { type: "text", autocomplete: "username", required: true });
  const password = h("input", { type: "password", autocomplete: "current-password", required: true });
  render(
    h(
      "form",
      {
        class: "card login",
        onsubmit: async (event) => {
          event.preventDefault();
          err.clear();
          try {
            const data = await api("/auth/token", {
              method: "POST",
              form: { username: username.value, password: password.value },
            });
            token = data.access_token;
            try { localStorage.setItem("token", token); } catch { /* ignore */ }
            await start();
          } catch (e) {
            err.show(e);
          }
        },
      },
      h("h1", {}, "Вход"),
      h("label", {}, "Логин"),
      username,
      h("label", {}, "Пароль"),
      password,
      h("div", { style: "margin-top:16px" }, h("button", { class: "primary" }, "Войти")),
      err.el,
    ),
  );
}

async function start() {
  if (!token) return showLogin();
  try {
    me = await api("/me");
  } catch {
    return logout();
  }
  fill(who,
    `${me.username} (${me.role === "admin" ? "администратор" : "студент"}) `,
    h("button", { class: "link", onclick: logout }, "Выйти"),
  );
  if (me.role === "admin") adminAssign();
  else studentTests();
}

// --- администратор ---------------------------------------------------------

const ADMIN_NAV = () => [
  ["Назначить тест", adminAssign],
  ["Студенты", adminStudents],
  ["Результаты группы", adminGroupResults],
  ["ПК → ОТФ", adminLaborFunctions],
  ["Банк вопросов", adminQuestions],
  ["Справочники", adminCatalogs],
  ["Импорт", adminImport],
];

async function adminAssign() {
  setNav(ADMIN_NAV(), adminAssign);
  const [groups, competencies, disciplines, questions] = await Promise.all([
    api("/groups"),
    api("/competencies"),
    api("/disciplines"),
    api("/questions"),
  ]);
  const err = errorBox();
  const ok = h("div", { class: "success" });

  const title = h("input", { type: "text", value: "Входной контроль", required: true });
  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const discipline = h(
    "select",
    {},
    h("option", { value: "" }, "Все дисциплины"),
    disciplines.map((d) => h("option", { value: d.id }, d.name)),
  );
  const perCompetency = h("input", { type: "number", min: 1, max: 50, value: 5 });
  const checks = new Map();

  // Сколько вопросов есть в банке по компетенции с учётом выбранной дисциплины.
  function available(competencyId) {
    const d = discipline.value ? Number(discipline.value) : null;
    return questions.filter(
      (q) => q.competency_id === competencyId && (d === null || q.discipline_id === d),
    ).length;
  }

  const list = h("div", { class: "check-list" });
  function drawCompetencies() {
    const d = discipline.value ? disciplines.find((x) => x.id === Number(discipline.value)) : null;
    const visible = d ? competencies.filter((c) => d.competency_ids.includes(c.id)) : competencies;
    fill(list,
      ...["УК", "ОПК", "ПК"].map((kind) => {
        const items = visible.filter((c) => c.kind === kind);
        if (!items.length) return null;
        return h(
          "div",
          {},
          h("h2", {}, kind),
          items.map((c) => {
            const box = checks.get(c.id) || h("input", { type: "checkbox", value: c.id });
            checks.set(c.id, box);
            return h(
              "label",
              {},
              box,
              h("strong", {}, c.code),
              ` — ${c.description} `,
              h("span", { class: "muted" }, `(вопросов: ${available(c.id)})`),
            );
          }),
        );
      }),
    );
  }
  discipline.addEventListener("change", drawCompetencies);
  drawCompetencies();

  render(
    h("h1", {}, "Назначить тест группе"),
    h(
      "form",
      {
        class: "card",
        onsubmit: async (event) => {
          event.preventDefault();
          err.clear();
          ok.textContent = "";
          const ids = [...checks.entries()]
            .filter(([, box]) => box.checked && box.isConnected)
            .map(([id]) => id);
          if (!ids.length) return err.show(new Error("выберите хотя бы одну компетенцию"));
          try {
            const test = await api("/tests", {
              method: "POST",
              body: {
                title: title.value,
                discipline_id: discipline.value ? Number(discipline.value) : null,
                competency_ids: ids,
                questions_per_competency: Number(perCompetency.value),
              },
            });
            await api("/assignments", {
              method: "POST",
              body: { test_id: test.id, group_id: Number(group.value) },
            });
            const groupName = group.selectedOptions[0].textContent;
            ok.textContent = `Тест «${test.title}» (${test.question_ids.length} вопр.) назначен группе ${groupName}`;
          } catch (e) {
            err.show(e);
          }
        },
      },
      h("label", {}, "Название теста"),
      title,
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Группа"), group),
        h("div", {}, h("label", {}, "Дисциплина"), discipline),
        h("div", {}, h("label", {}, "Вопросов на компетенцию"), perCompetency),
      ),
      list,
      h("div", { style: "margin-top:16px" }, h("button", { class: "primary" }, "Собрать и назначить")),
      err.el,
      ok,
    ),
  );
}

async function adminStudents() {
  setNav(ADMIN_NAV(), adminStudents);
  const groups = await api("/groups");
  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const table = h("div", { class: "table-wrap" });
  const err = errorBox();
  const ok = h("div", { class: "success" });

  async function drawStudents() {
    const [students, users] = await Promise.all([
      api(`/students?group_id=${group.value}`),
      api("/users"),
    ]);
    const logins = new Map(users.filter((u) => u.student_id).map((u) => [u.student_id, u.username]));
    fill(table,
      students.length
        ? h("table", {},
            h("tr", {}, h("th", {}, "ФИО"), h("th", {}, "Логин")),
            students.map((s) =>
              h("tr", {}, h("td", {}, s.full_name), h("td", {}, logins.get(s.id) || h("span", { class: "muted" }, "нет"))),
            ),
          )
        : h("p", { class: "muted" }, "В группе пока нет студентов"),
    );
  }
  group.addEventListener("change", drawStudents);

  const fullName = h("input", { type: "text", required: true });
  const username = h("input", { type: "text", required: true, minlength: 3 });
  const password = h("input", { type: "text", required: true, minlength: 6 });

  render(
    h("h1", {}, "Студенты"),
    h("div", { class: "card" }, h("label", {}, "Группа"), group, h("h2", {}, "Список"), table),
    h(
      "form",
      {
        class: "card",
        onsubmit: async (event) => {
          event.preventDefault();
          err.clear();
          ok.textContent = "";
          try {
            const student = await api("/students", {
              method: "POST",
              body: { full_name: fullName.value, group_id: Number(group.value) },
            });
            await api("/users", {
              method: "POST",
              body: {
                username: username.value,
                password: password.value,
                role: "student",
                student_id: student.id,
              },
            });
            ok.textContent = `Добавлен ${student.full_name}, логин ${username.value}`;
            fullName.value = username.value = password.value = "";
            await drawStudents();
          } catch (e) {
            err.show(e);
          }
        },
      },
      h("h2", { style: "margin-top:0" }, "Добавить студента в выбранную группу"),
      h("label", {}, "ФИО"),
      fullName,
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Логин"), username),
        h("div", {}, h("label", {}, "Пароль"), password),
      ),
      h("div", { style: "margin-top:16px" }, h("button", { class: "primary" }, "Добавить")),
      err.el,
      ok,
    ),
  );
  if (groups.length) await drawStudents();
}

async function adminGroupResults() {
  setNav(ADMIN_NAV(), adminGroupResults);
  const groups = await api("/groups");
  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const out = h("div", { class: "table-wrap" });

  async function draw() {
    const report = await api(`/reports/groups/${group.value}/competencies`);
    const codes = [...new Set(report.students.flatMap((s) => s.competencies.map((c) => c.code)))].sort();
    if (!codes.length) {
      fill(out, h("p", { class: "muted" }, "Группа ещё не проходила тесты"));
      return;
    }
    fill(out,
      h("table", {},
        h("tr", {}, h("th", {}, "Студент"), codes.map((c) => h("th", {}, c))),
        report.students.map((s) => {
          const byCode = new Map(s.competencies.map((c) => [c.code, c]));
          return h("tr", {},
            h("td", {}, s.full_name),
            codes.map((c) => h("td", {}, byCode.has(c) ? masteryBadge(byCode.get(c)) : h("span", { class: "muted" }, "—"))),
          );
        }),
      ),
    );
  }
  group.addEventListener("change", draw);
  render(
    h("h1", {}, "Результаты группы"),
    h("div", { class: "card" }, h("label", {}, "Группа"), group),
    h("div", { class: "card" }, out),
  );
  if (groups.length) await draw();
}

function laborFunctionsView(report) {
  if (!report.length) return h("p", { class: "muted" }, "Профстандарты не загружены");
  return report.map((g) =>
    h("div", { class: "card" },
      h("h2", { style: "margin-top:0" },
        `${g.standard_code} · ОТФ ${g.code}. ${g.name} `,
        h("span", { class: `badge ${g.covered ? "ok" : "bad"}` }, g.covered ? "закрыта" : "не закрыта"),
      ),
      h("div", { class: "table-wrap" },
        h("table", {},
          h("tr", {}, h("th", {}, "ТФ"), h("th", {}, "Название"), h("th", {}, "Компетенции"), h("th", {}, "")),
          g.functions.map((f) =>
            h("tr", {},
              h("td", {}, f.code),
              h("td", { style: "white-space:normal" }, f.name),
              h("td", {}, f.competency_codes.join(", ")),
              h("td", {}, h("span", { class: `badge ${f.covered ? "ok" : "bad"}` }, f.covered ? "✓" : "✗")),
            ),
          ),
        ),
      ),
    ),
  );
}

async function adminLaborFunctions() {
  setNav(ADMIN_NAV(), adminLaborFunctions);
  const students = await api("/students");
  const student = h("select", {}, students.map((s) => h("option", { value: s.id }, s.full_name)));
  const out = h("div");
  async function draw() {
    const report = await api(`/reports/students/${student.value}/labor-functions`);
    fill(out, laborFunctionsView(report));
  }
  student.addEventListener("change", draw);
  render(
    h("h1", {}, "ПК → ОТФ: трудовые функции студента"),
    h("div", { class: "card" },
      h("label", {}, "Студент"),
      student,
      h("p", { class: "muted" }, "ТФ закрыта, если сформированы все связанные с ней компетенции."),
    ),
    out,
  );
  if (students.length) await draw();
}

// --- справочники -----------------------------------------------------------

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

const byId = (rows) => new Map(rows.map((r) => [r.id, r]));
const codes = (ids, map) => ids.map((id) => map.get(id)?.code).filter(Boolean).join(", ") || "—";
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
};

let currentCatalog = "Компетенции";

async function adminCatalogs() {
  setNav(ADMIN_NAV(), adminCatalogs);
  const tabs = h("div", { class: "subnav" });
  const body = h("div");
  async function open(name) {
    currentCatalog = name;
    fill(tabs,
      ...Object.keys(CATALOGS).map((n) =>
        h("button", { class: `link ${n === name ? "active" : ""}`, onclick: () => open(n) }, n),
      ),
    );
    fill(body, await CATALOGS[name]());
  }
  render(h("h1", {}, "Справочники"), tabs, body);
  await open(currentCatalog);
}

// --- банк вопросов ---------------------------------------------------------

async function adminQuestions() {
  setNav(ADMIN_NAV(), adminQuestions);
  const [competencies, disciplines] = await Promise.all([api("/competencies"), api("/disciplines")]);
  const comps = byId(competencies);
  const discs = byId(disciplines);
  const indicators = byId(competencies.flatMap((c) => c.indicators));

  const filterCompetency = h("select", {}, h("option", { value: "" }, "Все компетенции"),
    competencies.map((c) => h("option", { value: c.id }, c.code)));
  const filterDiscipline = h("select", {}, h("option", { value: "" }, "Все дисциплины"),
    disciplines.map((d) => h("option", { value: d.id }, d.name)));
  const err = errorBox();
  const formSlot = h("div");
  const tableSlot = h("div", { class: "table-wrap" });

  async function refresh() {
    const params = new URLSearchParams();
    if (filterCompetency.value) params.set("competency_id", filterCompetency.value);
    if (filterDiscipline.value) params.set("discipline_id", filterDiscipline.value);
    const questions = await api(`/questions?${params}`);
    fill(tableSlot,
      questions.length
        ? h("table", {},
            h("tr", {}, ["Вопрос", "Компетенция", "Индикатор", "Дисциплина", "Вариантов", ""].map((t) => h("th", {}, t))),
            questions.map((q) =>
              h("tr", {},
                h("td", { class: "wrap" }, q.text, q.in_use ? [" ", h("span", { class: "badge ok" }, "в тестах")] : null),
                h("td", {}, comps.get(q.competency_id)?.code || "—"),
                h("td", {}, indicators.get(q.indicator_id)?.code || "—"),
                h("td", { class: "wrap" }, discs.get(q.discipline_id)?.name || "—"),
                h("td", {}, q.options.length),
                h("td", { class: "actions" },
                  h("button", { class: "link", onclick: () => openForm(q) }, "Изменить"),
                  q.in_use ? null : h("button", {
                    class: "link danger",
                    onclick: async () => {
                      if (!confirm("Удалить вопрос?")) return;
                      err.clear();
                      try {
                        await api(`/questions/${q.id}`, { method: "DELETE" });
                        fill(formSlot);
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
        : h("p", { class: "muted" }, "Вопросов не найдено"),
    );
  }

  function openForm(q) {
    const locked = Boolean(q?.in_use);
    const formErr = errorBox();
    const competency = h("select", { required: true, disabled: locked },
      competencies.map((c) => h("option", { value: c.id }, `${c.code} — ${c.description}`)));
    const indicator = h("select");
    const discipline = h("select", {}, h("option", { value: "" }, "Без дисциплины"),
      disciplines.map((d) => h("option", { value: d.id }, d.name)));
    const text = h("textarea", { rows: 3, required: true });
    const options = h("div", { class: "options" });

    function drawIndicators(selected) {
      const c = comps.get(Number(competency.value));
      fill(indicator,
        h("option", { value: "" }, "Без индикатора"),
        (c?.indicators || []).map((i) => h("option", { value: i.id }, `${i.code} — ${i.description}`)),
      );
      indicator.value = selected ? String(selected) : "";
    }
    competency.addEventListener("change", () => drawIndicators(null));

    const radioName = `correct-${Date.now()}`;
    function optionRow(o = { text: "", is_correct: false }) {
      const row = h("div", { class: "option-row" },
        h("input", { type: "radio", name: radioName, checked: o.is_correct, disabled: locked, title: "Правильный ответ" }),
        h("input", { type: "text", value: o.text, required: true, placeholder: "Вариант ответа" }),
        locked ? null : h("button", { type: "button", class: "link danger", onclick: () => row.remove() }, "✕"),
      );
      row.dataset.id = o.id ?? "";
      return row;
    }

    if (q) {
      competency.value = String(q.competency_id);
      discipline.value = q.discipline_id ? String(q.discipline_id) : "";
      text.value = q.text;
      q.options.forEach((o) => options.append(optionRow(o)));
    } else {
      if (filterCompetency.value) competency.value = filterCompetency.value;
      if (filterDiscipline.value) discipline.value = filterDiscipline.value;
      options.append(optionRow({ text: "", is_correct: true }), optionRow(), optionRow(), optionRow());
    }
    drawIndicators(q?.indicator_id);

    fill(formSlot,
      h("form", {
        class: "card edit-form",
        onsubmit: async (event) => {
          event.preventDefault();
          formErr.clear();
          const rows = [...options.querySelectorAll(".option-row")];
          const body = {
            competency_id: Number(competency.value),
            indicator_id: indicator.value ? Number(indicator.value) : null,
            discipline_id: discipline.value ? Number(discipline.value) : null,
            text: text.value.trim(),
            options: rows.map((r) => ({
              ...(r.dataset.id ? { id: Number(r.dataset.id) } : {}),
              text: r.querySelector("input[type=text]").value.trim(),
              is_correct: r.querySelector("input[type=radio]").checked,
            })),
          };
          if (!body.options.some((o) => o.is_correct)) return formErr.show(new Error("отметьте правильный вариант"));
          try {
            if (q) await api(`/questions/${q.id}`, { method: "PUT", body });
            else await api("/questions", { method: "POST", body });
            fill(formSlot);
            await refresh();
          } catch (e) {
            formErr.show(e);
          }
        },
      },
      h("h2", { style: "margin-top:0" }, q ? "Изменить вопрос" : "Новый вопрос"),
      locked ? h("p", { class: "muted" }, "Вопрос уже входит в собранные тесты, по нему могут быть ответы студентов. Можно править формулировки, индикатор и дисциплину; для остального создайте новый вопрос.") : null,
      h("label", {}, "Компетенция"), competency,
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Индикатор"), indicator),
        h("div", {}, h("label", {}, "Дисциплина"), discipline),
      ),
      h("label", {}, "Текст вопроса"), text,
      h("label", {}, "Варианты ответа (отметьте правильный)"), options,
      locked ? null : h("button", { type: "button", class: "link", onclick: () => options.append(optionRow()) }, "+ вариант"),
      h("div", { class: "row", style: "margin-top:16px" },
        h("button", { class: "primary" }, "Сохранить"),
        h("button", { type: "button", onclick: () => fill(formSlot) }, "Отмена"),
      ),
      formErr.el,
      ),
    );
    formSlot.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  filterCompetency.addEventListener("change", refresh);
  filterDiscipline.addEventListener("change", refresh);
  render(
    h("h1", {}, "Банк вопросов"),
    h("div", { class: "card" },
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Компетенция"), filterCompetency),
        h("div", {}, h("label", {}, "Дисциплина"), filterDiscipline),
        h("button", { class: "primary", onclick: () => openForm(null) }, "Новый вопрос"),
      ),
      err.el,
      h("div", { style: "margin-top:12px" }, tableSlot),
    ),
    formSlot,
  );
  await refresh();
}

// --- импорт компетенций ----------------------------------------------------

const IMPORT_STATUS = {
  new: ["новая", "ok"],
  update: ["есть отличия", "warn"],
  same: ["без изменений", ""],
};

async function adminImport() {
  setNav(ADMIN_NAV(), adminImport);
  const err = errorBox();
  const file = h("input", { type: "file", accept: ".docx,.xlsx,.pdf,.txt", required: true });
  const previewSlot = h("div");

  async function upload(event) {
    event.preventDefault();
    err.clear();
    fill(previewSlot);
    if (!file.files.length) return;
    const form = new FormData();
    form.append("file", file.files[0]);
    try {
      showPreview(await api("/import/preview", { method: "POST", multipart: form }));
    } catch (e) {
      err.show(e);
    }
  }

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
              : h("span", { class: "muted" }, "—"),
          ),
        );
      }),
    );

    fill(previewSlot,
      h("div", { class: "card" },
        h("h2", { style: "margin-top:0" }, `«${p.filename}»: найдено компетенций — ${p.competencies.length}`),
        p.warnings.map((w) => h("p", { class: "error" }, w)),
        p.competencies.length ? [
          h("label", {}, "Дисциплина (компетенции будут к ней привязаны)"),
          discipline,
          p.discipline_name
            ? h("div", { class: "muted small" }, p.discipline_exists ? "Дисциплина уже есть — компетенции добавятся к ней" : "Дисциплина будет создана")
            : null,
          h("label", { class: "inline" }, overwrite, "Перезаписать формулировки существующих компетенций и индикаторов"),
          h("div", { class: "table-wrap", style: "margin-top:12px" }, table),
          h("div", { class: "row", style: "margin-top:16px" },
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
                    h("h2", { style: "margin-top:0" }, "Импорт выполнен"),
                    h("ul", {},
                      h("li", {}, `Новых компетенций: ${result.created_competencies}`),
                      h("li", {}, `Обновлено формулировок компетенций: ${result.updated_competencies}`),
                      h("li", {}, `Новых индикаторов: ${result.created_indicators}`),
                      h("li", {}, `Обновлено формулировок индикаторов: ${result.updated_indicators}`),
                      result.discipline
                        ? h("li", {}, `Дисциплина «${result.discipline.name}»${result.created_discipline ? " создана" : ""}, привязано компетенций: ${result.linked_competencies}`)
                        : null,
                    ),
                    h("button", { onclick: adminCatalogs }, "Открыть справочники"),
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

  render(
    h("h1", {}, "Импорт компетенций из ОПОП / РПД"),
    h("form", { class: "card", onsubmit: upload },
      h("p", { class: "muted", style: "margin-top:0" },
        "Загрузите РПД, матрицу компетенций или другой документ ОПОП (.docx, .xlsx, .pdf, .txt). ",
        "В тексте ищутся коды УК-…, ОПК-…, ПК-… и индикаторы (УК-1.1, ИУК-1.1, ИД-1.УК-1) с формулировками. ",
        "Перед сохранением результат можно проверить и поправить; ничего не удаляется."),
      file,
      h("div", { style: "margin-top:12px" }, h("button", { class: "primary" }, "Разобрать файл")),
      err.el,
    ),
    previewSlot,
  );
}

// --- студент ---------------------------------------------------------------

const STUDENT_NAV = () => [
  ["Мои тесты", studentTests],
  ["Мои результаты", studentResults],
];

async function studentTests() {
  setNav(STUDENT_NAV(), studentTests);
  const assignments = await api("/me/assignments");
  render(
    h("h1", {}, "Мои тесты"),
    assignments.length
      ? h("div", { class: "card table-wrap" },
          h("table", {},
            h("tr", {}, h("th", {}, "Тест"), h("th", {}, "Вопросов"), h("th", {}, "Результат"), h("th", {}, "")),
            assignments.map((a) => {
              const done = a.attempt?.finished_at;
              return h("tr", {},
                h("td", {}, a.title),
                h("td", {}, a.question_count),
                h("td", {}, done ? `${a.attempt.score}/${a.attempt.max_score}` : h("span", { class: "muted" }, "не пройден")),
                h("td", {}, done ? "" : h("button", { class: "primary", onclick: () => takeTest(a.id) }, a.attempt ? "Продолжить" : "Пройти")),
              );
            }),
          ),
        )
      : h("p", { class: "muted" }, "Назначенных тестов нет"),
  );
}

async function takeTest(assignmentId) {
  const err = errorBox();
  let attempt;
  try {
    attempt = await api("/me/attempts", { method: "POST", body: { assignment_id: assignmentId } });
  } catch (e) {
    render(err.el);
    return err.show(e);
  }
  const form = h(
    "form",
    {
      class: "card",
      onsubmit: async (event) => {
        event.preventDefault();
        err.clear();
        const answers = attempt.questions
          .map((q) => ({ question_id: q.id, option: form.querySelector(`input[name="q${q.id}"]:checked`) }))
          .filter((a) => a.option)
          .map((a) => ({ question_id: a.question_id, option_id: Number(a.option.value) }));
        const missing = attempt.questions.length - answers.length;
        if (missing && !confirm(`Без ответа: ${missing}. Они будут засчитаны как неверные. Сдать?`)) return;
        try {
          const result = await api(`/me/attempts/${attempt.attempt_id}/submit`, {
            method: "POST",
            body: { answers },
          });
          render(
            h("h1", {}, attempt.title),
            h("div", { class: "card" },
              h("div", { class: "score" }, `${result.score} / ${result.max_score}`),
              h("p", { class: "muted" }, "Тест сдан"),
              h("button", { class: "primary", onclick: studentResults }, "Мои результаты"),
            ),
          );
        } catch (e) {
          err.show(e);
        }
      },
    },
    attempt.questions.map((q, i) =>
      h("div", { class: "question" },
        h("p", {}, `${i + 1}. ${q.text}`),
        q.options.map((o) => h("label", {}, h("input", { type: "radio", name: `q${q.id}`, value: o.id }), o.text)),
      ),
    ),
    h("button", { class: "primary" }, "Сдать тест"),
    err.el,
  );
  render(h("h1", {}, attempt.title), form);
}

async function studentResults() {
  setNav(STUDENT_NAV(), studentResults);
  const [report, labor] = await Promise.all([
    api("/me/reports/competencies"),
    api("/me/reports/labor-functions"),
  ]);
  render(
    h("h1", {}, "Мои результаты"),
    h("h2", {}, "Компетенции"),
    report.competencies.length
      ? h("div", { class: "card table-wrap" },
          h("table", {},
            h("tr", {}, h("th", {}, "Компетенция"), h("th", {}, "Результат"), h("th", {}, "")),
            report.competencies.map((c) =>
              h("tr", {},
                h("td", {}, c.code),
                h("td", {}, masteryBadge(c)),
                h("td", {}, c.mastered ? "сформирована" : "не сформирована"),
              ),
            ),
          ),
        )
      : h("p", { class: "muted" }, "Пока нет пройденных тестов"),
    h("h2", {}, "Трудовые функции профстандарта"),
    laborFunctionsView(labor),
  );
}

window.addEventListener("unhandledrejection", (event) => {
  const box = errorBox();
  box.show(event.reason);
  app.prepend(box.el);
});

start();
