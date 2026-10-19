// Банк вопросов: у администратора — все вопросы, у преподавателя — вопросы одной его
// дисциплины (questionBank с lockedDiscipline).

import { api, byId, DIFFICULTIES, errorBox, fill, h, QUESTION_KINDS } from "../core.js";

export async function adminQuestions(render) {
  const [competencies, disciplines] = await Promise.all([api("/competencies"), api("/disciplines")]);
  await questionBank(render, {
    title: "Банк вопросов",
    competencies,
    disciplines,
    fundUrl: (id, key) => `/disciplines/${id}/fund.docx${key ? "?key=true" : ""}`,
  });
}

// opts: title, competencies, disciplines, fundUrl(disciplineId, key),
//       lockedDiscipline (id) — только эта дисциплина, intro — блок над таблицей,
//       onChange() — после сохранения или удаления вопроса.
export async function questionBank(render, opts) {
  const { competencies, disciplines, lockedDiscipline = null } = opts;
  const comps = byId(competencies);
  const discs = byId(disciplines);

  const filterCompetency = h("select", {}, h("option", { value: "" }, "Все компетенции"),
    competencies.map((c) => h("option", { value: c.id }, c.code)));
  const filterDiscipline = h("select", { "aria-label": "Дисциплина" }, h("option", { value: "" }, "Все дисциплины"),
    disciplines.map((d) => h("option", { value: d.id }, d.name)));
  if (lockedDiscipline) filterDiscipline.value = String(lockedDiscipline);
  const err = errorBox();
  const fundBlank = h("a", { class: "button", download: "" }, "ФОМ дисциплины (Word)");
  const fundKey = h("a", { class: "button", download: "" }, "ФОМ с ответами (Word)");
  const fundHint = h("span", { class: "muted small" }, "Выберите дисциплину, чтобы выгрузить её ФОМ в Word.");
  function setFundLinks() {
    const id = filterDiscipline.value;
    fundBlank.hidden = fundKey.hidden = !id;
    fundHint.hidden = Boolean(id);
    if (id) {
      fundBlank.href = opts.fundUrl(id, false);
      fundKey.href = opts.fundUrl(id, true);
    }
  }
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
            h("tr", {}, ["Вопрос", "Тип", "Компетенция", lockedDiscipline ? null : "Дисциплина", ""].filter((t) => t !== null).map((t) => h("th", {}, t))),
            questions.map((q) =>
              h("tr", {},
                h("td", { class: "wrap" }, q.text, q.in_use ? [" ", h("span", { class: "badge ok" }, "в тестах")] : null),
                h("td", { class: "wrap small" }, QUESTION_KINDS[q.kind], q.difficulty === "advanced" ? h("div", { class: "muted" }, "повышенный") : null),
                h("td", {}, comps.get(q.competency_id)?.code || "—"),
                lockedDiscipline ? null : h("td", { class: "wrap" }, discs.get(q.discipline_id)?.name || "—"),
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
                        await opts.onChange?.();
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
    const competency = h("select", { required: true, disabled: locked, "aria-label": "Компетенция" },
      competencies.map((c) => h("option", { value: c.id }, `${c.code} — ${c.description}`)));
    const discipline = h("select", { disabled: Boolean(lockedDiscipline), "aria-label": "Дисциплина вопроса" },
      lockedDiscipline ? null : h("option", { value: "" }, "Без дисциплины"),
      disciplines.map((d) => h("option", { value: d.id }, d.name)));
    const text = h("textarea", { rows: 3, required: true });
    const kind = h("select", { disabled: locked, "aria-label": "Тип задания" },
      Object.entries(QUESTION_KINDS).map(([v, label]) => h("option", { value: v }, label)));
    const difficulty = h("select", { "aria-label": "Уровень сложности" },
      Object.entries(DIFFICULTIES).map(([v, label]) => h("option", { value: v }, label)));
    const editor = optionsEditor(locked);

    if (q) {
      competency.value = String(q.competency_id);
      discipline.value = q.discipline_id ? String(q.discipline_id) : "";
      text.value = q.text;
      kind.value = q.kind;
      difficulty.value = q.difficulty;
    } else {
      if (filterCompetency.value) competency.value = filterCompetency.value;
      if (filterDiscipline.value) discipline.value = filterDiscipline.value;
    }
    if (lockedDiscipline) discipline.value = String(lockedDiscipline);
    editor.draw(kind.value, q);
    kind.addEventListener("change", () => editor.draw(kind.value, null));

    fill(formSlot,
      h("form", {
        class: "card edit-form",
        onsubmit: async (event) => {
          event.preventDefault();
          formErr.clear();
          let options;
          try {
            options = editor.read();
          } catch (e) {
            return formErr.show(e);
          }
          const body = {
            competency_id: Number(competency.value),
            indicator_id: q?.indicator_id ?? null,  // индикаторы в интерфейсе не используются
            discipline_id: discipline.value ? Number(discipline.value) : null,
            text: text.value.trim(),
            kind: kind.value,
            difficulty: difficulty.value,
            options,
          };
          try {
            if (q) await api(`/questions/${q.id}`, { method: "PUT", body });
            else await api("/questions", { method: "POST", body });
            fill(formSlot);
            await refresh();
            await opts.onChange?.();
          } catch (e) {
            formErr.show(e);
          }
        },
      },
      h("h2", { style: "margin-top:0" }, q ? "Изменить вопрос" : "Новый вопрос"),
      locked ? h("p", { class: "muted" }, "Вопрос уже входит в собранные тесты, по нему могут быть ответы студентов. Можно править формулировки, дисциплину и сложность; для остального создайте новый вопрос.") : null,
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Тип задания"), kind),
        h("div", {}, h("label", {}, "Уровень сложности"), difficulty),
      ),
      h("label", {}, "Компетенция"), competency,
      lockedDiscipline ? null : [h("label", {}, "Дисциплина"), discipline],
      h("label", {}, "Текст задания"), text,
      editor.el,
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
  filterDiscipline.addEventListener("change", () => { setFundLinks(); refresh(); });
  setFundLinks();
  render(
    h("h1", {}, opts.title),
    opts.intro || null,
    h("div", { class: "card" },
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Компетенция"), filterCompetency),
        lockedDiscipline ? null : h("div", {}, h("label", {}, "Дисциплина"), filterDiscipline),
        h("button", { class: "primary", onclick: () => openForm(null) }, "Новый вопрос"),
      ),
      h("div", { class: "row", style: "margin-top:10px" }, fundBlank, fundKey, fundHint),
      err.el,
      h("div", { style: "margin-top:12px" }, tableSlot),
    ),
    formSlot,
  );
  await refresh();
}

// Редактор вариантов: своя форма для каждого типа задания. read() возвращает options для API.
function optionsEditor(locked) {
  const el = h("div");
  let read = () => [];

  const textInput = (value, placeholder) => h("input", { type: "text", value: value ?? "", required: true, placeholder });
  const removeButton = (row) => (locked ? null : h("button", { type: "button", class: "link danger", title: "Удалить", onclick: () => row.remove() }, "✕"));
  const withId = (row, option) => { row.dataset.id = option?.id ?? ""; return row; };
  const idOf = (row) => (row.dataset.id ? { id: Number(row.dataset.id) } : {});

  function list(label, hint, makeRow, initial, addLabel) {
    const box = h("div", { class: "options" });
    initial.forEach((o) => box.append(makeRow(o)));
    return {
      box,
      nodes: [
        h("label", {}, label),
        hint ? h("p", { class: "muted small", style: "margin-top:0" }, hint) : null,
        box,
        locked ? null : h("button", { type: "button", class: "link", onclick: () => box.append(makeRow()) }, addLabel),
      ],
    };
  }

  const drawers = {
    single(q) {
      const name = `correct-${Date.now()}`;
      const row = (o = {}) => {
        const r = h("div", { class: "option-row" },
          h("input", { type: "radio", name, checked: o.is_correct, disabled: locked, title: "Правильный ответ" }),
          textInput(o.text, "Вариант ответа"));
        r.append(removeButton(r) || "");
        return withId(r, o);
      };
      const initial = q ? q.options : [{ is_correct: true }, {}, {}, {}];
      const { box, nodes } = list("Варианты ответа (отметьте правильный)", null, row, initial, "+ вариант");
      read = () => {
        const options = [...box.children].map((r) => ({ ...idOf(r), text: r.querySelector("input[type=text]").value.trim(), is_correct: r.querySelector("input[type=radio]").checked }));
        if (!options.some((o) => o.is_correct)) throw new Error("отметьте правильный вариант");
        return options;
      };
      return nodes;
    },
    open(q) {
      const row = (o = {}) => { const r = h("div", { class: "option-row" }, textInput(o.text, "Правильный ответ")); r.append(removeButton(r) || ""); return withId(r, o); };
      const { box, nodes } = list("Допустимые ответы",
        "Засчитывается совпадение с любым из них. Регистр, «ё/е», кавычки и точка в конце не важны.",
        row, q ? q.options : [{}], "+ ещё вариант ответа");
      read = () => [...box.children].map((r) => ({ ...idOf(r), text: r.querySelector("input").value.trim() }));
      return nodes;
    },
    sequence(q) {
      const row = (o = {}) => {
        const r = h("div", { class: "option-row" }, h("span", { class: "seq-num" }), textInput(o.text, "Элемент"));
        if (!locked) {
          r.append(
            h("button", { type: "button", class: "link", title: "Выше", onclick: () => r.previousElementSibling?.before(r) }, "↑"),
            h("button", { type: "button", class: "link", title: "Ниже", onclick: () => r.nextElementSibling?.after(r) }, "↓"),
            removeButton(r));
        }
        return withId(r, o);
      };
      const { box, nodes } = list("Элементы в правильном порядке",
        "Студенту они будут показаны вперемешку; в Word — пронумерованы в случайном порядке.",
        row, q ? q.options : [{}, {}, {}, {}], "+ элемент");
      box.classList.add("numbered");
      read = () => [...box.children].map((r) => ({ ...idOf(r), text: r.querySelector("input").value.trim() }));
      return nodes;
    },
    matching(q) {
      const byId = new Map((q?.options || []).map((o) => [o.id, o]));
      const lefts = (q?.options || []).filter((o) => o.match_id);
      const used = new Set(lefts.map((o) => o.match_id));
      const extras = (q?.options || []).filter((o) => !o.match_id && !used.has(o.id));
      const pairRow = (pair = {}) => {
        const r = h("div", { class: "option-row pair-row" },
          textInput(pair.left?.text, "Левый столбец (например, термин)"),
          h("span", { "aria-hidden": "true" }, "→"),
          textInput(pair.right?.text, "Правый столбец (его пара)"));
        r.append(removeButton(r) || "");
        r.dataset.left = pair.left?.id ?? "";
        r.dataset.right = pair.right?.id ?? "";
        return r;
      };
      const extraRow = (o = {}) => { const r = h("div", { class: "option-row" }, textInput(o.text, "Лишний элемент правого столбца")); r.append(removeButton(r) || ""); return withId(r, o); };
      const pairs = list("Пары (левый столбец → правильный элемент правого)", null, pairRow,
        q ? lefts.map((o) => ({ left: o, right: byId.get(o.match_id) })) : [{}, {}, {}, {}], "+ пара");
      const extra = list("Лишние элементы правого столбца (необязательно)", "Усложняют задание: их нельзя сопоставить ни с чем.", extraRow, extras, "+ лишний элемент");
      read = () => {
        const rows = [...pairs.box.children];
        const lefts = rows.map((r, i) => ({ ...(r.dataset.left ? { id: Number(r.dataset.left) } : {}), text: r.querySelectorAll("input")[0].value.trim(), match_index: rows.length + i }));
        const rights = rows.map((r) => ({ ...(r.dataset.right ? { id: Number(r.dataset.right) } : {}), text: r.querySelectorAll("input")[1].value.trim() }));
        const more = [...extra.box.children].map((r) => ({ ...idOf(r), text: r.querySelector("input").value.trim() }));
        return [...lefts, ...rights, ...more];
      };
      return [...pairs.nodes, ...extra.nodes];
    },
  };

  return {
    el,
    draw(kind, q) { fill(el, drawers[kind](q)); },
    read: () => read(),
  };
}
