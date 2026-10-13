// Банк вопросов.

import { api, byId, errorBox, fill, h } from "../core.js";

export async function adminQuestions(render) {
  const [competencies, disciplines] = await Promise.all([api("/competencies"), api("/disciplines")]);
  const comps = byId(competencies);
  const discs = byId(disciplines);
  const indicators = byId(competencies.flatMap((c) => c.indicators));

  const filterCompetency = h("select", {}, h("option", { value: "" }, "Все компетенции"),
    competencies.map((c) => h("option", { value: c.id }, c.code)));
  const filterDiscipline = h("select", {}, h("option", { value: "" }, "Все дисциплины"),
    disciplines.map((d) => h("option", { value: d.id }, d.name)));
  const err = errorBox();
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
            h("tr", {}, ["Вопрос", "Компетенция", "Индикатор", "Дисциплина", "Вариантов", ""].map((t) => h("th", {}, t))),
            questions.map((q) =>
              h("tr", {},
                h("td", { class: "wrap" }, q.text, q.in_use ? [" ", h("span", { class: "badge ok" }, "в тестах")] : null),
                h("td", {}, comps.get(q.competency_id)?.code || "—"),
                h("td", {}, indicators.get(q.indicator_id)?.code || "—"),
                h("td", { class: "wrap" }, discs.get(q.discipline_id)?.name || "—"),
                h("td", {}, q.options.length),
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
    const competency = h("select", { required: true, disabled: locked },
      competencies.map((c) => h("option", { value: c.id }, `${c.code} — ${c.description}`)));
    const indicator = h("select");
    const discipline = h("select", {}, h("option", { value: "" }, "Без дисциплины"),
      disciplines.map((d) => h("option", { value: d.id }, d.name)));
    const text = h("textarea", { rows: 3, required: true });
    const options = h("div", { class: "options" });

    function drawIndicators(selected) {
      const c = comps.get(Number(competency.value));
      fill(indicator,
        h("option", { value: "" }, "Без индикатора"),
        (c?.indicators || []).map((i) => h("option", { value: i.id }, `${i.code} — ${i.description}`)),
      );
      indicator.value = selected ? String(selected) : "";
    }
    competency.addEventListener("change", () => drawIndicators(null));

    const radioName = `correct-${Date.now()}`;
    function optionRow(o = { text: "", is_correct: false }) {
      const row = h("div", { class: "option-row" },
        h("input", { type: "radio", name: radioName, checked: o.is_correct, disabled: locked, title: "Правильный ответ" }),
        h("input", { type: "text", value: o.text, required: true, placeholder: "Вариант ответа" }),
        locked ? null : h("button", { type: "button", class: "link danger", onclick: () => row.remove() }, "✕"),
      );
      row.dataset.id = o.id ?? "";
      return row;
    }

    if (q) {
      competency.value = String(q.competency_id);
      discipline.value = q.discipline_id ? String(q.discipline_id) : "";
      text.value = q.text;
      q.options.forEach((o) => options.append(optionRow(o)));
    } else {
      if (filterCompetency.value) competency.value = filterCompetency.value;
      if (filterDiscipline.value) discipline.value = filterDiscipline.value;
      options.append(optionRow({ text: "", is_correct: true }), optionRow(), optionRow(), optionRow());
    }
    drawIndicators(q?.indicator_id);

    fill(formSlot,
      h("form", {
        class: "card edit-form",
        onsubmit: async (event) => {
          event.preventDefault();
          formErr.clear();
          const rows = [...options.querySelectorAll(".option-row")];
          const body = {
            competency_id: Number(competency.value),
            indicator_id: indicator.value ? Number(indicator.value) : null,
            discipline_id: discipline.value ? Number(discipline.value) : null,
            text: text.value.trim(),
            options: rows.map((r) => ({
              ...(r.dataset.id ? { id: Number(r.dataset.id) } : {}),
              text: r.querySelector("input[type=text]").value.trim(),
              is_correct: r.querySelector("input[type=radio]").checked,
            })),
          };
          if (!body.options.some((o) => o.is_correct)) return formErr.show(new Error("отметьте правильный вариант"));
          try {
            if (q) await api(`/questions/${q.id}`, { method: "PUT", body });
            else await api("/questions", { method: "POST", body });
            fill(formSlot);
            await refresh();
          } catch (e) {
            formErr.show(e);
          }
        },
      },
      h("h2", { style: "margin-top:0" }, q ? "Изменить вопрос" : "Новый вопрос"),
      locked ? h("p", { class: "muted" }, "Вопрос уже входит в собранные тесты, по нему могут быть ответы студентов. Можно править формулировки, индикатор и дисциплину; для остального создайте новый вопрос.") : null,
      h("label", {}, "Компетенция"), competency,
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Индикатор"), indicator),
        h("div", {}, h("label", {}, "Дисциплина"), discipline),
      ),
      h("label", {}, "Текст вопроса"), text,
      h("label", {}, "Варианты ответа (отметьте правильный)"), options,
      locked ? null : h("button", { type: "button", class: "link", onclick: () => options.append(optionRow()) }, "+ вариант"),
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
  filterDiscipline.addEventListener("change", refresh);
  render(
    h("h1", {}, "Банк вопросов"),
    h("div", { class: "card" },
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Компетенция"), filterCompetency),
        h("div", {}, h("label", {}, "Дисциплина"), filterDiscipline),
        h("button", { class: "primary", onclick: () => openForm(null) }, "Новый вопрос"),
      ),
      err.el,
      h("div", { style: "margin-top:12px" }, tableSlot),
    ),
    formSlot,
  );
  await refresh();
}
