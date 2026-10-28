// Кабинет студента: назначенные тесты, прохождение, результаты.

import { api, errorBox, go, h, onLeave, screenAt, setAddress } from "./core.js";
import { profileCharts } from "./radar.js";
import { laborFunctionsView } from "./reports.js";

export async function studentTests(render) {
  const assignments = await api("/me/assignments");
  render(
    h("h1", {}, "Мои тесты"),
    assignments.length
      ? h("div", { class: "card table-wrap" },
          h("table", {},
            h("tr", {}, h("th", {}, "Тест"), h("th", {}, "Результат"), h("th", {}, "")),
            assignments.map((a) => {
              const done = a.attempt?.finished_at;
              return h("tr", {},
                h("td", { class: "wrap-text" }, a.title, h("div", { class: "muted small" }, `вопросов: ${a.question_count}`)),
                h("td", { class: "wrap-text" }, done
                  ? [`Верно ${a.attempt.score} из ${a.attempt.max_score} `, h("span", { class: "badge ok" }, "пройден")]
                  : h("span", { class: "muted" }, a.attempt ? "начат" : "не пройден")),
                h("td", { class: "actions" }, done
                  ? h("button", { class: "link", onclick: () => go(studentResults) }, "Результаты")
                  : h("button", { class: "primary", onclick: () => go(testScreen(a.id)) }, a.attempt ? "Продолжить" : "Пройти")),
              );
            }),
          ),
        )
      : h("p", { class: "muted" }, "Назначенных тестов нет"),
  );
}

// Прохождение теста по назначению (номер может прийти из адреса строкой).
export const testScreen = (assignmentId) =>
  screenAt(`test/${assignmentId}`, (render) => takeTest(Number(assignmentId), render), studentTests);

// Черновик ответов сохраняется на сервере через секунду после изменения, а также сразу при
// уходе с экрана или со страницы: обновление страницы, переход по меню или вход с другого
// компьютера ответы не стирают. flushDraft – сохранить несохранённое сейчас; lastSave –
// последнее сохранение: открывая тест, дожидаемся его, чтобы получить свежий черновик.
const DRAFT_DELAY = 1000;
let flushDraft = () => {};
let lastSave = Promise.resolve();
window.addEventListener("pagehide", () => flushDraft());

async function takeTest(assignmentId, render) {
  const err = errorBox();
  let attempt;
  try {
    await lastSave;
    attempt = await api("/me/attempts", { method: "POST", body: { assignment_id: assignmentId } });
  } catch (e) {
    render(err.el);
    return err.show(e);
  }
  const status = h("p", { class: "muted small" }, "Ответы сохраняются автоматически – тест можно закрыть и продолжить позже.");
  let timer = null;
  function saveDraft(keepalive = false) {
    clearTimeout(timer);
    timer = null;
    const answers = attempt.questions.map((q) => inputs.get(q.id).draft()).filter(Boolean);
    lastSave = api(`/me/attempts/${attempt.attempt_id}/draft`, { method: "PUT", body: { answers }, keepalive })
      .then(() => {
        status.textContent = `Ответы сохранены в ${new Date().toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" })}.`;
      })
      .catch((e) => {
        status.textContent = `Не удалось сохранить ответы (${e.message}). Попробуем снова при следующем изменении.`;
      });
  }
  const changed = () => {
    clearTimeout(timer);
    timer = setTimeout(saveDraft, DRAFT_DELAY);
  };
  flushDraft = () => {
    if (timer) saveDraft(true);
  };
  onLeave(() => flushDraft());

  const inputs = new Map(); // id вопроса → поле ответа (questionInput)
  const saved = new Map(attempt.draft.map((a) => [a.question_id, a]));
  const submit = h("button", { class: "primary" }, "Сдать тест");
  const form = h(
    "form",
    {
      class: "card",
      oninput: changed,
      onchange: changed,
      onsubmit: async (event) => {
        event.preventDefault();
        err.clear();
        const answers = attempt.questions.map((q) => inputs.get(q.id).read()).filter(Boolean);
        const missing = attempt.questions.length - answers.length;
        if (missing && !confirm(`Без ответа: ${missing}. Они будут засчитаны как неверные. Сдать?`)) return;
        clearTimeout(timer);
        timer = null;
        submit.disabled = true;
        try {
          const result = await api(`/me/attempts/${attempt.attempt_id}/submit`, {
            method: "POST",
            body: { answers },
          });
          flushDraft = () => {};
          // Сданный тест повторно не открыть: обновление страницы покажет список тестов.
          setAddress(studentTests.path, true);
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
          submit.disabled = false;
          err.show(e);
        }
      },
    },
    attempt.questions.map((q, i) => {
      const input = questionInput(q, changed);
      if (saved.has(q.id)) input.restore(saved.get(q.id));
      inputs.set(q.id, input);
      return h("div", { class: "question" }, h("p", {}, `${i + 1}. ${q.text}`), input.body);
    }),
    submit,
    status,
    err.el,
  );
  render(h("h1", {}, attempt.title), form);
}

// Поле ответа для вопроса:
// - body – элементы;
// - read() – ответ для сдачи или null, если ответа нет или он неполный;
// - draft() – ответ для черновика, в том числе неполный, или null;
// - restore(answer) – показать ответ из черновика.
// changed() вызывается при изменении, которого не видно по событиям input и change.
function questionInput(q, changed) {
  if (q.kind === "open") {
    const input = h("input", { type: "text", maxlength: 500, autocomplete: "off", "aria-label": "Ответ" });
    const read = () => (input.value.trim() ? { question_id: q.id, text: input.value.trim() } : null);
    return {
      body: [h("p", { class: "hint" }, "Впишите ответ – слово или словосочетание; регистр не важен."), input],
      read,
      draft: read,
      restore: (a) => { input.value = a.text ?? ""; },
    };
  }
  if (q.kind === "sequence") {
    const list = h("ol", { class: "seq-list" });
    const move = (li, up) => {
      if (up) li.previousElementSibling?.before(li);
      else li.nextElementSibling?.after(li);
      changed();
    };
    q.options.forEach((o) => {
      const li = h("li", {}, h("span", {}, o.text),
        h("button", { type: "button", class: "link", title: "Выше", "aria-label": `Поднять: ${o.text}`, onclick: () => move(li, true) }, "↑"),
        h("button", { type: "button", class: "link", title: "Ниже", "aria-label": `Опустить: ${o.text}`, onclick: () => move(li, false) }, "↓"));
      li.dataset.id = o.id;
      list.append(li);
    });
    const read = () => ({ question_id: q.id, order: [...list.children].map((li) => Number(li.dataset.id)) });
    return {
      body: [h("p", { class: "hint" }, "Расставьте элементы в правильном порядке кнопками ↑ ↓."), list],
      read,
      draft: read,
      restore: (a) => {
        const items = new Map([...list.children].map((li) => [Number(li.dataset.id), li]));
        // Элементы, которых нет в черновике (вопрос успели изменить), остаются в конце.
        for (const id of a.order ?? []) if (items.has(id)) list.append(items.get(id));
        for (const [id, li] of items) if (!a.order?.includes(id)) list.append(li);
      },
    };
  }
  // matching
  const selects = q.options.map((left) => {
    const select = h("select", { "aria-label": `Пара для «${left.text}»` },
      h("option", { value: "" }, "– выберите –"),
      q.right.map((r, i) => h("option", { value: r.id }, `${i + 1}. ${r.text}`)));
    return [left, select];
  });
  const pairs = () => Object.fromEntries(selects.filter(([, s]) => s.value).map(([left, s]) => [left.id, Number(s.value)]));
  return {
    body: [
      h("p", { class: "hint" }, "Для каждого элемента выберите пару из списка. Каждый вариант используется не больше одного раза, некоторые могут остаться лишними."),
      h("div", { class: "match-grid" }, selects.map(([left, select]) => [h("div", {}, left.text), select])),
    ],
    read: () => {
      const chosen = pairs();
      return Object.keys(chosen).length === selects.length ? { question_id: q.id, pairs: chosen } : null;
    },
    draft: () => {
      const chosen = pairs();
      return Object.keys(chosen).length ? { question_id: q.id, pairs: chosen } : null;
    },
    restore: (a) => {
      for (const [left, select] of selects) {
        const right = a.pairs?.[left.id];
        // Пары, которой уже нет среди вариантов, не выбираем.
        if (right !== undefined && q.right.some((r) => r.id === right)) select.value = String(right);
      }
    },
  };
}

// Уровень компетенции приходит с сервера (level_of): по умолчанию до 40% – «требует внимания»,
// 40–79% – «в процессе формирования», от 80% – «хорошо развита»; границы сдвигаются вместе с
// порогом «сформирована».
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
