// Главная администратора: общая картина, что требует внимания и быстрые действия.

import { api, go, h } from "../core.js";
import { peoplePage, prepPage, testsPage } from "./pages.js";
import { adminQuestions } from "./questions.js";
import { adminGroupResults } from "./results.js";

// Куда ведут ссылки из «Требует внимания» (target из GET /reports/dashboard).
const TARGETS = {
  curriculum: ["Открыть учебный план", () => go(prepPage.at("Учебный план и преподаватели"), prepPage)],
  groups: ["Открыть группы", () => go(peoplePage.at("Группы"), peoplePage)],
  students: ["Открыть студентов", () => go(peoplePage.at("Студенты"), peoplePage)],
  bank: ["Открыть банк вопросов", () => go(adminQuestions)],
  labor_functions: ["Открыть ТФ ⇒ компетенции", () => go(prepPage.at("ТФ ⇒ компетенции"), prepPage)],
  tests: ["Собрать тест", () => go(testsPage.at("Новый тест"), testsPage)],
};

const plural = (n, one, few, many) => {
  const mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
};

function tile(value, label, sub) {
  return h("div", { class: "tile" },
    h("div", { class: "tile-value" }, value),
    h("div", { class: "tile-label" }, label),
    sub ? h("div", { class: "muted small" }, sub) : null);
}

function bar(done, total) {
  const share = total ? Math.min(done / total, 1) : 0;
  const fillEl = h("div", { class: `bar-fill ${share >= 1 ? "full" : ""}` });
  // Через CSSOM, а не атрибутом style: CSP запрещает inline-стили.
  fillEl.style.width = `${Math.round(share * 100)}%`;
  return h("div", { class: "bar", role: "img", "aria-label": `${done} из ${total}` }, fillEl);
}

function attentionCard(items) {
  return h("div", { class: "card" },
    h("h2", {}, "Требует внимания"),
    items.length
      ? h("ul", { class: "attention" }, items.map((item) => {
          const [label, open] = TARGETS[item.target];
          return h("li", {}, h("span", {}, item.text), h("button", { class: "link", onclick: open }, `${label} →`));
        }))
      : h("p", { class: "muted mb-0" }, "Всё в порядке: база заполнена, преподаватели закреплены."));
}

function assignmentsCard(assignments) {
  return h("div", { class: "card" },
    h("h2", {}, "Последние тесты"),
    assignments.length
      ? h("div", { class: "table-wrap" }, h("table", {},
          h("tr", {}, ["Тест", "Группа", "Сдали"].map((t) => h("th", {}, t))),
          assignments.map((a) => h("tr", {},
            h("td", { class: "wrap main" },
              h("button", { class: "link bare text-left", title: "Открыть результаты", onclick: () => go(adminGroupResults) }, a.test),
              h("div", { class: "muted small" }, `назначен ${new Date(a.assigned_at).toLocaleDateString("ru-RU")}`)),
            h("td", {}, a.group),
            h("td", {}, `${a.finished} из ${a.students}`, bar(a.finished, a.students))))))
      : h("p", { class: "muted mb-0" }, "Тестов пока нет."),
    h("div", { class: "mt-m" },
      h("button", { class: "link bare", onclick: () => go(testsPage.at("Все тесты"), testsPage) }, "Все тесты →")));
}

function teachersCard(teachers) {
  const left = teachers.reduce((sum, t) => sum + Math.max(t.required - t.done, 0), 0);
  return h("div", { class: "card" },
    h("h2", {}, "Вопросы от преподавателей"),
    teachers.length
      ? [
          h("p", { class: "muted mt-0" }, left
            ? `Осталось разработать ${left} ${plural(left, "вопрос", "вопроса", "вопросов")}.`
            : "Все вопросы по квотам разработаны."),
          h("div", { class: "table-wrap" }, h("table", {},
            h("tr", {}, ["Дисциплина", "Преподаватель", "Сделано"].map((t) => h("th", {}, t))),
            teachers.map((t) => h("tr", {},
              h("td", { class: "wrap main" }, t.discipline),
              h("td", { class: "wrap" }, t.teacher),
              h("td", {}, t.required ? `${t.done} из ${t.required}` : h("span", { class: "muted" }, "квота не задана"), t.required ? bar(t.done, t.required) : null))))),
        ]
      : h("p", { class: "muted mb-0" }, "Дисциплины ещё не закреплены за преподавателями – это делается в «Подготовка → Учебный план и преподаватели»."));
}

export async function adminHome(render) {
  const d = await api("/reports/dashboard");
  const c = d.counts;
  const quotaDone = d.teachers.reduce((sum, t) => sum + t.done, 0);
  const quotaAll = d.teachers.reduce((sum, t) => sum + t.required, 0);
  render(
    h("h1", {}, "Главная"),
    h("div", { class: "row mb-s" },
      h("button", { class: "primary", onclick: () => go(testsPage.at("Новый тест"), testsPage) }, "Собрать и назначить тест"),
      h("button", { onclick: () => go(adminGroupResults) }, "Результаты"),
      h("button", { onclick: () => go(adminQuestions) }, "Банк вопросов"),
      h("button", { onclick: () => go(peoplePage.at("Загрузить список"), peoplePage) }, "Загрузить студентов"),
    ),
    h("div", { class: "tiles" },
      tile(c.students, plural(c.students, "студент", "студента", "студентов"),
        `в ${c.groups} ${plural(c.groups, "группе", "группах", "группах")}, с учётной записью – ${c.students_with_account}`),
      tile(c.tests, plural(c.tests, "тест", "теста", "тестов"),
        d.assignments.length ? `последний – «${d.assignments[0].test}»` : "пока ни одного"),
      tile(c.questions, plural(c.questions, "вопрос в банке", "вопроса в банке", "вопросов в банке"),
        quotaAll ? `по квотам преподавателей – ${quotaDone} из ${quotaAll}` : null),
      tile(c.teachers, plural(c.teachers, "преподаватель", "преподавателя", "преподавателей"), null),
    ),
    attentionCard(d.attention),
    h("div", { class: "home-grid" }, assignmentsCard(d.assignments), teachersCard(d.teachers)),
  );
}
