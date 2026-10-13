// Отчёты администратора: результаты группы и ПК → ОТФ по студенту.

import { api, fill, h, masteryBadge } from "../core.js";
import { laborFunctionsView } from "../reports.js";

export async function adminGroupResults(render) {
  const groups = await api("/groups");
  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const out = h("div", { class: "table-wrap" });

  async function draw() {
    const [report, settings] = await Promise.all([
      api(`/reports/groups/${group.value}/competencies`),
      api("/settings"),
    ]);
    const codes = [...new Set(report.students.flatMap((s) => s.competencies.map((c) => c.code)))].sort();
    if (!codes.length) {
      fill(out, h("p", { class: "muted" }, "Группа ещё не проходила тесты"));
      return;
    }
    fill(out,
      h("p", { class: "muted small", style: "margin-top:0" },
        `Зелёным — компетенция сформирована (от ${Math.round(settings.mastery_threshold * 100)}% верных ответов; порог меняется в «Справочники → Настройки»).`),
      h("table", {},
        h("tr", {}, h("th", {}, "Студент"), codes.map((c) => h("th", {}, c))),
        report.students.map((s) => {
          const byCode = new Map(s.competencies.map((c) => [c.code, c]));
          return h("tr", {},
            h("td", {}, s.full_name),
            codes.map((c) => h("td", {}, byCode.has(c) ? masteryBadge(byCode.get(c)) : h("span", { class: "muted" }, "—"))),
          );
        }),
      ),
    );
  }
  group.addEventListener("change", draw);
  render(
    h("h1", {}, "Результаты группы"),
    h("div", { class: "card" }, h("label", {}, "Группа"), group),
    h("div", { class: "card" }, out),
  );
  if (groups.length) await draw();
}

export async function adminLaborFunctions(render) {
  const students = await api("/students");
  const student = h("select", {}, students.map((s) => h("option", { value: s.id }, s.full_name)));
  const out = h("div");
  async function draw() {
    const report = await api(`/reports/students/${student.value}/labor-functions`);
    fill(out, laborFunctionsView(report));
  }
  student.addEventListener("change", draw);
  render(
    h("h1", {}, "ПК → ОТФ: трудовые функции студента"),
    h("div", { class: "card" },
      h("label", {}, "Студент"),
      student,
      h("p", { class: "muted" }, "ТФ закрыта, если сформированы все связанные с ней компетенции."),
    ),
    out,
  );
  if (students.length) await draw();
}
