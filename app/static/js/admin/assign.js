// Назначение теста группе. Новый тест собирается так, как проводят оценку остаточных знаний:
// группа → семестр → дисциплины, завершённые до него → компетенции этих дисциплин →
// вопросы только из завершённых дисциплин, в вариантах – по числу студентов группы.

import { api, errorBox, fill, h } from "../core.js";
import { kindBadge, loadTests, withDirection } from "./directions.js";

const KINDS = ["УК", "ОПК", "ПК"];
const semesters = (d) => (d.first_semester === d.last_semester ? `${d.first_semester}` : `${d.first_semester}–${d.last_semester}`);
const plural = (n, one, few, many) => {
  const mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
};
const variantsWord = (n) => `${n} ${plural(n, "вариант", "варианта", "вариантов")}`;
const numberInput = (attrs) => h("input", { type: "number", class: "narrow", ...attrs });

// --- расчёты ------------------------------------------------------------------

// Пул дисциплин: разрешённые дисциплины, в которых есть выбранные компетенции.
function poolOf(selected, allowed) {
  if (!allowed) return [];
  const ids = new Set(selected.map((c) => c.id));
  return allowed.filter((d) => d.competency_ids.some((id) => ids.has(id)));
}

// Вопросов по компетенции в банке; allowed – дисциплины, из которых можно брать (null – любые).
function questionCount(questions, competencyId, allowed) {
  const ids = allowed && new Set(allowed.map((d) => d.id));
  return questions.filter((q) => q.competency_id === competencyId && (!ids || ids.has(q.discipline_id))).length;
}

// Сколько вариантов получится: counts – число вопросов по каждой компетенции, k – вопросов на
// компетенцию в варианте, wanted – сколько вариантов просят.
function estimateVariants(counts, k, wanted) {
  const disjoint = Math.min(...counts.map((n) => Math.floor(n / k)));
  // Сколько различных вариантов вообще можно составить (считаем до wanted, чтобы не переполниться).
  let possible = 1;
  for (const n of counts) {
    let c = 1;
    for (let i = 0; i < k && c <= wanted; i++) c = (c * (n - i)) / (i + 1);
    possible = Math.min(possible * Math.round(c), wanted + 1);
  }
  return { variants: Math.min(wanted, possible), disjoint };
}

// --- отрисовка блоков ------------------------------------------------------------

function summaryNodes({ selected, allowed, counts, k, wanted }) {
  const disciplinesLine = allowed
    ? h("div", {}, h("strong", {}, "Вопросы из дисциплин: "), poolOf(selected, allowed).map((d) => d.name).join(", ") || "–")
    : h("div", {}, h("strong", {}, "Вопросы из любых дисциплин банка"));
  const short = selected.map((c, i) => [c, counts[i]]).filter(([, n]) => n < k);
  if (short.length) {
    return {
      blocked: true,
      nodes: [disciplinesLine,
        h("div", { class: "error mt-s" },
          "Не хватает вопросов: ",
          short.map(([c, n]) => `${c.code} – ${n} из ${k}`).join(", "),
          ". Уменьшите число вопросов на компетенцию или добавьте вопросы в банк.")],
    };
  }
  const { variants, disjoint } = estimateVariants(counts, k, wanted);
  const total = k * selected.length;
  return {
    blocked: false,
    nodes: [disciplinesLine,
      h("div", { class: "mt-s" },
        h("strong", {}, variantsWord(variants)),
        ` по ${total} ${plural(total, "вопросу", "вопроса", "вопросов")} (${k} на компетенцию). `,
        variants <= disjoint
          ? "Варианты не пересекаются."
          : `Вопросов на непересекающиеся хватает на ${disjoint}, поэтому варианты частично пересекаются (как «3 вопроса из одного, 2 из другого»), но все разные.`,
        variants < wanted ? ` Различных сочетаний вопросов меньше, чем вариантов: будет ${variants}.` : "",
        " Каждому студенту – свой вариант, пока они не закончатся.")],
  };
}

function disciplineNodes(plan, checks, onChange) {
  if (!plan) return h("p", { class: "muted small" }, "Учебный план не учитывается: доступны все компетенции и вопросы банка.");
  checks.clear();
  return [
    h("h3", {}, `Завершены до ${plan.semester}-го семестра`),
    plan.finished.length
      ? h("div", { class: "check-list check-grid" }, plan.finished.map((d) => {
          const box = h("input", { type: "checkbox", checked: true, onchange: onChange });
          checks.set(d.id, box);
          return h("label", {}, box, `${d.name} `, kindBadge(d.kind), " ", h("span", { class: "muted" }, `(${semesters(d)} сем.)`));
        }))
      : h("p", { class: "muted" }, "Ни одна дисциплина ещё не завершена – проверять остаточные знания пока не по чему."),
    plan.not_finished.length
      ? h("p", { class: "muted small" }, "Ещё изучаются или впереди: ",
          plan.not_finished.map((d) => `${d.name} (${semesters(d)})`).join(", "))
      : null,
    plan.unplanned.length
      ? h("p", { class: "small error" }, "Без семестров в учебном плане (в тест не попадут): ",
          plan.unplanned.join(", "), ". Укажите их в «Подготовка → Учебный план и преподаватели».")
      : null,
  ];
}

// visible – компетенции, которые можно выбрать; checks – чекбоксы (сохраняют отметки при перерисовке).
function competencyNodes(visible, checks, countOf, onChange, emptyText) {
  if (!visible.length) return h("p", { class: "muted" }, emptyText);
  return KINDS.map((kind) => {
    const items = visible.filter((c) => c.kind === kind);
    if (!items.length) return null;
    return h("div", {},
      h("h3", {}, kind),
      items.map((c) => {
        const box = checks.get(c.id) || h("input", { type: "checkbox", value: c.id, onchange: onChange });
        checks.set(c.id, box);
        return h("label", {}, box, h("strong", {}, c.code), ` – ${c.description} `,
          h("span", { class: "muted" }, `(вопросов: ${countOf(c)})`));
      }),
    );
  });
}

// --- новый тест -------------------------------------------------------------------

// Раздел «Собрать новый тест». setSubmitBlocked – заблокировать кнопку, пока вопросов не хватает.
function newTestSection({ data, group, err, setSubmitBlocked }) {
  const { competencies, questions, tests, students, groupsById } = data;
  const semester = numberInput({ min: 1, max: 12, "aria-label": "Семестр" });
  const semesterHint = h("span", { class: "muted small" });
  const ignorePlan = h("input", { type: "checkbox" });

  const titleKey = (t) => t.split(/\s+/).filter(Boolean).join(" ").toLowerCase();
  const title = h("input", { type: "text", required: true, placeholder: "любое, например «Остаточные знания ПИ-21, осень 2026»" });
  const titleHint = h("div", { class: "error small mt-xs" });
  title.addEventListener("input", () => {
    const taken = tests.find((t) => titleKey(t.title) === titleKey(title.value));
    titleHint.textContent = taken ? "Тест с таким названием уже есть – назовите иначе или выберите «Назначить готовый тест»" : "";
  });
  const perCompetency = numberInput({ min: 1, max: 50, value: 5, "aria-label": "Вопросов на компетенцию" });
  const variantsInput = numberInput({ min: 1, max: 300, "aria-label": "Вариантов" });
  const variantsHint = h("span", { class: "muted small" });

  let plan = null; // ответ /tests/plan или null, если учебный план не учитывается
  const disciplineChecks = new Map(); // id дисциплины → чекбокс
  const competencyChecks = new Map();
  const disciplineBox = h("div");
  const competencyBox = h("div", { class: "check-list" });
  const summary = h("div", { class: "notice", hidden: true });

  // Дисциплины, из которых можно брать вопросы (отмеченные из завершённых); null – любые.
  const allowedDisciplines = () => (plan ? plan.finished.filter((d) => disciplineChecks.get(d.id)?.checked) : null);
  const selectedCompetencies = () =>
    competencies.filter((c) => competencyChecks.get(c.id)?.checked && competencyChecks.get(c.id).isConnected);

  function drawSummary() {
    const allowed = allowedDisciplines();
    const selected = selectedCompetencies();
    const k = Number(perCompetency.value) || 0;
    setSubmitBlocked(false);
    if (!selected.length || k < 1) {
      summary.hidden = true;
      return;
    }
    const pool = allowed && poolOf(selected, allowed);
    const counts = selected.map((c) => questionCount(questions, c.id, pool));
    const wanted = Math.max(Number(variantsInput.value) || 1, 1);
    const { blocked, nodes } = summaryNodes({ selected, allowed, counts, k, wanted });
    setSubmitBlocked(blocked);
    fill(summary, nodes);
    summary.hidden = false;
  }

  function drawCompetencies() {
    const allowed = allowedDisciplines();
    // Без учебного плана – все компетенции направления группы.
    const own = competencies.filter((c) => c.direction_id === groupsById.get(Number(group.value))?.direction_id);
    const available = new Set(allowed ? allowed.flatMap((d) => d.competency_ids) : own.map((c) => c.id));
    fill(competencyBox, competencyNodes(
      competencies.filter((c) => available.has(c.id)),
      competencyChecks,
      (c) => questionCount(questions, c.id, allowed && poolOf([c], allowed)),
      drawSummary,
      plan ? "Нет компетенций: не выбрано ни одной завершённой дисциплины." : "Компетенций пока нет.",
    ));
    drawSummary();
  }

  let planRequest = 0;
  async function loadPlan() {
    err.clear();
    const current = ++planRequest;
    const g = groupsById.get(Number(group.value));
    semesterHint.textContent = g?.current_semester
      ? `сейчас у группы ${g.current_semester}-й (по году набора ${g.start_year})`
      : "год набора группы не указан – введите семестр";
    if (ignorePlan.checked) {
      plan = null;
    } else if (!semester.value) {
      plan = { semester: null, finished: [], not_finished: [], unplanned: [] };
      fill(disciplineBox, h("p", { class: "muted" }, "Укажите семестр, в котором сейчас группа."));
      drawCompetencies();
      return;
    } else {
      try {
        const loaded = await api(`/tests/plan?group_id=${group.value}&semester=${semester.value}`);
        if (current !== planRequest) return; // пока ждали, выбрали другую группу или семестр
        plan = loaded;
      } catch (e) {
        return err.show(e);
      }
    }
    fill(disciplineBox, disciplineNodes(plan, disciplineChecks, drawCompetencies));
    drawCompetencies();
  }

  semester.addEventListener("change", loadPlan);
  ignorePlan.addEventListener("change", () => {
    semester.disabled = ignorePlan.checked;
    loadPlan();
  });
  perCompetency.addEventListener("input", drawSummary);
  variantsInput.addEventListener("input", drawSummary);

  return {
    el: h("div", {},
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Семестр, в котором сейчас группа"), semester),
        h("div", { class: "pad-bottom" }, semesterHint),
      ),
      h("label", { class: "inline small" }, ignorePlan, "Не учитывать учебный план (все дисциплины)"),
      disciplineBox,
      h("h3", {}, "Компетенции"),
      competencyBox,
      h("div", { class: "row" },
        h("div", { class: "grow" }, h("label", {}, "Название теста"), title, titleHint),
        h("div", {}, h("label", {}, "Вопросов на компетенцию"), perCompetency),
        h("div", {}, h("label", {}, "Вариантов"), variantsInput),
      ),
      h("p", { class: "muted small mt-xs mb-0" }, variantsHint),
      summary,
    ),
    title,
    drawSummary,
    loadPlan,
    // При смене группы: её текущий семестр и вариантов по числу студентов.
    resetForGroup() {
      semester.value = groupsById.get(Number(group.value))?.current_semester ?? "";
      const n = students.filter((st) => st.group_id === Number(group.value)).length;
      variantsInput.value = Math.max(n, 1);
      variantsHint.textContent = n ? `по числу студентов группы (${n})` : "в группе пока нет студентов";
    },
    // Тело POST /tests или ошибка, если не выбрано ни одной компетенции.
    body() {
      const selected = selectedCompetencies();
      if (!selected.length) throw new Error("выберите хотя бы одну компетенцию");
      const allowed = allowedDisciplines();
      return {
        title: title.value,
        competency_ids: selected.map((c) => c.id),
        discipline_ids: allowed ? poolOf(selected, allowed).map((d) => d.id) : [],
        questions_per_competency: Number(perCompetency.value),
        variant_count: Number(variantsInput.value) || null,
        semester: plan ? plan.semester : null,
      };
    },
  };
}

// --- готовый тест -----------------------------------------------------------------

function existingTestSection({ tests, groupsById }, group) {
  const select = h("select");
  return {
    el: h("div", {},
      h("label", {}, "Тест"),
      select,
      h("p", { class: "muted small" }, "Вопросы те же, что у других групп, – результаты можно сравнивать."),
    ),
    draw() {
      const groupId = Number(group.value);
      fill(select, tests.map((t) => {
        const assigned = t.group_ids.map((id) => groupsById.get(id)?.name).filter(Boolean);
        const already = t.group_ids.includes(groupId);
        return h("option", { value: t.id, disabled: already },
          `${t.title} – ${t.questions_per_variant} вопр., вариантов: ${t.variant_count}`,
          assigned.length ? ` (назначен: ${assigned.join(", ")})` : "",
          already ? " – уже у этой группы" : "");
      }));
      const firstFree = [...select.options].find((o) => !o.disabled);
      if (firstFree) select.value = firstFree.value;
    },
    selected() {
      if (!select.value || select.selectedOptions[0]?.disabled) {
        throw new Error("выберите тест, который ещё не назначен этой группе");
      }
      return tests.find((t) => t.id === Number(select.value));
    },
  };
}

// --- экран --------------------------------------------------------------------------

export const adminAssign = withDirection("Назначить тест группе", async (render, direction) => {
  const query = `?direction_id=${direction.id}`;
  const [groups, competencies, questions, tests, students] = await Promise.all([
    api(`/groups${query}`),
    api(`/competencies${query}`),
    api(`/questions${query}`),
    loadTests(direction),
    api("/students"),
  ]);
  const data = { competencies, questions, tests, students, groupsById: new Map(groups.map((g) => [g.id, g])) };
  const err = errorBox();
  const ok = h("div", { class: "success" });
  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const modeNew = h("input", { type: "radio", name: "assign-mode", checked: true });
  const modeExisting = h("input", { type: "radio", name: "assign-mode", disabled: !tests.length });
  const submit = h("button", { class: "primary" });

  const fresh = newTestSection({ data, group, err, setSubmitBlocked: (blocked) => { submit.disabled = blocked; } });
  const existing = existingTestSection(data, group);

  function switchMode() {
    err.clear();
    fresh.el.hidden = !modeNew.checked;
    existing.el.hidden = modeNew.checked;
    fresh.title.required = modeNew.checked; // скрытое обязательное поле заблокировало бы отправку
    submit.textContent = modeNew.checked ? "Собрать и назначить" : "Назначить";
    if (modeNew.checked) fresh.drawSummary();
    else submit.disabled = false;
  }
  modeNew.addEventListener("change", switchMode);
  modeExisting.addEventListener("change", switchMode);
  group.addEventListener("change", () => {
    fresh.resetForGroup();
    existing.draw();
    fresh.loadPlan();
  });

  async function assign(event) {
    event.preventDefault();
    err.clear();
    ok.textContent = "";
    const groupName = group.selectedOptions[0]?.textContent;
    try {
      let test;
      if (modeNew.checked) {
        test = await api("/tests", { method: "POST", body: fresh.body() });
        tests.unshift({ ...test, group_ids: [] });
      } else {
        test = existing.selected();
      }
      await api("/assignments", { method: "POST", body: { test_id: test.id, group_id: Number(group.value) } });
      tests.find((t) => t.id === test.id).group_ids.push(Number(group.value));
      modeExisting.disabled = false;
      existing.draw();
      ok.textContent = `Тест «${test.title}» (${variantsWord(test.variant_count)} по ${test.questions_per_variant} вопр.) назначен группе ${groupName}. Его варианты и вопросы – на вкладке «Все тесты».`;
    } catch (e) {
      err.show(e);
    }
  }

  render(
    h("h1", {}, "Назначить тест группе"),
    h("form", { class: "card", onsubmit: assign },
      h("label", {}, "Группа"),
      group,
      h("div", { class: "row mode-switch" },
        h("label", { class: "inline" }, modeNew, "Собрать новый тест"),
        h("label", { class: "inline" }, modeExisting, "Назначить готовый тест"),
      ),
      fresh.el,
      existing.el,
      h("div", { class: "mt-l" }, submit),
      err.el,
      ok,
    ),
  );
  fresh.resetForGroup();
  existing.draw();
  switchMode();
  await fresh.loadPlan();
});
