// Отчёты администратора: результаты группы и ПК → ОТФ по студенту.

import { api, fill, h, masteryBadge } from "../core.js";
import { profileCharts } from "../radar.js";
import { laborFunctionsView } from "../reports.js";

export async function adminGroupResults(render) {
  const [groups, tests] = await Promise.all([api("/groups"), api("/tests")]);
  const group = h("select", {}, groups.map((g) => h("option", { value: g.id }, g.name)));
  const test = h("select", { "aria-label": "Тест" });
  const excel = h("a", { class: "button", download: "" }, "Скачать Excel");
  const out = h("div", { class: "table-wrap" });
  const whom = h("select", { "aria-label": "Чья роза" });
  const charts = h("div");
  const radarHint = h("p", { class: "notice" },
    "Появится, когда студенты сдадут тест: назначьте его во вкладке «Назначить тест», студент проходит его в «Мои тесты». Для диаграммы нужно минимум 3 компетенции.");
  const radarSection = h("section", {},
    h("h2", {}, "Роза ветров"),
    h("div", { class: "card" },
      h("div", {}, h("label", {}, "Чьи результаты"), whom),
      h("p", { class: "muted small" }, "Шкала 0–5: 5 – все ответы верные. Уровень трудовой функции – среднее по связанным с ней компетенциям, которые проверялись."),
      radarHint,
    ),
    charts,
  );
  const toRadar = h("button", {
    type: "button", class: "link",
    onclick: () => radarSection.scrollIntoView({ behavior: "smooth", block: "start" }),
  }, "Роза ветров ↓");
  let report = null;

  function drawTests() {
    const groupId = Number(group.value);
    fill(test,
      h("option", { value: "" }, "Все пройденные тесты"),
      tests.filter((t) => t.group_ids.includes(groupId)).map((t) => h("option", { value: t.id }, t.title)));
  }

  const query = () => (test.value ? `?test_id=${test.value}` : "");

  async function drawCharts() {
    const studentId = whom.value;
    const params = new URLSearchParams();
    if (test.value) params.set("test_id", test.value);
    if (studentId) params.set("student_id", studentId);
    const profile = await api(`/reports/groups/${group.value}/profile?${params}`);
    const who = studentId
      ? report.students.find((s) => s.student_id === Number(studentId)).full_name
      : `группа ${report.name}, среднее`;
    fill(charts, profileCharts(profile, who));
  }

  async function draw() {
    const [loaded, settings] = await Promise.all([
      api(`/reports/groups/${group.value}/competencies${query()}`),
      api("/settings"),
    ]);
    report = loaded;
    excel.href = `/reports/groups/${group.value}/competencies.xlsx${query()}`;
    const codes = [...new Set(report.students.flatMap((s) => s.competencies.map((c) => c.code)))].sort();
    const tested = report.students.filter((s) => s.competencies.length);
    fill(whom,
      h("option", { value: "" }, "Вся группа (среднее)"),
      tested.map((s) => h("option", { value: s.student_id }, s.full_name)));
    if (!codes.length) {
      fill(out, h("p", { class: "muted" }, test.value ? "Этот тест группа ещё не проходила" : "Группа ещё не проходила тесты"));
      fill(charts);
      excel.hidden = true;
      whom.parentElement.hidden = true;
      radarHint.hidden = false;
      return;
    }
    excel.hidden = false;
    whom.parentElement.hidden = false;
    radarHint.hidden = true;
    fill(out,
      h("p", { class: "muted small mt-0" },
        `«N из M» – верных ответов из заданных. Зелёным – компетенция сформирована (от ${Math.round(settings.mastery_threshold * 100)}% верных; порог меняется в «База → Настройки»).`),
      h("table", {},
        h("tr", {}, h("th", {}, "Студент"), h("th", {}, "Дата"), codes.map((c) => h("th", {}, c))),
        report.students.map((s) => {
          const byCode = new Map(s.competencies.map((c) => [c.code, c]));
          return h("tr", {},
            h("td", {}, s.full_name),
            h("td", {}, s.tested_at ? new Date(s.tested_at).toLocaleDateString("ru-RU") : h("span", { class: "muted" }, "–")),
            codes.map((c) => h("td", {}, byCode.has(c) ? masteryBadge(byCode.get(c)) : h("span", { class: "muted" }, "–"))),
          );
        }),
      ),
    );
    await drawCharts();
  }

  group.addEventListener("change", () => { drawTests(); draw(); });
  test.addEventListener("change", draw);
  whom.addEventListener("change", drawCharts);
  render(
    h("h1", {}, "Результаты группы"),
    h("div", { class: "card" },
      h("div", { class: "row" },
        h("div", {}, h("label", {}, "Группа"), group),
        h("div", { class: "grow" }, h("label", {}, "Тест"), test),
        h("div", {}, excel),
        h("div", { class: "pad-bottom" }, toRadar),
      ),
    ),
    h("div", { class: "card" }, out),
    radarSection,
  );
  if (groups.length) {
    drawTests();
    await draw();
  }
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
