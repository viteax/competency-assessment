// Кабинет студента: назначенные тесты, прохождение, результаты.

import { api, errorBox, go, h, masteryBadge } from "./core.js";
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
              h("button", { class: "primary", onclick: () => go(studentResults) }, "Мои результаты"),
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

export async function studentResults(render) {
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
