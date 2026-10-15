// Кабинет студента: назначенные тесты, прохождение, результаты.

import { api, errorBox, go, h, masteryBadge } from "./core.js";
import { profileCharts } from "./radar.js";
import { laborFunctionsView } from "./reports.js";

export async function studentTests(render) {
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
                h("td", {}, done ? "" : h("button", { class: "primary", onclick: () => go((render) => takeTest(a.id, render), studentTests) }, a.attempt ? "Продолжить" : "Пройти")),
              );
            }),
          ),
        )
      : h("p", { class: "muted" }, "Назначенных тестов нет"),
  );
}

async function takeTest(assignmentId, render) {
  const err = errorBox();
  let attempt;
  try {
    attempt = await api("/me/attempts", { method: "POST", body: { assignment_id: assignmentId } });
  } catch (e) {
    render(err.el);
    return err.show(e);
  }
  const readers = new Map(); // id вопроса → функция, возвращающая ответ или null
  const form = h(
    "form",
    {
      class: "card",
      onsubmit: async (event) => {
        event.preventDefault();
        err.clear();
        const answers = attempt.questions.map((q) => readers.get(q.id)()).filter(Boolean);
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
              h("button", { class: "primary", onclick: () => go(studentResults) }, "Мои результаты"),
            ),
          );
        } catch (e) {
          err.show(e);
        }
      },
    },
    attempt.questions.map((q, i) => {
      const [body, read] = questionInput(q);
      readers.set(q.id, read);
      return h("div", { class: "question" }, h("p", {}, `${i + 1}. ${q.text}`), body);
    }),
    h("button", { class: "primary" }, "Сдать тест"),
    err.el,
  );
  render(h("h1", {}, attempt.title), form);
}

// Поле ответа для вопроса; возвращает [элементы, read], read() — ответ для API или null.
function questionInput(q) {
  if (q.kind === "open") {
    const input = h("input", { type: "text", maxlength: 500, autocomplete: "off", "aria-label": "Ответ" });
    return [
      [h("p", { class: "hint" }, "Впишите ответ — слово или словосочетание; регистр не важен."), input],
      () => (input.value.trim() ? { question_id: q.id, text: input.value.trim() } : null),
    ];
  }
  if (q.kind === "sequence") {
    const list = h("ol", { class: "seq-list" });
    const move = (li, up) => (up ? li.previousElementSibling?.before(li) : li.nextElementSibling?.after(li));
    q.options.forEach((o) => {
      const li = h("li", {}, h("span", {}, o.text),
        h("button", { type: "button", class: "link", title: "Выше", "aria-label": `Поднять: ${o.text}`, onclick: () => move(li, true) }, "↑"),
        h("button", { type: "button", class: "link", title: "Ниже", "aria-label": `Опустить: ${o.text}`, onclick: () => move(li, false) }, "↓"));
      li.dataset.id = o.id;
      list.append(li);
    });
    return [
      [h("p", { class: "hint" }, "Расставьте элементы в правильном порядке кнопками ↑ ↓."), list],
      () => ({ question_id: q.id, order: [...list.children].map((li) => Number(li.dataset.id)) }),
    ];
  }
  if (q.kind === "matching") {
    const selects = q.options.map((left) => {
      const select = h("select", { "aria-label": `Пара для «${left.text}»` },
        h("option", { value: "" }, "— выберите —"),
        q.right.map((r, i) => h("option", { value: r.id }, `${i + 1}. ${r.text}`)));
      select.dataset.left = left.id;
      return [left, select];
    });
    return [
      [
        h("p", { class: "hint" }, "Для каждого элемента выберите пару из списка. Каждый вариант используется не больше одного раза, некоторые могут остаться лишними."),
        h("div", { class: "match-grid" }, selects.map(([left, select]) => [h("div", {}, left.text), select])),
      ],
      () => {
        const pairs = Object.fromEntries(selects.filter(([, s]) => s.value).map(([left, s]) => [left.id, Number(s.value)]));
        return Object.keys(pairs).length === selects.length ? { question_id: q.id, pairs } : null;
      },
    ];
  }
  const name = `q${q.id}`;
  return [
    q.options.map((o) => h("label", {}, h("input", { type: "radio", name, value: o.id }), o.text)),
    () => {
      const checked = document.querySelector(`input[name="${name}"]:checked`);
      return checked ? { question_id: q.id, option_id: Number(checked.value) } : null;
    },
  ];
}

export async function studentResults(render) {
  const [report, labor, profile] = await Promise.all([
    api("/me/reports/competencies"),
    api("/me/reports/labor-functions"),
    api("/me/reports/profile"),
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
    report.competencies.length ? profileCharts(profile, "мои результаты") : null,
    h("h2", {}, "Трудовые функции профстандарта"),
    laborFunctionsView(labor),
  );
}
