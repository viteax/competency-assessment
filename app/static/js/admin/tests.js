// Собранные тесты: варианты с вопросами, кому назначены, сколько прошли; снять назначение,
// удалить тест, пока его никто не открывал.

import { api, errorBox, fill, h, QUESTION_KINDS } from "../core.js";

export async function adminTests(render) {
  const [tests, competencies, disciplines] = await Promise.all([
    api("/tests"),
    api("/competencies"),
    api("/disciplines"),
  ]);
  const codes = new Map(competencies.map((c) => [c.id, c.code]));
  const disciplineNames = new Map(disciplines.map((d) => [d.id, d.name]));
  const err = errorBox();
  const detail = h("div");
  const table = h("div", { class: "table-wrap" });

  function drawTable() {
    fill(table, tests.length
      ? h("table", {},
          h("tr", {}, ["Тест", "Семестр", "Вариантов", "Вопросов у студента", "Создан", ""].map((t) => h("th", {}, t))),
          tests.map((t) => h("tr", {},
            h("td", { class: "wrap" }, t.title),
            h("td", {}, t.semester ?? "—"),
            h("td", {}, t.variant_count),
            h("td", {}, t.questions_per_variant),
            h("td", {}, new Date(t.created_at).toLocaleDateString("ru-RU")),
            h("td", { class: "actions" }, h("button", { class: "link", onclick: () => open(t.id) }, "Открыть")),
          )))
      : h("p", { class: "muted" }, "Тестов пока нет — соберите первый во вкладке «Назначить тест»."));
  }

  async function open(testId) {
    err.clear();
    let t;
    try {
      t = await api(`/tests/${testId}`);
    } catch (e) {
      return err.show(e);
    }
    const detailErr = errorBox();
    const variant = h("select", { "aria-label": "Вариант для Word" },
      h("option", { value: "" }, t.variant_count > 1 ? "Все варианты" : "Тест"),
      t.variant_count > 1 ? t.variants.map((v) => h("option", { value: v.variant }, `Вариант ${v.variant}`)) : null);
    const blank = h("a", { class: "button", download: "" }, "Скачать в Word");
    const key = h("a", { class: "button", download: "" }, "Ключ с ответами");
    const setLinks = () => {
      const params = new URLSearchParams(variant.value ? { variant: variant.value } : {});
      blank.href = `/tests/${t.id}/document.docx?${params}`;
      params.set("key", "true");
      key.href = `/tests/${t.id}/document.docx?${params}`;
    };
    variant.addEventListener("change", setLinks);
    setLinks();
    fill(detail, h("div", { class: "card" },
      h("h2", { style: "margin-top:0" }, t.title),
      h("div", { class: "row", style: "margin-bottom:8px" },
        t.variant_count > 1 ? h("div", {}, variant) : null, blank, key),
      h("p", { class: "muted small", style: "margin-top:0" }, "Документ оформлен по образцу фонда оценочных материалов: бланк с пустыми полями «Ответ» и отдельно ключ с правильными ответами."),
      h("p", { class: "muted" },
        t.semester ? `Для ${t.semester}-го семестра. ` : "",
        t.discipline_ids.length
          ? `Вопросы из дисциплин: ${t.discipline_ids.map((id) => disciplineNames.get(id)).join(", ")}.`
          : "Вопросы из любых дисциплин."),
      h("h3", {}, "Назначен группам"),
      t.assignments.length
        ? h("table", {},
            h("tr", {}, ["Группа", "Назначен", "Открыли", "Сдали", ""].map((x) => h("th", {}, x))),
            t.assignments.map((a) => h("tr", {},
              h("td", {}, a.group_name),
              h("td", {}, new Date(a.created_at).toLocaleDateString("ru-RU")),
              h("td", {}, a.started),
              h("td", {}, a.finished),
              h("td", { class: "actions" }, a.started
                ? h("span", { class: "muted small" }, "уже проходят")
                : h("button", {
                    class: "link danger",
                    onclick: async () => {
                      if (!confirm(`Снять тест с группы ${a.group_name}?`)) return;
                      try {
                        await api(`/assignments/${a.id}`, { method: "DELETE" });
                        const listed = tests.find((x) => x.id === t.id);
                        listed.group_ids = listed.group_ids.filter((id) => id !== a.group_id);
                        await open(t.id);
                      } catch (e) {
                        detailErr.show(e);
                      }
                    },
                  }, "Снять назначение")),
            )))
        : h("p", { class: "muted" }, "Пока никому не назначен."),
      h("h3", {}, `Варианты (${t.variant_count})`),
      h("p", { class: "muted small" }, "Варианты не пересекаются по вопросам. Каждому студенту при открытии теста достаётся случайный из тех, что выданы реже, а порядок вопросов и ответов перемешивается. Правильные ответы отмечены ✓, для последовательности — верный порядок."),
      t.variants.map((v) => h("details", { open: t.variant_count === 1 },
        h("summary", {}, `Вариант ${v.variant} — ${v.questions.length} вопр.`),
        h("ol", {}, v.questions.map((q) => h("li", { style: "margin:8px 0" },
          h("span", { class: "badge" }, codes.get(q.competency_id) || "—"), " ",
          h("span", { class: "muted small" }, QUESTION_KINDS[q.kind], ". "), q.text,
          answerKey(q),
        ))),
      )),
      h("div", { class: "row", style: "margin-top:16px" },
        h("button", {
          class: "danger",
          disabled: t.assignments.some((a) => a.started),
          title: t.assignments.some((a) => a.started) ? "Тест уже проходили — удалить нельзя, иначе пропадут результаты" : "",
          onclick: async () => {
            if (!confirm(`Удалить тест «${t.title}»? Назначения группам тоже удалятся.`)) return;
            try {
              await api(`/tests/${t.id}`, { method: "DELETE" });
              tests.splice(tests.findIndex((x) => x.id === t.id), 1);
              fill(detail);
              drawTable();
            } catch (e) {
              detailErr.show(e);
            }
          },
        }, "Удалить тест"),
        h("button", { type: "button", onclick: () => fill(detail) }, "Закрыть"),
      ),
      detailErr.el,
    ));
    detail.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  render(
    h("h1", {}, "Тесты"),
    h("div", { class: "card" }, table, err.el),
    detail,
  );
  drawTable();
}

// Правильный ответ на вопрос любого типа (для преподавателя).
function answerKey(q) {
  const opts = q.options;
  if (q.kind === "open") {
    return h("div", { class: "small" }, "✓ ", opts.map((o) => o.text).join(" / "));
  }
  if (q.kind === "sequence") {
    return h("ol", { class: "small" }, opts.map((o) => h("li", {}, o.text)));
  }
  if (q.kind === "matching") {
    const byId = new Map(opts.map((o) => [o.id, o]));
    const used = new Set(opts.map((o) => o.match_id).filter(Boolean));
    const extra = opts.filter((o) => !o.match_id && !used.has(o.id));
    return h("ul", { class: "small" },
      opts.filter((o) => o.match_id).map((o) => h("li", {}, `${o.text} → ${byId.get(o.match_id)?.text}`)),
      extra.length ? h("li", { class: "muted" }, `лишние: ${extra.map((o) => o.text).join(", ")}`) : null);
  }
  return h("ul", { class: "small" }, opts.map((o) =>
    h("li", { class: o.is_correct ? "" : "muted" }, o.is_correct ? `✓ ${o.text}` : o.text)));
}
