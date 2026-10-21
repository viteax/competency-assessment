// Кабинет преподавателя: закреплённые дисциплины, что и сколько разработать, составление
// вопросов и выгрузка ФОМ в Word для учебного управления.

import { api, fill, go, h } from "./core.js";
import { questionBank } from "./admin/questions.js";

const semesters = (d) => (d.first_semester === d.last_semester ? `${d.first_semester}` : `${d.first_semester}–${d.last_semester}`);
const fundUrl = (id, key) => `/teacher/disciplines/${id}/fund.docx${key ? "?key=true" : ""}`;

// «Сделано 10 из 40» и остаток по каждой компетенции.
function progressView(d) {
  const left = Math.max(d.required - d.done, 0);
  return h("div", {},
    h("div", { class: "progress-line" },
      h("strong", {}, d.required ? `Сделано ${d.done} из ${d.required}` : `Вопросов в банке: ${d.competencies.reduce((n, c) => n + c.done, 0)}`),
      d.required ? h("span", { class: left ? "badge warn" : "badge ok" }, left ? `осталось ${left}` : "готово") : null,
    ),
    d.required ? h("progress", { max: d.required, value: d.done, "aria-label": "Готовность вопросов" }) : null,
    h("table", { class: "small" },
      h("tr", {}, ["Компетенция", "Нужно", "Сделано", "Осталось"].map((t) => h("th", {}, t))),
      d.competencies.map((c) => h("tr", {},
        h("td", { class: "wrap main", title: c.description }, h("strong", {}, c.code), ` – ${c.description}`),
        h("td", {}, c.required || "–"),
        h("td", {}, c.done),
        h("td", {}, c.required ? Math.max(c.required - c.done, 0) : "–"),
      ))),
    d.required ? null : h("p", { class: "muted small" }, "Сколько вопросов нужно, ещё не указано – уточните у администратора."),
  );
}

export async function teacherDisciplines(render) {
  const mine = await api("/teacher/disciplines");
  render(
    h("h1", {}, "Мои дисциплины"),
    mine.length
      ? [
          h("p", { class: "muted" }, "Для каждой дисциплины указано, по каким компетенциям и сколько тестовых вопросов нужно разработать. Вопросы можно составлять частями – прогресс сохраняется."),
          mine.map((d) => h("div", { class: "card" },
            h("h2", {}, d.discipline),
            h("p", { class: "muted small mt-0" }, `${d.direction}, ${semesters(d)} семестр`),
            progressView(d),
            h("div", { class: "row mt-m" },
              h("button", { class: "primary", onclick: () => go((r) => disciplineQuestions(r, d.discipline_id), teacherDisciplines) }, "Составлять вопросы"),
              h("a", { class: "button", download: "", href: fundUrl(d.discipline_id, false) }, "ФОМ в Word"),
              h("a", { class: "button", download: "", href: fundUrl(d.discipline_id, true) }, "ФОМ с ответами (Word)"),
            ),
          )),
        ]
      : h("p", { class: "muted" }, "За вами пока не закреплены дисциплины. Обратитесь к администратору."),
  );
}

// Банк вопросов одной дисциплины с панелью прогресса сверху.
async function disciplineQuestions(render, disciplineId) {
  const load = async () => (await api("/teacher/disciplines")).find((d) => d.discipline_id === disciplineId);
  const d = await load();
  if (!d) return go(teacherDisciplines);
  const panel = h("div", { class: "card" });
  const drawPanel = (data) => fill(panel,
    h("button", { type: "button", class: "link bare", onclick: () => go(teacherDisciplines) }, "← Мои дисциплины"),
    h("p", { class: "muted small" }, `${data.direction}, ${semesters(data)} семестр`),
    progressView(data));
  drawPanel(d);
  await questionBank(render, {
    title: d.discipline,
    intro: panel,
    competencies: d.competencies.map((c) => ({ id: c.competency_id, code: c.code, description: c.description })),
    disciplines: [{ id: d.discipline_id, name: d.discipline }],
    lockedDiscipline: d.discipline_id,
    fundUrl,
    onChange: async () => drawPanel(await load()),
  });
}
