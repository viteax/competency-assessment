// Банк вопросов: у администратора – все вопросы, у преподавателя – вопросы одной его
// дисциплины (questionBank с lockedDiscipline).

import { api, byId, DIFFICULTIES, errorBox, fill, h, QUESTION_KINDS } from "../core.js";
import { currentDirection, directionPicker } from "./directions.js";
import { fundImportCard } from "./fund-import.js";

// У каждого направления свои компетенции и дисциплины: банк показывается по направлению.
export async function adminQuestions(render, direction = null) {
  const directions = await api("/directions");
  direction = direction || currentDirection(directions);
  const query = direction ? `?direction_id=${direction.id}` : "";
  const loadLists = async () => {
    const [competencies, disciplines] = await Promise.all([api(`/competencies${query}`), api(`/disciplines${query}`)]);
    return { competencies, disciplines };
  };
  await questionBank(render, {
    title: "Банк вопросов",
    ...(await loadLists()),
    loadLists,
    directionId: direction?.id,
    intro: directions.length > 1 ? directionPicker(directions, direction, (chosen) => adminQuestions(render, chosen)) : null,
    fundUrl: (id, key) => `/disciplines/${id}/fund.docx${key ? "?key=true" : ""}`,
  });
}

// Ссылки «ФОМ дисциплины» и «ФОМ с ответами»; update(id) – для выбранной дисциплины.
function fundLinks(fundUrl) {
  const blank = h("a", { class: "button", download: "" }, "ФОМ дисциплины (Word)");
  const key = h("a", { class: "button", download: "" }, "ФОМ с ответами (Word)");
  const hint = h("span", { class: "muted small" }, "Выберите дисциплину, чтобы выгрузить её ФОМ в Word.");
  return {
    el: h("div", { class: "row mt-m" }, blank, key, hint),
    update(id) {
      blank.hidden = key.hidden = !id;
      hint.hidden = Boolean(id);
      if (id) {
        blank.href = fundUrl(id, false);
        key.href = fundUrl(id, true);
      }
    },
  };
}

function questionsTable(questions, { comps, discs, lockedDiscipline, onEdit, onDelete }) {
  if (!questions.length) return h("p", { class: "muted" }, "Вопросов не найдено");
  const heads = ["Вопрос", "Тип", "Компетенция", lockedDiscipline ? null : "Дисциплина", ""];
  return h("table", {},
    h("tr", {}, heads.filter((t) => t !== null).map((t) => h("th", {}, t))),
    questions.map((q) =>
      h("tr", {},
        h("td", { class: "wrap main" }, h("span", { class: "pre-line" }, q.text), q.in_use ? [" ", h("span", { class: "badge ok" }, "в тестах")] : null),
        h("td", { class: "wrap small" }, QUESTION_KINDS[q.kind], q.difficulty === "advanced" ? h("div", { class: "muted" }, "повышенный") : null),
        h("td", {}, comps.get(q.competency_id)?.code || "–"),
        lockedDiscipline ? null : h("td", { class: "wrap" }, discs.get(q.discipline_id)?.name || "–"),
        h("td", { class: "actions" },
          h("button", { class: "link", onclick: () => onEdit(q) }, "Изменить"),
          q.in_use ? null : h("button", { class: "link danger", onclick: () => onDelete(q) }, "Удалить"),
        ),
      ),
    ),
  );
}

// Длинные формулировки в выпадающем списке раскрываются на весь экран – обрезаем.
const shortText = (t, max = 70) => (t.length > max ? `${t.slice(0, max).trimEnd()}…` : t);

// Форма вопроса (q – существующий или null). defaults – компетенция и дисциплина из фильтров.
function questionForm(q, { competencies, disciplines, lockedDiscipline, defaults, onSaved, onCancel }) {
  const locked = Boolean(q?.in_use);
  const formErr = errorBox();
  const competency = h("select", { required: true, disabled: locked, "aria-label": "Компетенция" },
    competencies.map((c) => h("option", { value: c.id, title: c.description }, shortText(`${c.code} – ${c.description}`))));
  const competencyFull = h("p", { class: "hint" });
  const showCompetency = () => {
    competencyFull.textContent = competencies.find((c) => String(c.id) === competency.value)?.description || "";
  };
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
    if (defaults.competency) competency.value = defaults.competency;
    if (defaults.discipline) discipline.value = defaults.discipline;
  }
  if (lockedDiscipline) discipline.value = String(lockedDiscipline);
  showCompetency();
  competency.addEventListener("change", showCompetency);
  editor.draw(kind.value, q);
  kind.addEventListener("change", () => editor.draw(kind.value, null));

  async function save(event) {
    event.preventDefault();
    formErr.clear();
    try {
      const body = {
        competency_id: Number(competency.value),
        indicator_id: q?.indicator_id ?? null, // индикаторы в интерфейсе не используются
        discipline_id: discipline.value ? Number(discipline.value) : null,
        text: text.value.trim(),
        kind: kind.value,
        difficulty: difficulty.value,
        options: editor.read(),
      };
      if (q) await api(`/questions/${q.id}`, { method: "PUT", body });
      else await api("/questions", { method: "POST", body });
      await onSaved();
    } catch (e) {
      formErr.show(e);
    }
  }

  return h("form", { class: "card edit-form", onsubmit: save },
    h("h2", {}, q ? "Изменить вопрос" : "Новый вопрос"),
    locked ? h("p", { class: "muted" }, "Вопрос уже входит в собранные тесты, по нему могут быть ответы студентов. Можно править формулировки, дисциплину и сложность; для остального создайте новый вопрос.") : null,
    h("div", { class: "row" },
      h("div", {}, h("label", {}, "Тип задания"), kind),
      h("div", {}, h("label", {}, "Уровень сложности"), difficulty),
    ),
    h("label", {}, "Компетенция"), competency, competencyFull,
    lockedDiscipline ? null : [h("label", {}, "Дисциплина"), discipline],
    h("label", {}, "Текст задания"), text,
    editor.el,
    h("div", { class: "row mt-l" },
      h("button", { class: "primary" }, "Сохранить"),
      h("button", { type: "button", onclick: onCancel }, "Отмена"),
    ),
    formErr.el,
  );
}

// opts: title, competencies, disciplines, fundUrl(disciplineId, key),
//       lockedDiscipline (id) – только эта дисциплина, intro – блок над таблицей,
//       directionId – вопросы только этого направления,
//       loadLists() – заново получить компетенции и дисциплины (после загрузки из ФОС),
//       onChange() – после сохранения или удаления вопроса.
export async function questionBank(render, opts) {
  const { lockedDiscipline = null } = opts;
  let { competencies, disciplines } = opts;
  let comps = byId(competencies);
  let discs = byId(disciplines);

  const filterCompetency = h("select", {});
  const filterDiscipline = h("select", { "aria-label": "Дисциплина" });
  // Списки фильтров (выбранное значение сохраняется, если оно еще есть).
  function fillFilters() {
    const [competency, discipline] = [filterCompetency.value, filterDiscipline.value];
    fill(filterCompetency, h("option", { value: "" }, "Все компетенции"),
      competencies.map((c) => h("option", { value: c.id }, c.code)));
    fill(filterDiscipline, h("option", { value: "" }, "Все дисциплины"),
      disciplines.map((d) => h("option", { value: d.id }, d.name)));
    filterCompetency.value = comps.has(Number(competency)) ? competency : "";
    filterDiscipline.value = discs.has(Number(discipline)) ? discipline : "";
  }
  fillFilters();
  if (lockedDiscipline) filterDiscipline.value = String(lockedDiscipline);
  const search = h("input", { type: "search", placeholder: "Поиск по тексту задания", "aria-label": "Поиск" });
  const err = errorBox();
  const fund = fundLinks(opts.fundUrl);
  const formSlot = h("div");
  const counter = h("p", { class: "muted small mt-0" });
  const tableSlot = h("div", { class: "table-wrap" });
  let loaded = [];

  async function changed() {
    fill(formSlot);
    await refresh();
    await opts.onChange?.();
  }

  async function remove(q) {
    if (!confirm("Удалить вопрос?")) return;
    err.clear();
    try {
      await api(`/questions/${q.id}`, { method: "DELETE" });
      await changed();
    } catch (e) {
      err.show(e);
    }
  }

  function openImport() {
    fill(formSlot, fundImportCard({
      directionId: opts.directionId,
      disciplineId: lockedDiscipline,
      onDone: async () => {
        if (opts.loadLists) {
          ({ competencies, disciplines } = await opts.loadLists());
          comps = byId(competencies);
          discs = byId(disciplines);
          fillFilters();
        }
        await refresh();
        await opts.onChange?.();
      },
      onCancel: () => fill(formSlot),
    }));
    formSlot.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  function openForm(q) {
    fill(formSlot, questionForm(q, {
      competencies, disciplines, lockedDiscipline,
      defaults: { competency: filterCompetency.value, discipline: filterDiscipline.value },
      onSaved: changed,
      onCancel: () => fill(formSlot),
    }));
    formSlot.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function refresh() {
    const params = new URLSearchParams();
    if (opts.directionId) params.set("direction_id", opts.directionId);
    if (filterCompetency.value) params.set("competency_id", filterCompetency.value);
    if (filterDiscipline.value) params.set("discipline_id", filterDiscipline.value);
    loaded = await api(`/questions?${params}`);
    drawTable();
  }

  function drawTable() {
    const words = search.value.toLowerCase().split(/\s+/).filter(Boolean);
    const shown = loaded.filter((q) => words.every((w) => q.text.toLowerCase().includes(w)));
    counter.textContent = shown.length === loaded.length
      ? `Вопросов: ${loaded.length}`
      : `Найдено: ${shown.length} из ${loaded.length}`;
    fill(tableSlot, questionsTable(shown, { comps, discs, lockedDiscipline, onEdit: openForm, onDelete: remove }));
  }

  filterCompetency.addEventListener("change", refresh);
  search.addEventListener("input", drawTable);
  filterDiscipline.addEventListener("change", () => { fund.update(filterDiscipline.value); refresh(); });
  fund.update(filterDiscipline.value);
  render(
    h("h1", {}, opts.title),
    opts.intro || null,
    h("div", { class: "card" },
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Компетенция"), filterCompetency),
        lockedDiscipline ? null : h("div", {}, h("label", {}, "Дисциплина"), filterDiscipline),
        h("button", { class: "primary", onclick: () => openForm(null) }, "Новый вопрос"),
        h("button", { onclick: openImport }, "Загрузить из ФОС (Word)"),
      ),
      fund.el,
      err.el,
    ),
    formSlot,
    h("div", { class: "card" },
      h("div", { class: "row" }, h("div", { class: "grow" }, search)),
      h("div", { class: "mt-s" }, counter),
      tableSlot,
    ),
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
        hint ? h("p", { class: "muted small mt-0" }, hint) : null,
        box,
        locked ? null : h("button", { type: "button", class: "link", onclick: () => box.append(makeRow()) }, addLabel),
      ],
    };
  }

  const drawers = {
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
        "Студенту они будут показаны вперемешку; в Word – пронумерованы в случайном порядке.",
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
