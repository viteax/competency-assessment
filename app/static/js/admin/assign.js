// Назначение теста группе. Новый тест собирается так, как проводят оценку остаточных знаний:
// группа → семестр → дисциплины, завершённые до него → компетенции этих дисциплин →
// вопросы только из завершённых дисциплин, в вариантах – по числу студентов группы.

import { api, errorBox, fill, h } from "../core.js";

const KINDS = ["УК", "ОПК", "ПК"];
const semesters = (d) => (d.first_semester === d.last_semester ? `${d.first_semester}` : `${d.first_semester}–${d.last_semester}`);
const plural = (n, one, few, many) => {
  const mod10 = n % 10, mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
};

export async function adminAssign(render) {
  const [groups, competencies, disciplines, questions, tests, students] = await Promise.all([
    api("/groups"),
    api("/competencies"),
    api("/disciplines"),
    api("/questions"),
    api("/tests"),
    api("/students"),
  ]);
  const groupsById = new Map(groups.map((g) => [g.id, g]));
  const err = errorBox();
  const ok = h("div", { class: "success" });

  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const semester = h("input", { type: "number", min: 1, max: 12, style: "max-width:110px", "aria-label": "Семестр" });
  const semesterHint = h("span", { class: "muted small" });
  const ignorePlan = h("input", { type: "checkbox" });
  const modeNew = h("input", { type: "radio", name: "assign-mode", checked: true });
  const modeExisting = h("input", { type: "radio", name: "assign-mode", disabled: !tests.length });

  // --- новый тест ---
  const titleKey = (t) => t.split(/\s+/).filter(Boolean).join(" ").toLowerCase();
  const title = h("input", { type: "text", required: true, placeholder: "любое, например «Остаточные знания ПИ-21, осень 2026»" });
  const titleHint = h("div", { class: "error small", style: "margin-top:4px" });
  title.addEventListener("input", () => {
    const taken = tests.find((t) => titleKey(t.title) === titleKey(title.value));
    titleHint.textContent = taken ? "Тест с таким названием уже есть – назовите иначе или выберите «Назначить готовый тест»" : "";
  });
  const perCompetency = h("input", { type: "number", min: 1, max: 50, value: 5, style: "max-width:110px", "aria-label": "Вопросов на компетенцию" });
  const variantsInput = h("input", { type: "number", min: 1, max: 300, style: "max-width:110px", "aria-label": "Вариантов" });
  const variantsHint = h("span", { class: "muted small" });
  const studentsInGroup = (id) => students.filter((st) => st.group_id === id).length;
  function resetVariants() {
    const n = studentsInGroup(Number(group.value));
    variantsInput.value = Math.max(n, 1);
    variantsHint.textContent = n ? `по числу студентов группы (${n})` : "в группе пока нет студентов";
  }

  let plan = null; // ответ /tests/plan или null, если учебный план не учитывается
  const disciplineChecks = new Map(); // id дисциплины → чекбокс
  const competencyChecks = new Map();
  const disciplineBox = h("div");
  const competencyBox = h("div", { class: "check-list" });
  const summary = h("div", { class: "notice", hidden: true });

  // Дисциплины, из которых можно брать вопросы (отмеченные из завершённых).
  function allowedDisciplines() {
    if (!plan) return null; // любые
    return plan.finished.filter((d) => disciplineChecks.get(d.id)?.checked);
  }

  function countFor(competencyId, allowed) {
    const ids = allowed && new Set(allowed.map((d) => d.id));
    return questions.filter((q) => q.competency_id === competencyId && (!ids || ids.has(q.discipline_id))).length;
  }

  function selectedCompetencies() {
    return competencies.filter((c) => competencyChecks.get(c.id)?.checked && competencyChecks.get(c.id).isConnected);
  }

  // Пул дисциплин: разрешённые дисциплины, в которых есть выбранные компетенции.
  function pool(selected, allowed) {
    if (!allowed) return [];
    const ids = new Set(selected.map((c) => c.id));
    return allowed.filter((d) => d.competency_ids.some((id) => ids.has(id)));
  }

  function drawSummary() {
    const allowed = allowedDisciplines();
    const selected = selectedCompetencies();
    const k = Number(perCompetency.value) || 0;
    submit.disabled = false;
    if (!selected.length || k < 1) {
      summary.hidden = true;
      return;
    }
    const counts = selected.map((c) => [c, countFor(c.id, allowed && pool(selected, allowed))]);
    const short = counts.filter(([, n]) => n < k);
    const disjoint = Math.min(...counts.map(([, n]) => Math.floor(n / k)));
    const wanted = Math.max(Number(variantsInput.value) || 1, 1);
    // Сколько различных вариантов вообще можно составить (считаем до wanted, чтобы не переполниться).
    let possible = 1;
    for (const [, n] of counts) {
      let c = 1;
      for (let i = 0; i < k && c <= wanted; i++) c = (c * (n - i)) / (i + 1);
      possible = Math.min(possible * Math.round(c), wanted + 1);
    }
    const variants = Math.min(wanted, possible);
    const disciplinesLine = allowed
      ? h("div", {}, h("strong", {}, "Вопросы из дисциплин: "), pool(selected, allowed).map((d) => d.name).join(", ") || "–")
      : h("div", {}, h("strong", {}, "Вопросы из любых дисциплин банка"));
    if (short.length) {
      submit.disabled = true;
      fill(summary, disciplinesLine,
        h("div", { class: "error", style: "margin-top:6px" },
          "Не хватает вопросов: ",
          short.map(([c, n]) => `${c.code} – ${n} из ${k}`).join(", "),
          ". Уменьшите число вопросов на компетенцию или добавьте вопросы в банк."));
    } else {
      fill(summary, disciplinesLine,
        h("div", { style: "margin-top:6px" },
          h("strong", {}, `${variants} ${plural(variants, "вариант", "варианта", "вариантов")}`),
          ` по ${k * selected.length} ${plural(k * selected.length, "вопросу", "вопроса", "вопросов")}`,
          ` (${k} на компетенцию). `,
          variants <= disjoint
            ? "Варианты не пересекаются."
            : `Вопросов на непересекающиеся хватает на ${disjoint}, поэтому варианты частично пересекаются (как «3 вопроса из одного, 2 из другого»), но все разные.`,
          variants < wanted ? ` Различных сочетаний вопросов меньше, чем вариантов: будет ${variants}.` : "",
          " Каждому студенту – свой вариант, пока они не закончатся."));
    }
    summary.hidden = false;
  }

  function drawCompetencies() {
    const allowed = allowedDisciplines();
    const available = allowed
      ? new Set(allowed.flatMap((d) => d.competency_ids))
      : new Set(competencies.map((c) => c.id));
    const visible = competencies.filter((c) => available.has(c.id));
    if (!visible.length) {
      fill(competencyBox, h("p", { class: "muted" }, plan ? "Нет компетенций: не выбрано ни одной завершённой дисциплины." : "Компетенций пока нет."));
      drawSummary();
      return;
    }
    fill(competencyBox,
      KINDS.map((kind) => {
        const items = visible.filter((c) => c.kind === kind);
        if (!items.length) return null;
        return h("div", {},
          h("h3", {}, kind),
          items.map((c) => {
            const box = competencyChecks.get(c.id) || h("input", { type: "checkbox", value: c.id, onchange: drawSummary });
            competencyChecks.set(c.id, box);
            return h("label", {}, box, h("strong", {}, c.code), ` – ${c.description} `,
              h("span", { class: "muted" }, `(вопросов: ${countFor(c.id, allowed && pool([c], allowed))})`));
          }),
        );
      }),
    );
    drawSummary();
  }

  function drawDisciplines() {
    if (!plan) {
      fill(disciplineBox, h("p", { class: "muted small" }, "Учебный план не учитывается: доступны все компетенции и вопросы банка."));
      return;
    }
    disciplineChecks.clear();
    fill(disciplineBox,
      h("h3", {}, `Завершены до ${plan.semester}-го семестра`),
      plan.finished.length
        ? h("div", { class: "check-list check-grid" }, plan.finished.map((d) => {
            const box = h("input", { type: "checkbox", checked: true, onchange: drawCompetencies });
            disciplineChecks.set(d.id, box);
            return h("label", {}, box, `${d.name} `, h("span", { class: "muted" }, `(${semesters(d)} сем.)`));
          }))
        : h("p", { class: "muted" }, "Ни одна дисциплина ещё не завершена – проверять остаточные знания пока не по чему."),
      plan.not_finished.length
        ? h("p", { class: "muted small" }, "Ещё изучаются или впереди: ",
            plan.not_finished.map((d) => `${d.name} (${semesters(d)})`).join(", "))
        : null,
      plan.unplanned.length
        ? h("p", { class: "small error" }, "Без семестров в учебном плане (в тест не попадут): ",
            plan.unplanned.join(", "), ". Укажите их в «Справочники → Учебный план».")
        : null,
    );
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
    drawDisciplines();
    drawCompetencies();
  }

  function resetSemester() {
    semester.value = groupsById.get(Number(group.value))?.current_semester ?? "";
  }
  semester.addEventListener("change", loadPlan);
  ignorePlan.addEventListener("change", () => {
    semester.disabled = ignorePlan.checked;
    loadPlan();
  });
  perCompetency.addEventListener("input", drawSummary);
  variantsInput.addEventListener("input", drawSummary);

  const newSection = h("div", {},
    h("div", { class: "row" },
      h("div", {}, h("label", {}, "Семестр, в котором сейчас группа"), semester),
      h("div", { style: "padding-bottom:10px" }, semesterHint),
    ),
    h("label", { class: "inline small" }, ignorePlan, "Не учитывать учебный план (все дисциплины)"),
    disciplineBox,
    h("h3", {}, "Компетенции"),
    competencyBox,
    h("div", { class: "row" },
      h("div", { style: "flex:1;min-width:240px" }, h("label", {}, "Название теста"), title, titleHint),
      h("div", {}, h("label", {}, "Вопросов на компетенцию"), perCompetency),
      h("div", {}, h("label", {}, "Вариантов"), variantsInput),
    ),
    h("p", { class: "muted small", style: "margin:4px 0 0" }, variantsHint),
    summary,
  );

  // --- готовый тест ---
  const existing = h("select");
  function drawExisting() {
    const groupId = Number(group.value);
    fill(existing, tests.map((t) => {
      const assigned = t.group_ids.map((id) => groupsById.get(id)?.name).filter(Boolean);
      const already = t.group_ids.includes(groupId);
      return h("option", { value: t.id, disabled: already },
        `${t.title} – ${t.questions_per_variant} вопр., вариантов: ${t.variant_count}`,
        assigned.length ? ` (назначен: ${assigned.join(", ")})` : "",
        already ? " – уже у этой группы" : "");
    }));
    const firstFree = [...existing.options].find((o) => !o.disabled);
    if (firstFree) existing.value = firstFree.value;
  }
  const existingSection = h("div", {},
    h("label", {}, "Тест"),
    existing,
    h("p", { class: "muted small" }, "Вопросы те же, что у других групп, – результаты можно сравнивать."),
  );

  group.addEventListener("change", () => {
    resetSemester();
    resetVariants();
    drawExisting();
    loadPlan();
  });

  const submit = h("button", { class: "primary" });
  function switchMode() {
    err.clear();
    newSection.hidden = !modeNew.checked;
    existingSection.hidden = modeNew.checked;
    title.required = modeNew.checked; // скрытое обязательное поле заблокировало бы отправку
    submit.textContent = modeNew.checked ? "Собрать и назначить" : "Назначить";
    if (modeNew.checked) drawSummary();
    else submit.disabled = false;
  }
  modeNew.addEventListener("change", switchMode);
  modeExisting.addEventListener("change", switchMode);

  render(
    h("h1", {}, "Назначить тест группе"),
    h(
      "form",
      {
        class: "card",
        onsubmit: async (event) => {
          event.preventDefault();
          err.clear();
          ok.textContent = "";
          const groupName = group.selectedOptions[0]?.textContent;
          try {
            let test;
            if (modeNew.checked) {
              const selected = selectedCompetencies();
              if (!selected.length) return err.show(new Error("выберите хотя бы одну компетенцию"));
              const allowed = allowedDisciplines();
              test = await api("/tests", {
                method: "POST",
                body: {
                  title: title.value,
                  competency_ids: selected.map((c) => c.id),
                  discipline_ids: allowed ? pool(selected, allowed).map((d) => d.id) : [],
                  questions_per_competency: Number(perCompetency.value),
                  variant_count: Number(variantsInput.value) || null,
                  semester: plan ? plan.semester : null,
                },
              });
              tests.unshift({ ...test, group_ids: [] });
            } else {
              if (!existing.value || existing.selectedOptions[0]?.disabled) {
                return err.show(new Error("выберите тест, который ещё не назначен этой группе"));
              }
              test = tests.find((t) => t.id === Number(existing.value));
            }
            await api("/assignments", {
              method: "POST",
              body: { test_id: test.id, group_id: Number(group.value) },
            });
            tests.find((t) => t.id === test.id).group_ids.push(Number(group.value));
            modeExisting.disabled = false;
            drawExisting();
            const v = test.variant_count;
            ok.textContent = `Тест «${test.title}» (${v} ${plural(v, "вариант", "варианта", "вариантов")} по ${test.questions_per_variant} вопр.) назначен группе ${groupName}. Его вопросы – во вкладке «Тесты».`;
          } catch (e) {
            err.show(e);
          }
        },
      },
      h("label", {}, "Группа"),
      group,
      h("div", { class: "row", style: "margin:14px 0 4px" },
        h("label", { class: "inline", style: "margin:0" }, modeNew, "Собрать новый тест"),
        h("label", { class: "inline", style: "margin:0" }, modeExisting, "Назначить готовый тест"),
      ),
      newSection,
      existingSection,
      h("div", { style: "margin-top:16px" }, submit),
      err.el,
      ok,
    ),
  );
  resetSemester();
  resetVariants();
  drawExisting();
  switchMode();
  await loadPlan();
}
