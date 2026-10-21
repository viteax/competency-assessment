// Кабинет студента: назначенные тесты, прохождение, результаты.

import { api, errorBox, go, h } from "./core.js";
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
                h("td", {}, done
                  ? [`Верно ${a.attempt.score} из ${a.attempt.max_score} `, h("span", { class: "badge ok" }, "пройден")]
                  : h("span", { class: "muted" }, a.attempt ? "начат" : "не пройден")),
                h("td", { class: "actions" }, done
                  ? h("button", { class: "link", onclick: () => go(studentResults) }, "Результаты")
                  : h("button", { class: "primary", onclick: () => go((render) => takeTest(a.id, render), studentTests) }, a.attempt ? "Продолжить" : "Пройти")),
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
          const labor = await api("/me/reports/labor-functions").catch(() => []);
          render(
            h("h1", {}, attempt.title),
            h("div", { class: "card" },
              h("p", { class: "muted m-0" }, "Тест сдан"),
              h("div", { class: "score" }, `Верно ${result.score} из ${result.max_score}`),
              h("h2", {}, "Вывод по компетенциям"),
              verdictView(result.competencies),
            ),
            laborSummary(labor),
            h("button", { class: "primary", onclick: () => go(studentResults) }, "Мои результаты"),
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

// Поле ответа для вопроса; возвращает [элементы, read], read() – ответ для API или null.
function questionInput(q) {
  if (q.kind === "open") {
    const input = h("input", { type: "text", maxlength: 500, autocomplete: "off", "aria-label": "Ответ" });
    return [
      [h("p", { class: "hint" }, "Впишите ответ – слово или словосочетание; регистр не важен."), input],
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
  // matching
  const selects = q.options.map((left) => {
    const select = h("select", { "aria-label": `Пара для «${left.text}»` },
      h("option", { value: "" }, "– выберите –"),
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

// Уровень компетенции: до 40% – «требует внимания», 40–79% – «в процессе формирования»,
// от 80% – «хорошо развита».
const LEVELS = {
  attention: ["bad", "требует внимания", "Стоит повторить материал по этой компетенции."],
  forming: ["warn", "в процессе формирования", "Основа есть, но часть заданий вызвала затруднения."],
  good: ["ok", "хорошо развита", "Вы уверенно справляетесь с заданиями по этой компетенции."],
};

const percent = (c) => Math.round(c.ratio * 100);

function verdictView(competencies) {
  if (!competencies.length) return h("p", { class: "muted" }, "Пока нет пройденных тестов");
  return h("div", { class: "verdict" },
    competencies.map((c) => {
      const [tone, label, advice] = LEVELS[c.level];
      return h("div", { class: "verdict-item" },
        h("div", { class: "what" },
          h("strong", {}, c.code), c.name ? ` – ${c.name}` : "",
          h("div", { class: "muted small" }, `Верно ${c.correct} из ${c.total} (${percent(c)}%). ${advice}`),
        ),
        h("span", { class: `badge ${tone}` }, label),
      );
    }),
  );
}

// Трудовые функции профстандарта, которые студент может выполнять: все их компетенции
// сформированы.
function laborSummary(labor) {
  const covered = labor.flatMap((g) => g.functions.filter((f) => f.covered).map((f) => ({ ...f, standard: g.standard_code })));
  return h("div", { class: "card" },
    h("h2", {}, "Трудовые функции, которые вы можете выполнять"),
    covered.length
      ? h("ul", {}, covered.map((f) => h("li", {}, h("strong", {}, f.code), ` ${f.name} `,
          h("span", { class: "muted small" }, `(профстандарт ${f.standard})`))))
      : h("p", { class: "muted mb-0" },
          labor.length
            ? "Пока ни одна трудовая функция не подтверждена полностью: для этого нужны сформированными все её компетенции."
            : "Профстандарты не загружены."),
  );
}

export async function studentResults(render) {
  const [report, labor, profile] = await Promise.all([
    api("/me/reports/competencies"),
    api("/me/reports/labor-functions"),
    api("/me/reports/profile"),
  ]);
  const correct = report.competencies.reduce((sum, c) => sum + c.correct, 0);
  const total = report.competencies.reduce((sum, c) => sum + c.total, 0);
  render(
    h("h1", {}, "Мои результаты"),
    h("div", { class: "card" },
      total ? h("div", { class: "score" }, `Верно ${correct} из ${total}`) : null,
      total ? h("p", { class: "muted mt-0" }, "по всем пройденным тестам") : null,
      h("h2", {}, "Вывод по компетенциям"),
      verdictView(report.competencies),
    ),
    report.competencies.length ? laborSummary(labor) : null,
    report.competencies.length ? profileCharts(profile, "мои результаты") : null,
    report.competencies.length
      ? h("details", { class: "card" },
          h("summary", {}, "Подробно: трудовые функции профстандарта и нужные для них компетенции"),
          h("div", { class: "mt-m" }, laborFunctionsView(labor)))
      : null,
  );
}
