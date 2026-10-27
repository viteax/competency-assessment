// Загрузка вопросов из ФОС дисциплины (Word или архив .zip с несколькими документами).
// Сначала разбор и проверка, потом тот же файл отправляется на сохранение.

import { api, DIFFICULTIES, errorBox, fill, h, QUESTION_KINDS } from "../core.js";

const STATUS = {
  new: ["новый", "ok"],
  duplicate: ["уже в банке", ""],
  error: ["не разобран", "bad"],
};

function questionRows(questions) {
  return h("table", {},
    h("tr", {}, ["№", "Компетенция", "Тип", "Задание и ответ", "Статус"].map((t) => h("th", {}, t))),
    questions.map((q) => {
      const [label, cls] = STATUS[q.status];
      return h("tr", {},
        h("td", {}, q.number),
        h("td", {}, q.competency || "–"),
        h("td", { class: "wrap small" }, QUESTION_KINDS[q.kind], h("div", { class: "muted" }, DIFFICULTIES[q.difficulty].split(" ")[0].toLowerCase())),
        h("td", { class: "wrap main" },
          h("div", { class: "pre-line" }, q.text || "–"),
          q.answer.length ? h("ul", { class: "indicators muted small" }, q.answer.map((a) => h("li", {}, a))) : null),
        h("td", { class: "wrap" }, h("span", { class: `badge ${cls}` }, label), q.error ? h("div", { class: "error small" }, q.error) : null),
      );
    }));
}

function documentPreview(d) {
  const count = (status) => d.questions.filter((q) => q.status === status).length;
  return h("div", { class: "mt-l" },
    h("h3", {}, `«${d.filename}»`),
    h("p", { class: "mt-0" },
      h("strong", {}, d.discipline || "дисциплина не указана"),
      d.discipline && !d.error ? (d.discipline_exists ? " – есть в справочниках" : " – будет добавлена в справочники") : "",
      h("span", { class: "muted" }, ` · ${d.direction || "направление не указано"}${d.semester ? ` · ${d.semester} семестр` : ""}`)),
    d.error ? h("p", { class: "error" }, d.error) : null,
    d.competencies.length
      ? h("p", { class: "small" }, "Компетенции: ", d.competencies.map((c, i) => [i ? ", " : "", c.code, c.exists ? "" : " (будет добавлена)"]))
      : null,
    h("p", {}, `Заданий: ${d.questions.length} – новых ${count("new")}, уже в банке ${count("duplicate")}, не разобрано ${count("error")}`),
    d.warnings.map((w) => h("p", { class: "muted small" }, w)),
    d.questions.length
      ? h("details", { class: "mt-s" }, h("summary", {}, "Задания"), h("div", { class: "table-wrap mt-s" }, questionRows(d.questions)))
      : null,
  );
}

// options: directionId (администратор – направление банка), disciplineId (преподаватель –
// его дисциплина), onDone() – после сохранения, onCancel() – закрыть.
export function fundImportCard({ directionId = null, disciplineId = null, onDone, onCancel }) {
  const err = errorBox();
  const file = h("input", { type: "file", accept: ".docx,.zip", required: true, "aria-label": "Файл ФОС" });
  const previewSlot = h("div");

  const formWith = () => {
    const form = new FormData();
    form.append("file", file.files[0]);
    if (disciplineId) form.append("discipline_id", disciplineId);
    else if (directionId) form.append("direction_id", directionId);
    return form;
  };

  function showPreview(p) {
    const applyErr = errorBox();
    const fresh = p.documents.flatMap((d) => d.questions).filter((q) => q.status === "new").length;
    fill(previewSlot,
      p.documents.map(documentPreview),
      h("div", { class: "row mt-l" },
        h("button", {
          class: "primary",
          disabled: !fresh,
          onclick: async (event) => {
            applyErr.clear();
            event.target.disabled = true;
            try {
              const r = await api("/questions/import/apply", { method: "POST", multipart: formWith() });
              fill(previewSlot, h("div", { class: "success" },
                `Добавлено вопросов: ${r.created_questions}. Уже были в банке: ${r.duplicates}. Пропущено (не разобраны): ${r.errors}.`,
                r.created_disciplines ? ` Добавлено дисциплин: ${r.created_disciplines}.` : "",
                r.created_competencies ? ` Добавлено компетенций: ${r.created_competencies}.` : "",
                r.directions.length ? ` Направление: ${r.directions.join(", ")} – выберите его вверху страницы, чтобы увидеть вопросы.` : ""));
              await onDone?.();
            } catch (e) {
              applyErr.show(e);
              event.target.disabled = false;
            }
          },
        }, fresh ? `Загрузить новые вопросы (${fresh})` : "Новых вопросов нет"),
      ),
      applyErr.el,
    );
  }

  return h("form", {
    class: "card edit-form",
    onsubmit: async (event) => {
      event.preventDefault();
      err.clear();
      fill(previewSlot);
      try {
        showPreview(await api("/questions/import/preview", { method: "POST", multipart: formWith() }));
      } catch (e) {
        err.show(e);
      }
    },
  },
    h("h2", {}, "Загрузка вопросов из ФОС"),
    h("p", { class: "muted mt-0" },
      "Фонд оценочных материалов дисциплины в Word (.docx) или архив .zip с несколькими документами. ",
      "Берутся задания на соответствие, последовательность и открытого типа с ответами; уровень сложности – ",
      "из таблицы распределения заданий. ",
      disciplineId ? "Вопросы добавятся в эту дисциплину. " : "Направление и дисциплина – из шапки документа. ",
      "Перед сохранением можно проверить разбор; вопросы, которые уже есть в банке, не повторяются."),
    file,
    h("div", { class: "row mt-m" },
      h("button", { class: "primary" }, "Разобрать файл"),
      h("button", { type: "button", onclick: onCancel }, "Закрыть"),
    ),
    err.el,
    previewSlot,
  );
}
