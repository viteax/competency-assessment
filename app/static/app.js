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
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : String(child));
  }
  return el;
}

function render(...nodes) {
  app.replaceChildren(...nodes.flat().filter(Boolean));
}

async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) payload = new URLSearchParams(form);
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
  nav.replaceChildren(
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
  nav.replaceChildren();
  who.replaceChildren();
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
  who.replaceChildren(
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
    list.replaceChildren(
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
    table.replaceChildren(
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
      out.replaceChildren(h("p", { class: "muted" }, "Группа ещё не проходила тесты"));
      return;
    }
    out.replaceChildren(
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
    out.replaceChildren(...[laborFunctionsView(report)].flat());
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
