// Назначение теста группе: собрать новый или выбрать готовый.

import { api, errorBox, fill, h, render } from "../core.js";

export async function adminAssign() {
  const [groups, competencies, disciplines, questions, tests] = await Promise.all([
    api("/groups"),
    api("/competencies"),
    api("/disciplines"),
    api("/questions"),
    api("/tests"),
  ]);
  const groupNames = new Map(groups.map((g) => [g.id, g.name]));
  const err = errorBox();
  const ok = h("div", { class: "success" });

  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const modeNew = h("input", { type: "radio", name: "assign-mode", checked: true });
  const modeExisting = h("input", { type: "radio", name: "assign-mode", disabled: !tests.length });

  // --- новый тест ---
  const titleKey = (t) => t.split(/\s+/).filter(Boolean).join(" ").toLowerCase();
  const title = h("input", { type: "text", required: true, placeholder: "например, Входной контроль ПИ-21, осень" });
  const titleHint = h("div", { class: "error small", style: "margin-top:4px" });
  title.addEventListener("input", () => {
    const taken = tests.find((t) => titleKey(t.title) === titleKey(title.value));
    titleHint.textContent = taken ? "Тест с таким названием уже есть — назовите иначе или выберите «Назначить готовый тест»" : "";
  });
  const discipline = h(
    "select",
    {},
    h("option", { value: "" }, "Все дисциплины"),
    disciplines.map((d) => h("option", { value: d.id }, d.name)),
  );
  const perCompetency = h("input", { type: "number", min: 1, max: 50, value: 5 });
  const checks = new Map();

  // Сколько вопросов есть в банке по компетенции с учётом выбранной дисциплины.
  function available(competencyId) {
    const d = discipline.value ? Number(discipline.value) : null;
    return questions.filter(
      (q) => q.competency_id === competencyId && (d === null || q.discipline_id === d),
    ).length;
  }

  const list = h("div", { class: "check-list" });
  function drawCompetencies() {
    const d = discipline.value ? disciplines.find((x) => x.id === Number(discipline.value)) : null;
    const visible = d ? competencies.filter((c) => d.competency_ids.includes(c.id)) : competencies;
    fill(list,
      ...["УК", "ОПК", "ПК"].map((kind) => {
        const items = visible.filter((c) => c.kind === kind);
        if (!items.length) return null;
        return h(
          "div",
          {},
          h("h2", {}, kind),
          items.map((c) => {
            const box = checks.get(c.id) || h("input", { type: "checkbox", value: c.id });
            checks.set(c.id, box);
            return h(
              "label",
              {},
              box,
              h("strong", {}, c.code),
              ` — ${c.description} `,
              h("span", { class: "muted" }, `(вопросов: ${available(c.id)})`),
            );
          }),
        );
      }),
    );
  }
  discipline.addEventListener("change", drawCompetencies);
  drawCompetencies();

  const newSection = h("div", {},
    h("label", {}, "Название теста"),
    title,
    titleHint,
    h("div", { class: "row" },
      h("div", {}, h("label", {}, "Дисциплина"), discipline),
      h("div", {}, h("label", {}, "Вопросов на компетенцию"), perCompetency),
    ),
    list,
  );

  // --- готовый тест ---
  const existing = h("select");
  function drawExisting() {
    const groupId = Number(group.value);
    fill(existing, tests.map((t) => {
      const assigned = t.group_ids.map((id) => groupNames.get(id)).filter(Boolean);
      const already = t.group_ids.includes(groupId);
      return h("option", { value: t.id, disabled: already },
        `${t.title} — ${t.question_ids.length} вопр.`,
        assigned.length ? ` (назначен: ${assigned.join(", ")})` : "",
        already ? " — уже у этой группы" : "");
    }));
    const firstFree = [...existing.options].find((o) => !o.disabled);
    if (firstFree) existing.value = firstFree.value;
  }
  group.addEventListener("change", drawExisting);
  drawExisting();
  const existingSection = h("div", {},
    h("label", {}, "Тест"),
    existing,
    h("p", { class: "muted small" }, "Вопросы те же, что у других групп, — результаты можно сравнивать."),
  );

  function switchMode() {
    err.clear();
    newSection.hidden = !modeNew.checked;
    existingSection.hidden = modeNew.checked;
    title.required = modeNew.checked; // скрытое обязательное поле заблокировало бы отправку
    submit.textContent = modeNew.checked ? "Собрать и назначить" : "Назначить";
  }
  modeNew.addEventListener("change", switchMode);
  modeExisting.addEventListener("change", switchMode);
  const submit = h("button", { class: "primary" });

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
              const ids = [...checks.entries()]
                .filter(([, box]) => box.checked && box.isConnected)
                .map(([id]) => id);
              if (!ids.length) return err.show(new Error("выберите хотя бы одну компетенцию"));
              test = await api("/tests", {
                method: "POST",
                body: {
                  title: title.value,
                  discipline_id: discipline.value ? Number(discipline.value) : null,
                  competency_ids: ids,
                  questions_per_competency: Number(perCompetency.value),
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
            ok.textContent = `Тест «${test.title}» (${test.question_ids.length} вопр.) назначен группе ${groupName}`;
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
  switchMode();
}
